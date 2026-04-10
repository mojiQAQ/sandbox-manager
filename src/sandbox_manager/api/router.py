"""API 路由注册 - 汇总所有子路由"""

from fastapi import APIRouter

from sandbox_manager.api import health, sandboxes, templates, ws_terminal

api_router = APIRouter(prefix="/api/v1")

# 注册子路由
api_router.include_router(health.router)
api_router.include_router(templates.router)
api_router.include_router(sandboxes.router)
api_router.include_router(ws_terminal.router)
