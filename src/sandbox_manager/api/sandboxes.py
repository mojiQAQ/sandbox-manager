"""沙盒管理 API - M1 + M2: 创建/列表/详情/销毁/快照/暂停/恢复/连接信息/批量销毁"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox_manager.dependencies import (
    get_connector_service,
    get_db,
    get_docker_bridge,
    get_sandbox_service,
    get_template_service,
)
from sandbox_manager.exceptions import (
    SandboxManagerError,
    SandboxNotFoundError,
    SandboxStateError,
    TemplateAlreadyExistsError,
    TemplateNotFoundError,
)
from sandbox_manager.models.database import ActiveSandbox, Template
from sandbox_manager.models.schemas import (
    ApiResponse,
    BatchDeleteResponse,
    ConnectInfo,
    CreateSandboxRequest,
    SandboxDetail,
    SandboxListItem,
    SaveTemplateRequest,
)
from sandbox_manager.services.connector import ConnectorService
from sandbox_manager.services.docker_bridge import DockerBridge
from sandbox_manager.services.sandbox_service import SandboxService
from sandbox_manager.services.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sandboxes", tags=["沙盒管理"])


# --- 辅助函数 ---


async def _get_sandbox_or_404(
    session: AsyncSession, sandbox_id: str
) -> ActiveSandbox:
    """获取沙盒记录，不存在则抛出 404"""
    result = await session.execute(
        select(ActiveSandbox).where(ActiveSandbox.id == sandbox_id)
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"沙盒 '{sandbox_id}' 不存在")
    return sandbox


async def _get_template_for_sandbox(
    session: AsyncSession, sandbox: ActiveSandbox
) -> Template | None:
    """获取沙盒关联的模板"""
    if not sandbox.template_id:
        return None
    result = await session.execute(
        select(Template).where(Template.id == sandbox.template_id)
    )
    return result.scalar_one_or_none()


def _map_docker_status(docker_status: str | None) -> str:
    """将 Docker 容器状态映射为沙盒状态

    Docker 状态: running, paused, exited, created, restarting, removing, dead
    沙盒状态: running, paused, stopped
    """
    if docker_status is None:
        return "stopped"
    mapping = {
        "running": "running",
        "paused": "paused",
        "exited": "stopped",
        "created": "stopped",
        "restarting": "running",
        "removing": "stopped",
        "dead": "stopped",
    }
    return mapping.get(docker_status, "stopped")


async def _sync_sandbox_status(
    session: AsyncSession,
    sandbox: ActiveSandbox,
    docker_bridge: DockerBridge,
) -> None:
    """同步沙盒数据库状态与 Docker 容器实际状态

    查询 Docker 容器的真实状态，如果与数据库记录不一致则更新数据库。
    所有读取或操作沙盒状态的端点都应在状态校验前调用此函数，
    以避免基于过时数据库状态做判断。
    """
    docker_status = await docker_bridge.get_container_status(
        sandbox.docker_container_name
    )
    actual_status = _map_docker_status(docker_status)
    if sandbox.status != actual_status:
        logger.info(
            "同步沙盒状态: %s, 数据库=%s, 实际=%s",
            sandbox.id,
            sandbox.status,
            actual_status,
        )
        sandbox.status = actual_status
        await session.commit()


# --- API 端点 ---


@router.post("", response_model=SandboxDetail, summary="创建沙盒")
async def create_sandbox(
    request: CreateSandboxRequest,
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
    template_service: TemplateService = Depends(get_template_service),
) -> SandboxDetail:
    """创建沙盒，支持从模板或直接指定镜像创建

    - template_name: 从已构建的模板创建
    - image: 直接指定 Docker 镜像创建
    - 两者二选一，优先使用 template_name

    从模板创建时，会自动执行模板定义的启动命令。
    如果模板定义了就绪检查，等待就绪后才标记为可用。
    """
    template = None
    image = None
    entrypoint = None
    env = {}
    connect_type = None

    if request.template_name:
        # 从模板创建
        try:
            template = await template_service.get_template(session, request.template_name)
        except TemplateNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message)

        if template.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"模板 '{template.name}' 状态为 '{template.status}'，请先构建模板",
            )

        image = template.docker_image
        entrypoint = template.get_entrypoint() or None
        env = template.get_env()
        connect_type = template.connect_type

    elif request.image:
        image = request.image
    else:
        raise HTTPException(
            status_code=400,
            detail="必须指定 template_name 或 image",
        )

    # 合并额外环境变量
    if request.env:
        env.update(request.env)

    # 通过 OpenSandbox SDK 创建沙盒
    try:
        sandbox = await sandbox_service.create_sandbox(
            image=image,
            entrypoint=entrypoint,
            env=env if env else None,
        )
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    # 记录到数据库
    sandbox_record = ActiveSandbox(
        id=sandbox.id,
        template_id=template.id if template else None,
        name=request.name,
        status="running",
        image=image,
        docker_container_name=f"sandbox-{sandbox.id}",
    )
    session.add(sandbox_record)
    await session.commit()

    # 创建后自动执行模板的启动命令（如果 entrypoint 不是默认的 tail -f /dev/null）
    # 注意: entrypoint 已在容器创建时通过 OpenSandbox SDK 设置，无需额外执行。
    # 如果模板定义了 ready_check（目前 YAML 中未定义此字段），可在此处检查。

    return SandboxDetail(
        id=sandbox_record.id,
        name=sandbox_record.name,
        template_name=template.name if template else None,
        template_id=template.id if template else None,
        status=sandbox_record.status,
        image=sandbox_record.image,
        created_at=sandbox_record.created_at,
        connect_type=connect_type,
        docker_container_name=sandbox_record.docker_container_name,
    )


@router.get("", response_model=list[SandboxListItem], summary="沙盒列表")
async def list_sandboxes(
    status: str | None = Query(default=None, description="按状态筛选: running | paused | stopped"),
    session: AsyncSession = Depends(get_db),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
) -> list[SandboxListItem]:
    """获取所有活跃沙盒，支持按状态筛选

    会同步检查 Docker 容器的实际状态，确保数据库与实际状态一致。
    """
    # TODO: 优化 N+1 查询问题 -- 目前对每个沙盒单独查询模板和 Docker 状态。
    # 后续可用 joinedload 批量加载模板，用一次 docker ps 批量获取容器状态。
    # MVP 阶段沙盒数量通常 < 20，性能影响有限。
    query = select(ActiveSandbox).order_by(ActiveSandbox.created_at.desc())
    # 先取全部，同步状态后再做筛选
    result = await session.execute(query)
    sandboxes = result.scalars().all()

    items = []
    status_updated = False
    for s in sandboxes:
        # 同步 Docker 容器实际状态
        docker_status = await docker_bridge.get_container_status(s.docker_container_name)
        actual_status = _map_docker_status(docker_status)

        if s.status != actual_status:
            logger.info(
                "同步沙盒状态: %s, 数据库=%s, 实际=%s",
                s.id,
                s.status,
                actual_status,
            )
            s.status = actual_status
            status_updated = True

        # 按状态筛选
        if status and s.status != status:
            continue

        # 获取关联模板的连接类型
        connect_type = None
        template_name = None
        if s.template_id:
            t_result = await session.execute(
                select(Template).where(Template.id == s.template_id)
            )
            t = t_result.scalar_one_or_none()
            if t:
                connect_type = t.connect_type
                template_name = t.name

        items.append(
            SandboxListItem(
                id=s.id,
                name=s.name,
                template_name=template_name,
                status=s.status,
                image=s.image,
                created_at=s.created_at,
                connect_type=connect_type,
                docker_container_name=s.docker_container_name,
            )
        )

    if status_updated:
        await session.commit()

    return items


@router.get("/{sandbox_id}", response_model=SandboxDetail, summary="沙盒详情")
async def get_sandbox(
    sandbox_id: str,
    session: AsyncSession = Depends(get_db),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
) -> SandboxDetail:
    """获取指定沙盒的详情，同步容器实际状态"""
    sandbox = await _get_sandbox_or_404(session, sandbox_id)

    # 同步容器实际状态
    await _sync_sandbox_status(session, sandbox, docker_bridge)

    # 获取关联模板信息
    template = await _get_template_for_sandbox(session, sandbox)
    connect_type = template.connect_type if template else None
    template_name = template.name if template else None

    return SandboxDetail(
        id=sandbox.id,
        name=sandbox.name,
        template_name=template_name,
        template_id=sandbox.template_id,
        status=sandbox.status,
        image=sandbox.image,
        created_at=sandbox.created_at,
        connect_type=connect_type,
        docker_container_name=sandbox.docker_container_name,
    )


@router.get(
    "/{sandbox_id}/connect-info",
    response_model=ConnectInfo,
    summary="获取连接信息",
)
async def get_connect_info(
    sandbox_id: str,
    session: AsyncSession = Depends(get_db),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
    connector_service: ConnectorService = Depends(get_connector_service),
) -> ConnectInfo:
    """获取沙盒的自适应连接信息

    根据模板的 connect_type 返回不同的连接信息:
    - shell: 返回 docker exec 命令
    - url: 返回访问 URL
    - port: 返回端口映射列表

    连接前检查沙盒状态，未运行时给出提示。
    """
    sandbox = await _get_sandbox_or_404(session, sandbox_id)

    # 同步容器实际状态
    await _sync_sandbox_status(session, sandbox, docker_bridge)

    # 获取关联模板信息
    template = await _get_template_for_sandbox(session, sandbox)

    connect_type = "shell"
    connect_port = None
    ports = {}

    if template:
        connect_type = template.connect_type
        connect_port = template.connect_port
        ports = template.get_ports()

    # 检查沙盒状态
    if sandbox.status == "paused":
        raise HTTPException(
            status_code=409,
            detail="沙盒已暂停，请先恢复沙盒: POST /api/v1/sandboxes/{id}/resume",
        )

    if sandbox.status == "stopped":
        raise HTTPException(
            status_code=409,
            detail="沙盒已停止，无法连接",
        )

    # 沙盒正在运行，获取连接信息
    info = await connector_service.get_connect_info(
        sandbox_id=sandbox.id,
        sandbox_status=sandbox.status,
        connect_type=connect_type,
        connect_port=connect_port,
        ports=ports,
        docker_container_name=sandbox.docker_container_name,
    )

    return ConnectInfo(
        connect_type=info.get("connect_type", connect_type),
        sandbox_id=sandbox.id,
        container_name=info.get("container_name", sandbox.docker_container_name),
        status=sandbox.status,
        command=info.get("command"),
        url=info.get("url"),
        port=info.get("port"),
        ports=info.get("ports"),
    )


@router.post(
    "/{sandbox_id}/pause",
    response_model=ApiResponse,
    summary="暂停沙盒",
)
async def pause_sandbox(
    sandbox_id: str,
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
) -> ApiResponse:
    """暂停沙盒（cgroup freeze），暂停后不消耗 CPU

    只有 running 状态的沙盒可以暂停。
    """
    sandbox = await _get_sandbox_or_404(session, sandbox_id)

    # 先同步 Docker 容器实际状态，避免基于过时数据库状态判断
    await _sync_sandbox_status(session, sandbox, docker_bridge)

    if sandbox.status == "paused":
        raise SandboxStateError(
            sandbox_id=sandbox_id,
            current_state="paused",
            expected_states=["running"],
        )

    if sandbox.status != "running":
        raise SandboxStateError(
            sandbox_id=sandbox_id,
            current_state=sandbox.status,
            expected_states=["running"],
        )

    try:
        await sandbox_service.pause_sandbox(sandbox_id)
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    # 更新数据库状态
    sandbox.status = "paused"
    await session.commit()

    return ApiResponse(success=True, message=f"沙盒 '{sandbox_id}' 已暂停")


@router.post(
    "/{sandbox_id}/resume",
    response_model=ApiResponse,
    summary="恢复沙盒",
)
async def resume_sandbox(
    sandbox_id: str,
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
    docker_bridge: DockerBridge = Depends(get_docker_bridge),
) -> ApiResponse:
    """恢复已暂停的沙盒，恢复后环境与暂停前一致

    只有 paused 状态的沙盒可以恢复。
    """
    sandbox = await _get_sandbox_or_404(session, sandbox_id)

    # 先同步 Docker 容器实际状态，避免基于过时数据库状态判断
    await _sync_sandbox_status(session, sandbox, docker_bridge)

    if sandbox.status == "running":
        raise SandboxStateError(
            sandbox_id=sandbox_id,
            current_state="running",
            expected_states=["paused"],
        )

    if sandbox.status != "paused":
        raise SandboxStateError(
            sandbox_id=sandbox_id,
            current_state=sandbox.status,
            expected_states=["paused"],
        )

    try:
        await sandbox_service.resume_sandbox(sandbox_id)
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    # 更新数据库状态
    sandbox.status = "running"
    await session.commit()

    return ApiResponse(success=True, message=f"沙盒 '{sandbox_id}' 已恢复运行")


@router.delete("", response_model=BatchDeleteResponse, summary="批量销毁沙盒")
async def delete_all_sandboxes(
    all: bool = Query(
        default=False, description="必须为 true 才会执行批量销毁"
    ),
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
) -> BatchDeleteResponse:
    """批量销毁所有沙盒

    必须显式传入 all=true 以确认批量操作。
    销毁前如果沙盒仍在运行，直接 kill。
    """
    if not all:
        raise HTTPException(
            status_code=400,
            detail="批量销毁需要显式指定 all=true",
        )

    result = await session.execute(select(ActiveSandbox))
    sandboxes = list(result.scalars().all())

    total = len(sandboxes)
    deleted = 0
    failed = 0

    for s in sandboxes:
        try:
            await sandbox_service.kill_sandbox_by_id(s.id)
            await session.delete(s)
            deleted += 1
        except Exception:
            logger.warning("批量销毁沙盒失败: %s", s.id, exc_info=True)
            # 即使 kill 失败也从数据库删除记录（容器可能已不存在）
            await session.delete(s)
            failed += 1

    await session.commit()

    return BatchDeleteResponse(
        success=True,
        total=total,
        deleted=deleted,
        failed=failed,
        message=f"已销毁 {deleted}/{total} 个沙盒",
    )


@router.delete("/{sandbox_id}", response_model=ApiResponse, summary="销毁沙盒")
async def delete_sandbox(
    sandbox_id: str,
    session: AsyncSession = Depends(get_db),
    sandbox_service: SandboxService = Depends(get_sandbox_service),
) -> ApiResponse:
    """销毁指定沙盒，移除 Docker 容器并清理数据库记录

    如果沙盒仍在运行（或暂停），直接 kill。
    """
    sandbox = await _get_sandbox_or_404(session, sandbox_id)

    # 通过 OpenSandbox SDK 销毁（无论状态都 kill）
    try:
        await sandbox_service.kill_sandbox_by_id(sandbox_id)
    except Exception:
        logger.warning("销毁沙盒失败: %s", sandbox_id, exc_info=True)

    # 从数据库移除（即使 kill 失败也清理记录，容器可能已不存在）
    await session.delete(sandbox)
    await session.commit()

    return ApiResponse(success=True, message=f"沙盒 '{sandbox_id}' 已销毁")


@router.post(
    "/{sandbox_id}/save-template",
    response_model=ApiResponse,
    summary="快照为模板",
)
async def save_as_template(
    sandbox_id: str,
    request: SaveTemplateRequest,
    session: AsyncSession = Depends(get_db),
    template_service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """将运行中的沙盒快照保存为新模板

    快照时会自动暂停容器保证文件系统一致性，完成后自动恢复。
    新模板默认继承原模板的连接类型和启动命令（可覆盖）。
    """
    try:
        template = await template_service.save_sandbox_as_template(
            session=session,
            sandbox_id=sandbox_id,
            name=request.name,
            description=request.description,
            connect_type=request.connect_type,
            entrypoint=request.entrypoint,
        )
    except SandboxNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except TemplateAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except SandboxManagerError as e:
        raise HTTPException(status_code=500, detail=e.message)

    size_mb = (template.size_bytes or 0) / (1024 * 1024)
    return ApiResponse(
        success=True,
        message=f"快照保存成功: 模板 '{template.name}'，镜像大小 {size_mb:.1f} MB",
        data={"template_name": template.name, "size_bytes": template.size_bytes},
    )
