"""WebSocket 终端 - 桥接浏览器 xterm.js 与 docker exec

通过 WebSocket 接收前端 xterm.js 的输入，转发到 docker exec 启动的
bash 进程，同时将进程输出回传到前端。

使用 Docker SDK 的 exec_create + exec_start (tty=True, socket=True)
获得真正的 PTY，从而支持输入回显、PS1 提示符、行编辑等交互功能。
"""

import asyncio
import logging

import docker
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["终端"])
logger = logging.getLogger(__name__)


@router.websocket("/sandboxes/{sandbox_id}/terminal")
async def terminal_ws(websocket: WebSocket, sandbox_id: str) -> None:
    """WebSocket 终端端点

    连接后通过 Docker SDK 创建带 PTY 的 exec 实例，
    双向转发 WebSocket <-> 容器终端。
    """
    await websocket.accept()
    container_name = f"sandbox-{sandbox_id}"

    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        await websocket.send_text(f"\r\n容器 {container_name} 不存在\r\n")
        await websocket.close()
        return
    except Exception as e:
        await websocket.send_text(f"\r\n连接 Docker 失败: {e}\r\n")
        await websocket.close()
        return

    # 尝试 bash，失败回退 sh
    exec_id: str | None = None
    for shell in ["/bin/bash", "/bin/sh"]:
        try:
            exec_instance = client.api.exec_create(
                container.id,
                cmd=shell,
                stdin=True,
                tty=True,
                stderr=True,
                stdout=True,
            )
            exec_id = exec_instance["Id"]
            break
        except Exception:
            logger.debug("尝试 %s 失败，将回退", shell)
            continue

    if exec_id is None:
        await websocket.send_text("\r\n无法在容器中启动 shell\r\n")
        await websocket.close()
        return

    # 启动 exec (socket 模式，获取底层 socket 进行双向通信)
    try:
        sock = client.api.exec_start(exec_id, tty=True, socket=True, demux=False)
    except Exception as e:
        await websocket.send_text(f"\r\n启动终端失败: {e}\r\n")
        await websocket.close()
        return

    # 获取底层 socket
    raw_sock = sock._sock  # noqa: SLF001
    raw_sock.setblocking(False)

    logger.info(
        "终端已连接: sandbox=%s, container=%s, exec=%s",
        sandbox_id,
        container_name,
        exec_id,
    )

    loop = asyncio.get_event_loop()

    async def _read_from_container() -> None:
        """从容器 socket 读取输出并发送到 WebSocket"""
        try:
            while True:
                try:
                    data = await loop.run_in_executor(None, raw_sock.recv, 4096)
                except BlockingIOError:
                    await asyncio.sleep(0.01)
                    continue
                except OSError:
                    break
                if not data:
                    break
                await websocket.send_bytes(data)
        except (WebSocketDisconnect, ConnectionError):
            pass
        except Exception:
            logger.debug("读取容器输出异常", exc_info=True)

    async def _read_from_websocket() -> None:
        """从 WebSocket 读取输入并写入容器 socket"""
        try:
            while True:
                try:
                    data = await websocket.receive_bytes()
                except WebSocketDisconnect:
                    break
                try:
                    await loop.run_in_executor(None, raw_sock.sendall, data)
                except OSError:
                    break
        except (WebSocketDisconnect, ConnectionError):
            pass
        except Exception:
            logger.debug("读取 WebSocket 输入异常", exc_info=True)

    # 并行运行输入和输出任务
    read_task = asyncio.create_task(_read_from_container())
    write_task = asyncio.create_task(_read_from_websocket())

    try:
        done, pending = await asyncio.wait(
            [read_task, write_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        try:
            raw_sock.close()
        except Exception:
            pass

        try:
            await websocket.close()
        except Exception:
            pass

        logger.info("终端已断开: sandbox=%s", sandbox_id)
