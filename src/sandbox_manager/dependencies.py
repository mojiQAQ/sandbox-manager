"""FastAPI 依赖注入 - 提供全局服务实例和数据库 session"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox_manager.db.engine import get_session
from sandbox_manager.services.connector import ConnectorService
from sandbox_manager.services.docker_bridge import DockerBridge
from sandbox_manager.services.sandbox_service import SandboxService
from sandbox_manager.services.template_service import TemplateService

# 全局单例
_docker_bridge: DockerBridge | None = None
_sandbox_service: SandboxService | None = None
_template_service: TemplateService | None = None
_connector_service: ConnectorService | None = None


def get_docker_bridge() -> DockerBridge:
    """获取 DockerBridge 单例"""
    global _docker_bridge
    if _docker_bridge is None:
        _docker_bridge = DockerBridge()
    return _docker_bridge


def get_sandbox_service() -> SandboxService:
    """获取 SandboxService 单例"""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service


def get_template_service(
    sandbox_service: SandboxService = Depends(get_sandbox_service),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
) -> TemplateService:
    """获取 TemplateService 单例"""
    global _template_service
    if _template_service is None:
        _template_service = TemplateService(
            sandbox_service=sandbox_service,
            docker_bridge=docker_bridge,
        )
    return _template_service


def get_connector_service(
    sandbox_service: SandboxService = Depends(get_sandbox_service),
) -> ConnectorService:
    """获取 ConnectorService 单例"""
    global _connector_service
    if _connector_service is None:
        _connector_service = ConnectorService(sandbox_service=sandbox_service)
    return _connector_service


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库 session（请求级别生命周期）"""
    async for session in get_session():
        yield session
