"""健康检查和系统状态 API"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox_manager import __version__
from sandbox_manager.dependencies import get_db, get_sandbox_service
from sandbox_manager.models.database import ActiveSandbox, Template
from sandbox_manager.models.schemas import HealthResponse, SystemStatus
from sandbox_manager.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check(
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
) -> HealthResponse:
    """检查 API 服务、OpenSandbox 和数据库的健康状态"""
    # 检查数据库
    db_ok = True
    try:
        await session.execute(select(func.count()).select_from(Template))
    except Exception:
        db_ok = False
        logger.error("数据库连接检查失败", exc_info=True)

    # 检查 OpenSandbox（轻量级 HTTP ping）
    opensandbox_ok = False
    try:
        opensandbox_ok = await sandbox_service.ping_opensandbox()
    except Exception:
        logger.error("OpenSandbox 连通性检查失败", exc_info=True)

    return HealthResponse(
        status="ok" if (db_ok and opensandbox_ok) else "degraded",
        version=__version__,
        opensandbox_connected=opensandbox_ok,
        database_ok=db_ok,
    )


@router.get("/status", response_model=SystemStatus, summary="系统状态")
async def system_status(
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
) -> SystemStatus:
    """获取系统整体状态: 活跃沙盒数、已构建模板数等"""
    # 活跃沙盒数
    result = await session.execute(
        select(func.count()).select_from(ActiveSandbox)
    )
    active_sandboxes = result.scalar() or 0

    # 已构建模板数
    result = await session.execute(
        select(func.count())
        .select_from(Template)
        .where(Template.status == "ready")
    )
    built_templates = result.scalar() or 0

    # 总模板数
    result = await session.execute(
        select(func.count()).select_from(Template)
    )
    total_templates = result.scalar() or 0

    # OpenSandbox 连接状态（轻量级 HTTP ping）
    opensandbox_connected = await sandbox_service.ping_opensandbox()

    return SystemStatus(
        api_running=True,
        opensandbox_connected=opensandbox_connected,
        active_sandboxes=active_sandboxes,
        built_templates=built_templates,
        total_templates=total_templates,
    )
