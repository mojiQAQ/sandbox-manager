"""ConnectorService - 自适应连接器

根据模板的 connect_type 返回不同的连接信息:
- shell: 返回 docker exec 命令
- url: 返回通过 OpenSandbox endpoint 或 Docker 端口映射获取的访问 URL
- port: 返回端口映射列表

连接前检查沙盒状态，未运行时给出提示。
"""

import logging

from sandbox_manager.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)


class ConnectorService:
    """自适应连接服务"""

    def __init__(self, sandbox_service: SandboxService) -> None:
        self._sandbox_service = sandbox_service

    async def get_connect_info(
        self,
        sandbox_id: str,
        sandbox_status: str,
        connect_type: str,
        connect_port: int | None = None,
        ports: dict[str, int] | None = None,
        docker_container_name: str | None = None,
    ) -> dict:
        """根据模板配置获取连接信息

        Args:
            sandbox_id: 沙盒 ID
            sandbox_status: 沙盒当前状态
            connect_type: 连接类型 (shell/url/port)
            connect_port: 主连接端口（url 类型时使用）
            ports: 端口映射配置
            docker_container_name: Docker 容器名

        Returns:
            连接信息字典，结构根据 connect_type 不同而变化
        """
        container_name = docker_container_name or f"sandbox-{sandbox_id}"

        if connect_type == "shell":
            return self._build_shell_info(sandbox_id, container_name)

        elif connect_type == "url":
            return await self._build_url_info(
                sandbox_id, container_name, connect_port, ports
            )

        elif connect_type == "port":
            return await self._build_port_info(
                sandbox_id, container_name, connect_port, ports
            )

        else:
            # 未知类型，回退到 shell
            logger.warning(
                "未知的 connect_type: %s, 回退到 shell", connect_type
            )
            return self._build_shell_info(sandbox_id, container_name)

    def _build_shell_info(self, sandbox_id: str, container_name: str) -> dict:
        """构建 shell 类型的连接信息"""
        return {
            "connect_type": "shell",
            "command": f"docker exec -it {container_name} /bin/bash",
            "sandbox_id": sandbox_id,
            "container_name": container_name,
        }

    async def _build_url_info(
        self,
        sandbox_id: str,
        container_name: str,
        connect_port: int | None,
        ports: dict[str, int] | None,
    ) -> dict:
        """构建 url 类型的连接信息

        尝试通过 OpenSandbox SDK 获取端点 URL，失败时回退到 Docker 端口映射。
        """
        url = None

        if connect_port:
            try:
                url = await self._sandbox_service.get_endpoint(sandbox_id, connect_port)
                # OpenSandbox 可能返回不含协议前缀的 URL，如 "127.0.0.1:PORT/proxy/8443"
                if url and not url.startswith(("http://", "https://")):
                    url = f"http://{url}"
            except Exception:
                logger.warning(
                    "通过 OpenSandbox 获取端点失败，将尝试 Docker 端口映射: sandbox=%s, port=%d",
                    sandbox_id,
                    connect_port,
                )
                # 回退: 使用 localhost + 端口映射
                url = f"http://localhost:{connect_port}"

        result = {
            "connect_type": "url",
            "url": url,
            "port": connect_port,
            "sandbox_id": sandbox_id,
            "container_name": container_name,
        }

        # 如果有额外端口信息也一并返回（转为 list[dict] 格式）
        if ports:
            result["ports"] = [
                {"name": name, "container_port": port, "url": f"http://localhost:{port}"}
                for name, port in ports.items()
            ]

        return result

    async def _build_port_info(
        self,
        sandbox_id: str,
        container_name: str,
        connect_port: int | None,
        ports: dict[str, int] | None,
    ) -> dict:
        """构建 port 类型的连接信息

        返回端口映射列表，并尝试获取每个端口的访问 URL。
        """
        port_mappings = []

        # 收集所有端口
        all_ports: dict[str, int] = {}
        if ports:
            all_ports.update(ports)
        if connect_port and str(connect_port) not in all_ports:
            all_ports[str(connect_port)] = connect_port

        for name, port in all_ports.items():
            mapping: dict = {
                "name": name,
                "container_port": port,
            }
            try:
                url = await self._sandbox_service.get_endpoint(sandbox_id, port)
                if url and not url.startswith(("http://", "https://")):
                    url = f"http://{url}"
                mapping["url"] = url
            except Exception:
                mapping["url"] = f"http://localhost:{port}"
                logger.debug("获取端口 %d 的端点失败，使用默认地址", port)

            port_mappings.append(mapping)

        return {
            "connect_type": "port",
            "ports": port_mappings,
            "sandbox_id": sandbox_id,
            "container_name": container_name,
        }
