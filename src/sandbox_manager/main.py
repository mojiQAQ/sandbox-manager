"""FastAPI 应用入口 - lifespan 管理 + 全局异常处理"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sandbox_manager import __version__
from sandbox_manager.api.router import api_router
from sandbox_manager.config import settings
from sandbox_manager.db.engine import close_db, init_db
from sandbox_manager.dependencies import (
    get_docker_bridge,
    get_sandbox_service,
    get_template_service,
)
from sandbox_manager.exceptions import (
    NotFoundError,
    SandboxManagerError,
    SandboxStateError,
    TemplateAlreadyExistsError,
    TemplateBuildInProgressError,
    TemplateNotReadyError,
)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时:
    1. 初始化数据库（创建表结构）
    2. 检查 OpenSandbox 连接
    3. 注册内置模板
    4. 检查 Docker Engine

    关闭时:
    1. 关闭数据库连接
    """
    logger.info("=" * 60)
    logger.info("Sandbox Manager v%s 启动中...", __version__)
    logger.info("=" * 60)

    # 1. 初始化数据库
    logger.info("正在初始化数据库...")
    await init_db()

    # 2. 检查 Docker Engine
    docker_bridge = get_docker_bridge()
    docker_ok = await docker_bridge.check_docker()
    if docker_ok:
        logger.info("Docker Engine 连接正常")
    else:
        logger.warning("Docker Engine 不可达，部分功能将不可用")

    # 3. 检查 OpenSandbox 连接
    sandbox_service = get_sandbox_service()
    opensandbox_ok = await sandbox_service.check_connection()
    if opensandbox_ok:
        logger.info("OpenSandbox server 连接正常: %s", settings.opensandbox_url)
    else:
        logger.warning(
            "OpenSandbox server 不可达: %s，沙盒相关操作将不可用",
            settings.opensandbox_url,
        )

    # 4. 清理异常构建状态 + 注册内置模板
    template_service = get_template_service(sandbox_service, docker_bridge)
    from sandbox_manager.db.engine import _get_session_factory

    session_factory = _get_session_factory()
    async with session_factory() as session:
        stale = await template_service.cleanup_stale_builds(session)
        if stale > 0:
            logger.warning("已清理 %d 个异常构建状态的模板", stale)

        count = await template_service.register_builtin_templates(session)
        if count > 0:
            logger.info("新注册 %d 个内置模板", count)

    logger.info("=" * 60)
    logger.info("Sandbox Manager 已就绪: http://%s:%s", settings.host, settings.port)
    logger.info("API 文档: http://%s:%s/docs", settings.host, settings.port)
    logger.info("=" * 60)

    yield  # 应用运行中

    # 关闭
    logger.info("Sandbox Manager 正在关闭...")
    await close_db()
    logger.info("Sandbox Manager 已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="Sandbox Manager",
    description="一条命令，秒级进入预装好开发工具的隔离环境",
    version=__version__,
    lifespan=lifespan,
)

# CORS 中间件（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)

# --- 前端静态文件服务 ---
# 生产环境：前端构建产物放在 /app/static 目录
_static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="static-assets")

    @app.get("/")
    async def serve_index():
        """根路径返回 index.html"""
        return FileResponse(_static_dir / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback：非 API 路由都返回 index.html"""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")


# --- 全局异常处理 ---


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(TemplateNotReadyError)
async def template_not_ready_handler(
    request: Request, exc: TemplateNotReadyError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(TemplateAlreadyExistsError)
async def template_exists_handler(
    request: Request, exc: TemplateAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(TemplateBuildInProgressError)
async def build_in_progress_handler(
    request: Request, exc: TemplateBuildInProgressError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(SandboxStateError)
async def sandbox_state_handler(
    request: Request, exc: SandboxStateError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(SandboxManagerError)
async def general_error_handler(
    request: Request, exc: SandboxManagerError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """统一 HTTPException 响应格式，与自定义异常处理器保持一致"""
    detail_str = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": detail_str,
            "detail": detail_str,
        },
    )
