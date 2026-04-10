"""沙盒服务反向代理 - 将请求转发到沙盒容器内的服务

解决 OpenSandbox 代理模式下 code-server 等 Web 应用的兼容性问题。
浏览器通过 /proxy/{sandbox_id}/{port}/ 访问沙盒内的 Web 服务。
"""

import logging

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from sandbox_manager.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_sandbox_service() -> SandboxService:
    from sandbox_manager.dependencies import get_sandbox_service

    return get_sandbox_service()


async def _get_sandbox_ip(sandbox_id: str) -> str | None:
    """通过 Docker API 获取沙盒容器的内部 IP"""
    import docker

    client = docker.from_env()
    try:
        container = client.containers.get(f"sandbox-{sandbox_id}")
        networks = container.attrs["NetworkSettings"]["Networks"]
        for net_name, net_info in networks.items():
            if net_info.get("IPAddress"):
                return net_info["IPAddress"]
    except Exception as e:
        logger.error("获取沙盒 IP 失败: %s, error: %s", sandbox_id, e)
    finally:
        client.close()
    return None


@router.api_route(
    "/proxy/{sandbox_id}/{port}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_to_sandbox(sandbox_id: str, port: int, path: str, request: Request):
    """HTTP 反向代理到沙盒容器"""
    ip = await _get_sandbox_ip(sandbox_id)
    if not ip:
        return Response(content="Sandbox not found or not running", status_code=404)

    target_url = f"http://{ip}:{port}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False,
            )
            response_headers = dict(resp.headers)
            response_headers.pop("transfer-encoding", None)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers,
            )
        except Exception as e:
            logger.error("代理请求失败: %s -> %s, error: %s", request.url, target_url, e)
            return Response(content=f"Proxy error: {e}", status_code=502)


@router.websocket("/proxy/{sandbox_id}/{port}/{path:path}")
async def proxy_ws_to_sandbox(websocket: WebSocket, sandbox_id: str, port: int, path: str):
    """WebSocket 反向代理到沙盒容器"""
    ip = await _get_sandbox_ip(sandbox_id)
    if not ip:
        await websocket.close(code=4004, reason="Sandbox not found")
        return

    target_url = f"ws://{ip}:{port}/{path}"
    query = str(websocket.url.query) if websocket.url.query else ""
    if query:
        target_url += f"?{query}"

    await websocket.accept()

    import asyncio
    import websockets

    try:
        async with websockets.connect(target_url) as ws_target:

            async def client_to_target():
                try:
                    while True:
                        data = await websocket.receive()
                        if "text" in data:
                            await ws_target.send(data["text"])
                        elif "bytes" in data:
                            await ws_target.send(data["bytes"])
                except WebSocketDisconnect:
                    pass

            async def target_to_client():
                try:
                    async for msg in ws_target:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            await websocket.send_bytes(msg)
                except Exception:
                    pass

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_target()),
                    asyncio.create_task(target_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        logger.error("WebSocket 代理失败: %s, error: %s", target_url, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
