"""SandboxService - OpenSandbox SDK 封装

负责:
- 连接管理: 验证 OpenSandbox server 可达性
- 沙盒创建: 从镜像创建沙盒（支持自定义 entrypoint、env、timeout）
- 沙盒暂停/恢复: 通过 OpenSandbox SDK 暂停和恢复沙盒
- 沙盒销毁: 通过 OpenSandbox SDK 销毁沙盒
- 命令执行: 在沙盒内执行命令
- 端点获取: 获取沙盒服务的访问 URL
"""

import logging
from datetime import timedelta

import httpx
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig

from sandbox_manager.config import settings
from sandbox_manager.exceptions import OpenSandboxConnectionError

logger = logging.getLogger(__name__)


class SandboxService:
    """OpenSandbox SDK 操作封装"""

    def __init__(self) -> None:
        self._config: ConnectionConfig | None = None

    @property
    def connection_config(self) -> ConnectionConfig:
        """获取 OpenSandbox 连接配置"""
        if self._config is None:
            self._config = ConnectionConfig(
                domain=f"{settings.opensandbox_host}:{settings.opensandbox_port}",
                api_key=settings.opensandbox_api_key,
                protocol=settings.opensandbox_protocol,
                request_timeout=timedelta(seconds=120),
            )
        return self._config

    async def ping_opensandbox(self, timeout: float = 2.0) -> bool:
        """轻量级检测 OpenSandbox server 是否可达

        通过 HTTP GET 请求 OpenSandbox 的 /health 端点，设置短超时。
        不会创建/销毁沙盒，适合在 health/status 端点中频繁调用。

        Args:
            timeout: HTTP 请求超时时间（秒），默认 2 秒

        Returns:
            True 表示可达，False 表示不可达
        """
        health_url = f"{settings.opensandbox_url}/health"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(health_url)
                return resp.status_code == 200
        except Exception:
            return False

    async def check_connection(self) -> bool:
        """检查 OpenSandbox server 是否可达

        通过创建并立即销毁一个测试沙盒来验证连通性。
        如果失败，返回 False 并记录错误日志。
        """
        try:
            sandbox = await Sandbox.create(
                "alpine:latest",
                connection_config=self.connection_config,
                entrypoint=["echo", "ping"],
                timeout=timedelta(seconds=60),
                resource={"cpu": "0.5", "memory": "256Mi"},
                skip_health_check=True,
            )
            await sandbox.kill()
            logger.info("OpenSandbox server 连接正常: %s", settings.opensandbox_url)
            return True
        except Exception as e:
            logger.error(
                "OpenSandbox server 连接失败: %s, 错误: %s",
                settings.opensandbox_url,
                str(e),
            )
            return False

    async def create_sandbox(
        self,
        image: str,
        entrypoint: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout_minutes: int | None = None,
    ) -> Sandbox:
        """创建沙盒

        Args:
            image: Docker 镜像名
            entrypoint: 容器启动命令，默认 tail -f /dev/null
            env: 环境变量
            timeout_minutes: 超时时间（分钟）

        Returns:
            Sandbox 实例

        Raises:
            OpenSandboxConnectionError: 无法连接到 OpenSandbox server
        """
        if entrypoint is None:
            entrypoint = ["tail", "-f", "/dev/null"]
        if env is None:
            env = {}
        if timeout_minutes is None:
            timeout_minutes = settings.default_timeout_minutes

        try:
            sandbox = await Sandbox.create(
                image,
                connection_config=self.connection_config,
                entrypoint=entrypoint,
                env=env,
                timeout=timedelta(minutes=timeout_minutes),
                resource={"cpu": "1", "memory": "512Mi"},
            )
            logger.info(
                "沙盒创建成功: id=%s, image=%s",
                sandbox.id,
                image,
            )
            return sandbox
        except Exception as e:
            logger.error("创建沙盒失败: image=%s, 错误: %s", image, str(e))
            raise OpenSandboxConnectionError(
                settings.opensandbox_url,
                str(e),
            ) from e

    async def run_command(
        self,
        sandbox: Sandbox,
        command: str,
        timeout_seconds: int = 300,
    ) -> tuple[int, str, str]:
        """在沙盒内执行命令

        Args:
            sandbox: Sandbox 实例
            command: 要执行的命令
            timeout_seconds: 命令超时时间（秒），暂未使用

        Returns:
            (exit_code, stdout, stderr) 元组
        """
        try:
            execution = await sandbox.commands.run(command)
            stdout = ""
            stderr = ""
            if execution.logs.stdout:
                stdout = "\n".join(log.text for log in execution.logs.stdout)
            if execution.logs.stderr:
                stderr = "\n".join(log.text for log in execution.logs.stderr)

            return execution.exit_code, stdout, stderr
        except Exception as e:
            logger.error("命令执行失败: %s, 错误: %s", command, str(e))
            return -1, "", str(e)

    async def kill_sandbox(self, sandbox: Sandbox) -> None:
        """销毁沙盒"""
        try:
            sandbox_id = sandbox.id
            await sandbox.kill()
            logger.info("沙盒已销毁: %s", sandbox_id)
        except Exception as e:
            logger.error("销毁沙盒失败: %s", str(e))

    async def kill_sandbox_by_id(self, sandbox_id: str) -> None:
        """通过 ID 销毁沙盒"""
        try:
            sandbox = await Sandbox.connect(
                sandbox_id,
                connection_config=self.connection_config,
            )
            await sandbox.kill()
            logger.info("沙盒已销毁: %s", sandbox_id)
        except Exception as e:
            logger.warning("通过 ID 销毁沙盒失败: %s, 错误: %s", sandbox_id, str(e))

    async def pause_sandbox(self, sandbox_id: str) -> None:
        """暂停沙盒

        通过 OpenSandbox SDK 暂停沙盒（cgroup freeze），暂停后不消耗 CPU。

        Args:
            sandbox_id: 沙盒 ID

        Raises:
            OpenSandboxConnectionError: 无法连接到 OpenSandbox server
        """
        try:
            sandbox = await Sandbox.connect(
                sandbox_id,
                connection_config=self.connection_config,
            )
            await sandbox.pause()
            logger.info("沙盒已暂停: %s", sandbox_id)
        except Exception as e:
            logger.error("暂停沙盒失败: %s, 错误: %s", sandbox_id, str(e))
            raise OpenSandboxConnectionError(
                settings.opensandbox_url,
                f"暂停沙盒失败: {e}",
            ) from e

    async def resume_sandbox(self, sandbox_id: str) -> "Sandbox":
        """恢复沙盒

        通过 OpenSandbox SDK 恢复已暂停的沙盒。

        Args:
            sandbox_id: 沙盒 ID

        Returns:
            恢复后的 Sandbox 实例

        Raises:
            OpenSandboxConnectionError: 无法连接到 OpenSandbox server
        """
        try:
            sandbox = await Sandbox.resume(
                sandbox_id=sandbox_id,
                connection_config=self.connection_config,
            )
            logger.info("沙盒已恢复: %s", sandbox_id)
            return sandbox
        except Exception as e:
            logger.error("恢复沙盒失败: %s, 错误: %s", sandbox_id, str(e))
            raise OpenSandboxConnectionError(
                settings.opensandbox_url,
                f"恢复沙盒失败: {e}",
            ) from e

    async def get_endpoint(self, sandbox_id: str, port: int) -> str:
        """获取沙盒指定端口的访问 URL

        通过 OpenSandbox SDK 获取端口映射后的实际访问地址。

        Args:
            sandbox_id: 沙盒 ID
            port: 端口号

        Returns:
            访问 URL 字符串

        Raises:
            OpenSandboxConnectionError: 获取端点失败
        """
        try:
            sandbox = await Sandbox.connect(
                sandbox_id,
                connection_config=self.connection_config,
                skip_health_check=True,
            )
            endpoint = await sandbox.get_endpoint(port)
            url = endpoint.endpoint if hasattr(endpoint, "endpoint") else str(endpoint)
            logger.info("获取端点成功: sandbox=%s, port=%d, url=%s", sandbox_id, port, url)
            return url
        except Exception as e:
            logger.error(
                "获取端点失败: sandbox=%s, port=%d, 错误: %s",
                sandbox_id,
                port,
                str(e),
            )
            raise OpenSandboxConnectionError(
                settings.opensandbox_url,
                f"获取端点失败: {e}",
            ) from e
