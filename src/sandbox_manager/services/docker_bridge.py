"""Docker Bridge - docker commit + 镜像管理

负责与 Docker Engine 直接交互的底层操作:
- docker commit: 将运行中的容器保存为镜像
- 镜像信息查询: 获取镜像大小、ID 等
- 镜像删除: 清理不需要的镜像
- 容器暂停/恢复: 快照时保证文件系统一致性

OpenSandbox 的容器命名规则: sandbox-{sandbox_id}
"""

import asyncio
import logging

import docker
from docker.errors import APIError, ImageNotFound, NotFound

from sandbox_manager.config import settings
from sandbox_manager.exceptions import DockerError

logger = logging.getLogger(__name__)


class DockerBridge:
    """Docker 操作封装"""

    def __init__(self) -> None:
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        """获取 Docker 客户端（延迟初始化）"""
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
                logger.info("Docker Engine 连接成功")
            except Exception as e:
                raise DockerError("连接 Docker Engine", str(e)) from e
        return self._client

    def get_container_name(self, sandbox_id: str) -> str:
        """根据沙盒 ID 获取 Docker 容器名"""
        return f"sandbox-{sandbox_id}"

    def get_image_tag(self, template_name: str, tag: str = "latest") -> str:
        """根据模板名生成 Docker 镜像 tag"""
        return f"{settings.docker_image_prefix}/{template_name}:{tag}"

    async def commit_container(
        self,
        sandbox_id: str,
        template_name: str,
        pause: bool = True,
    ) -> tuple[str, int]:
        """对容器执行 docker commit，返回 (image_id, size_bytes)

        Args:
            sandbox_id: 沙盒 ID
            template_name: 目标模板名称（用于生成镜像 tag）
            pause: 是否在 commit 前暂停容器

        Returns:
            (image_id, size_bytes) 元组
        """
        container_name = self.get_container_name(sandbox_id)
        image_tag = self.get_image_tag(template_name)
        repo, tag = image_tag.rsplit(":", 1)

        try:
            container = await asyncio.to_thread(self.client.containers.get, container_name)
        except NotFound as e:
            raise DockerError(
                f"查找容器 {container_name}",
                f"容器不存在，沙盒 ID: {sandbox_id}",
            ) from e

        paused = False
        try:
            if pause:
                logger.info("暂停容器 %s 以保证文件系统一致性", container_name)
                await asyncio.to_thread(container.pause)
                paused = True

            logger.info("正在执行 docker commit: %s -> %s", container_name, image_tag)
            image = await asyncio.to_thread(container.commit, repository=repo, tag=tag)
            logger.info("docker commit 完成: %s", image.id)

        except APIError as e:
            raise DockerError(f"commit 容器 {container_name}", str(e)) from e
        finally:
            if paused:
                try:
                    await asyncio.to_thread(container.unpause)
                    logger.info("容器 %s 已恢复运行", container_name)
                except APIError:
                    logger.error("恢复容器 %s 失败", container_name, exc_info=True)

        # 获取镜像大小
        try:
            await asyncio.to_thread(image.reload)
            size_bytes = image.attrs.get("Size", 0)
        except Exception:
            size_bytes = 0
            logger.warning("获取镜像大小失败", exc_info=True)

        return image.id, size_bytes

    async def get_image_info(self, image_tag: str) -> dict | None:
        """获取 Docker 镜像信息

        Returns:
            包含 id, size_bytes 的 dict，镜像不存在时返回 None
        """
        try:
            image = await asyncio.to_thread(self.client.images.get, image_tag)
            return {
                "id": image.id,
                "size_bytes": image.attrs.get("Size", 0),
                "tags": image.tags,
            }
        except ImageNotFound:
            return None
        except APIError as e:
            raise DockerError(f"查询镜像 {image_tag}", str(e)) from e

    async def remove_image(self, image_tag: str, force: bool = False) -> bool:
        """删除 Docker 镜像

        Returns:
            True 表示成功删除，False 表示镜像不存在
        """
        try:
            await asyncio.to_thread(self.client.images.remove, image_tag, force=force)
            logger.info("已删除 Docker 镜像: %s", image_tag)
            return True
        except ImageNotFound:
            logger.warning("镜像 %s 不存在，跳过删除", image_tag)
            return False
        except APIError as e:
            raise DockerError(f"删除镜像 {image_tag}", str(e)) from e

    async def check_docker(self) -> bool:
        """检查 Docker Engine 是否可用"""
        try:
            await asyncio.to_thread(self.client.ping)
            return True
        except Exception:
            return False

    async def get_container_status(self, container_name: str) -> str | None:
        """获取容器当前状态

        Returns:
            容器状态字符串 (running/paused/exited/...)，容器不存在时返回 None
        """
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_name)
            return container.status
        except NotFound:
            return None
        except APIError as e:
            logger.warning("获取容器状态失败: %s, 错误: %s", container_name, str(e))
            return None
