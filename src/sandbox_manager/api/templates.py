"""模板管理 API - CRUD + 构建 + 构建状态"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox_manager.dependencies import get_db, get_template_service
from sandbox_manager.exceptions import (
    SandboxManagerError,
    TemplateBuildInProgressError,
    TemplateNotFoundError,
)
from sandbox_manager.models.schemas import (
    ApiResponse,
    TemplateBuildStatus,
    TemplateDetail,
    TemplateListItem,
)
from sandbox_manager.services.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["模板管理"])


@router.get("", response_model=list[TemplateListItem], summary="模板列表")
async def list_templates(
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> list[TemplateListItem]:
    """获取所有模板，包含名称、状态、连接类型、镜像大小等"""
    templates = await template_service.list_templates(session)
    return [
        TemplateListItem(
            id=t.id,
            name=t.name,
            description=t.description,
            status=t.status,
            source=t.source,
            connect_type=t.connect_type,
            docker_image=t.docker_image,
            size_bytes=t.size_bytes,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.get("/{name}", response_model=TemplateDetail, summary="模板详情")
async def get_template(
    name: str,
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateDetail:
    """获取指定模板的详情，包含完整构建配置"""
    try:
        t = await template_service.get_template(session, name)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)

    return TemplateDetail(
        id=t.id,
        name=t.name,
        description=t.description,
        status=t.status,
        source=t.source,
        connect_type=t.connect_type,
        connect_port=t.connect_port,
        docker_image=t.docker_image,
        docker_image_id=t.docker_image_id,
        base_image=t.base_image,
        entrypoint=json.loads(t.entrypoint) if t.entrypoint else [],
        env=json.loads(t.env) if t.env else {},
        ports=json.loads(t.ports) if t.ports else {},
        install_commands=json.loads(t.install_commands) if t.install_commands else [],
        size_bytes=t.size_bytes,
        build_error=t.build_error,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.delete("/{name}", response_model=ApiResponse, summary="删除模板")
async def delete_template(
    name: str,
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """删除模板，同时清理对应的 Docker 镜像"""
    try:
        await template_service.delete_template(session, name)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    return ApiResponse(success=True, message=f"模板 '{name}' 已删除")


@router.post("/{name}/build", response_model=ApiResponse, summary="触发模板构建")
async def build_template(
    name: str,
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """触发异步模板构建

    构建流程: 创建临时沙盒 -> 执行安装命令 -> docker commit -> 注册元数据
    构建是异步操作，可通过 build-status 接口查询进度。
    """
    try:
        await template_service.build_template(session, name)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except TemplateBuildInProgressError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    return ApiResponse(
        success=True,
        message=f"模板 '{name}' 构建已启动，请通过 build-status 接口查询进度",
    )


@router.get(
    "/{name}/build-status",
    response_model=TemplateBuildStatus,
    summary="查询构建状态",
)
async def get_build_status(
    name: str,
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateBuildStatus:
    """查询模板的构建状态"""
    try:
        template = await template_service.get_template(session, name)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)

    # 检查内存中的构建任务
    in_progress = template_service.get_build_status(name)
    status = in_progress if in_progress else template.status

    return TemplateBuildStatus(
        name=template.name,
        status=status,
        build_error=template.build_error,
    )
