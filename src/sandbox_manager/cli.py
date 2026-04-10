"""Sandbox Manager CLI - Typer + Rich

所有命令通过 httpx 调用本地 FastAPI 服务 REST API，不直接调用 service 层。

命令总览:
  sbx start <template>              # 一键创建+连接
  sbx list                          # 列出所有沙盒
  sbx connect <sandbox-id>          # 连接到已有沙盒
  sbx stop <sandbox-id|--all>       # 停止沙盒
  sbx rm <sandbox-id|--all>         # 销毁沙盒
  sbx pause <sandbox-id>            # 暂停沙盒
  sbx resume <sandbox-id>           # 恢复沙盒
  sbx snapshot <id> --name <name>   # 保存沙盒为模板
  sbx template list                 # 列出所有模板
  sbx template build <name|--all>   # 构建模板
  sbx template init <name>          # 生成模板配置脚手架
  sbx template show <name>          # 查看模板详情
  sbx template rm <name>            # 删除模板
  sbx status                        # 系统状态
  sbx config show                   # 查看配置
  sbx config set <key> <value>      # 修改配置
  sbx version                       # 版本信息
"""

from __future__ import annotations

import json
import os
import time
import webbrowser
from contextlib import nullcontext
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sandbox_manager import __version__

# ---------------------------------------------------------------------------
# App & sub-command groups
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="sbx",
    help="Sandbox Manager CLI - 一条命令，秒级进入预装好开发工具的隔离环境",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

template_app = typer.Typer(
    name="template",
    help="模板管理命令组",
    no_args_is_help=True,
)
app.add_typer(template_app, name="template")

config_app = typer.Typer(
    name="config",
    help="配置管理命令组",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

console = Console()
error_console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

DEFAULT_API_BASE = "http://localhost:9000/api/v1"
CONFIG_DIR = Path.home() / ".sandbox-manager"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Timeout for regular API calls (seconds)
API_TIMEOUT = 10.0
# Timeout for long-running operations (build, etc.)
API_LONG_TIMEOUT = 300.0


def _get_api_base() -> str:
    """Read API base URL from config or env."""
    env_val = os.environ.get("SBX_API_URL")
    if env_val:
        return env_val.rstrip("/")

    if CONFIG_FILE.exists():
        try:
            import yaml

            with open(CONFIG_FILE) as f:
                cfg = yaml.safe_load(f) or {}
            url = cfg.get("api_url")
            if url:
                return url.rstrip("/")
        except Exception:
            pass

    return DEFAULT_API_BASE


def _client() -> httpx.Client:
    """Create a short-lived httpx client."""
    return httpx.Client(base_url=_get_api_base(), timeout=API_TIMEOUT)


def _handle_api_error(resp: httpx.Response) -> None:
    """Raise a clean error for non-2xx responses."""
    if resp.is_success:
        return
    try:
        body = resp.json()
        msg = body.get("message") or body.get("detail") or resp.text
    except Exception:
        msg = resp.text or f"HTTP {resp.status_code}"

    # 对 409 (Conflict) 做 CLI 友好化处理: 替换 API 路径为 CLI 命令
    if resp.status_code == 409 and msg and "暂停" in msg:
        msg = "沙盒已暂停，请先执行: sbx resume <id>"

    error_console.print(f"[bold red]错误:[/bold red] {msg}")
    raise typer.Exit(1)


def _api_get(path: str, *, params: dict | None = None, timeout: float = API_TIMEOUT) -> dict:
    """GET helper with connection-error handling."""
    try:
        with httpx.Client(base_url=_get_api_base(), timeout=timeout) as c:
            resp = c.get(path, params=params)
    except httpx.ConnectError:
        _print_api_unreachable()
        raise typer.Exit(1)
    except httpx.TimeoutException:
        _print_timeout_error()
        raise typer.Exit(1)
    _handle_api_error(resp)
    return resp.json()


def _api_post(
    path: str,
    *,
    json_body: dict | None = None,
    timeout: float = API_TIMEOUT,
) -> dict:
    """POST helper."""
    try:
        with httpx.Client(base_url=_get_api_base(), timeout=timeout) as c:
            resp = c.post(path, json=json_body)
    except httpx.ConnectError:
        _print_api_unreachable()
        raise typer.Exit(1)
    except httpx.TimeoutException:
        _print_timeout_error()
        raise typer.Exit(1)
    _handle_api_error(resp)
    return resp.json()


def _api_delete(path: str, *, params: dict | None = None, timeout: float = API_TIMEOUT) -> dict:
    """DELETE helper."""
    try:
        with httpx.Client(base_url=_get_api_base(), timeout=timeout) as c:
            resp = c.delete(path, params=params)
    except httpx.ConnectError:
        _print_api_unreachable()
        raise typer.Exit(1)
    except httpx.TimeoutException:
        _print_timeout_error()
        raise typer.Exit(1)
    _handle_api_error(resp)
    return resp.json()


def _print_api_unreachable() -> None:
    """Print a user-friendly message when the API is unreachable."""
    api_base = _get_api_base()
    error_console.print(
        Panel(
            f"[bold red]无法连接到 Sandbox Manager API 服务[/bold red]\n\n"
            f"  地址: {api_base}\n\n"
            f"请确认:\n"
            f"  1. API 服务已启动 (docker-compose up)\n"
            f"  2. 服务地址配置正确 (当前: {api_base})\n"
            f"  3. 可通过 SBX_API_URL 环境变量或 ~/.sandbox-manager/config.yaml 修改地址",
            title="连接失败",
            border_style="red",
        )
    )


def _print_timeout_error() -> None:
    """Print a user-friendly message when an API request times out."""
    error_console.print(
        Panel(
            "[bold red]请求超时[/bold red]\n\n"
            "API 服务未能在预期时间内响应，请稍后重试。\n\n"
            "可能的原因:\n"
            "  1. API 服务负载过高\n"
            "  2. 操作涉及大量容器，耗时较长\n"
            "  3. 网络连接不稳定",
            title="请求超时",
            border_style="yellow",
        )
    )


def _print_json(data: object) -> None:
    """Print data as formatted JSON to stdout (no Rich markup processing)."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _resolve_sandbox_id(prefix: str) -> str:
    """Resolve a sandbox ID by prefix match.

    If the prefix matches exactly one sandbox, return its full ID.
    If multiple match, print them and exit.
    If none match, print error and exit.
    """
    sandboxes = _api_get("/sandboxes")
    matches = [s for s in sandboxes if s["id"].startswith(prefix)]

    if len(matches) == 1:
        return matches[0]["id"]

    if len(matches) == 0:
        error_console.print(f"[bold red]错误:[/bold red] 找不到 ID 以 '{prefix}' 开头的沙盒")
        if sandboxes:
            error_console.print("\n可用沙盒:")
            for s in sandboxes:
                error_console.print(f"  {s['id'][:12]}  {s.get('template_name') or '-'}")
        raise typer.Exit(1)

    # Multiple matches
    error_console.print(
        f"[bold yellow]警告:[/bold yellow] 前缀 '{prefix}' 匹配到多个沙盒，请输入更多字符:"
    )
    for s in matches:
        error_console.print(f"  {s['id'][:12]}  {s.get('template_name') or '-'}")
    raise typer.Exit(1)


def _status_style(status: str) -> str:
    """Return rich color tag for a status string."""
    return {
        "running": "green",
        "paused": "yellow",
        "stopped": "red",
        "ready": "green",
        "building": "yellow",
        "unbuilt": "dim",
        "failed": "red",
    }.get(status, "")


def _adaptive_connect(connect_info: dict) -> None:
    """Execute adaptive connection based on connect_type.

    - shell: os.execvp into docker exec -it
    - url: webbrowser.open + print URL
    - port: print port mappings
    """
    ctype = connect_info.get("connect_type", "shell")
    container = connect_info.get("container_name", "")

    if ctype == "shell":
        console.print(f"[green]正在连接到沙盒...[/green] (容器: {container})")
        console.print("[dim]退出 shell 后沙盒继续运行，使用 sbx stop 停止[/dim]\n")
        # Replace current process with docker exec
        os.execvp("docker", ["docker", "exec", "-it", container, "/bin/bash"])

    elif ctype == "url":
        url = connect_info.get("url")
        if url:
            console.print("[green]正在打开浏览器...[/green]")
            console.print(f"  URL: [bold cyan]{url}[/bold cyan]")
            webbrowser.open(url)
        else:
            console.print("[yellow]未获取到访问 URL[/yellow]")

        # Also print port info if available
        ports = connect_info.get("ports")
        if ports:
            console.print("\n端口映射:")
            for p in ports:
                console.print(f"  {p.get('name', '-')}: {p.get('url', '-')}")

    elif ctype == "port":
        ports = connect_info.get("ports", [])
        if ports:
            table = Table(title="端口映射")
            table.add_column("名称", style="cyan")
            table.add_column("容器端口", justify="right")
            table.add_column("访问地址", style="green")
            for p in ports:
                table.add_row(
                    str(p.get("name", "-")),
                    str(p.get("container_port", "-")),
                    p.get("url", "-"),
                )
            console.print(table)
        else:
            console.print("[yellow]未获取到端口映射信息[/yellow]")

    else:
        console.print(f"[yellow]未知的连接类型: {ctype}，尝试 shell 连接...[/yellow]")
        os.execvp("docker", ["docker", "exec", "-it", container, "/bin/bash"])


# ===========================================================================
# 功能 #15: sbx start <template-name>
# ===========================================================================


@app.command(help="一键创建沙盒并连接 (核心命令)")
def start(
    template_name: str = typer.Argument(help="模板名称，如 claude-code, python-dev"),
    name: str | None = typer.Option(None, "--name", "-n", help="沙盒自定义名称"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """从模板一键创建沙盒并自适应连接。

    例: sbx start claude-code
    """
    # 1. Check template exists and is ready
    try:
        template = _api_get(f"/templates/{template_name}")
    except typer.Exit:
        # _api_get already printed the error, but let's check if it's a 404
        # and suggest available templates
        try:
            templates = _api_get("/templates")
            available = [t["name"] for t in templates]
            error_console.print(f"\n可用模板: {', '.join(available)}")
        except Exception:
            pass
        raise

    if template["status"] == "unbuilt":
        error_console.print(
            f"[bold yellow]模板 '{template_name}' 尚未构建[/bold yellow]\n\n"
            f"请先执行构建:\n"
            f"  [cyan]sbx template build {template_name}[/cyan]\n\n"
            f"或构建所有内置模板:\n"
            f"  [cyan]sbx template build --all[/cyan]"
        )
        raise typer.Exit(1)

    if template["status"] == "building":
        error_console.print(
            f"[bold yellow]模板 '{template_name}' 正在构建中[/bold yellow]\n\n"
            f"请等待构建完成:\n"
            f"  [cyan]sbx template build {template_name}[/cyan]  (查看进度)"
        )
        raise typer.Exit(1)

    if template["status"] == "failed":
        error_console.print(
            f"[bold red]模板 '{template_name}' 构建失败[/bold red]\n\n"
            f"请重新构建:\n"
            f"  [cyan]sbx template build {template_name}[/cyan]"
        )
        raise typer.Exit(1)

    # 2. Create sandbox
    if not json_output:
        status_ctx = console.status("[bold green]正在创建沙盒...")
    else:
        status_ctx = nullcontext()

    with status_ctx:
        t0 = time.monotonic()
        body: dict = {"template_name": template_name}
        if name:
            body["name"] = name
        sandbox = _api_post("/sandboxes", json_body=body)
        elapsed_create = time.monotonic() - t0

    sandbox_id = sandbox["id"]
    if not json_output:
        console.print(
            f"[green]沙盒已创建[/green]  ID: [cyan]{sandbox_id[:12]}[/cyan]  "
            f"({elapsed_create:.1f}s)"
        )

    # 3. Get connect info
    if not json_output:
        status_ctx2 = console.status("[bold green]正在获取连接信息...")
    else:
        status_ctx2 = nullcontext()

    with status_ctx2:
        connect_info = _api_get(f"/sandboxes/{sandbox_id}/connect-info")

    if json_output:
        _print_json({"sandbox": sandbox, "connect_info": connect_info})
        return

    # 4. Adaptive connect
    _adaptive_connect(connect_info)


# ===========================================================================
# 功能 #16: 沙盒管理命令组
# ===========================================================================


@app.command("list", help="列出所有沙盒")
def list_sandboxes(
    status: str | None = typer.Option(
        None, "--status", "-s", help="按状态筛选: running | paused | stopped"
    ),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """列出所有沙盒，表格展示。"""
    params = {}
    if status:
        params["status"] = status

    sandboxes = _api_get("/sandboxes", params=params)

    if json_output:
        _print_json(sandboxes)
        return

    if not sandboxes:
        console.print("[dim]当前没有沙盒[/dim]")
        return

    table = Table(title="沙盒列表")
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("名称", style="green")
    table.add_column("模板", style="yellow")
    table.add_column("状态", style="bold")
    table.add_column("连接方式")
    table.add_column("创建时间")

    for s in sandboxes:
        st = _status_style(s["status"])
        table.add_row(
            s["id"][:12],
            s.get("name") or "-",
            s.get("template_name") or "-",
            f"[{st}]{s['status']}[/{st}]" if st else s["status"],
            s.get("connect_type") or "-",
            s["created_at"][:19],
        )

    console.print(table)


@app.command(help="连接到已有沙盒")
def connect(
    sandbox_id: str = typer.Argument(help="沙盒 ID（支持前缀匹配）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """连接到已有沙盒，自适应选择连接方式。"""
    full_id = _resolve_sandbox_id(sandbox_id)
    connect_info = _api_get(f"/sandboxes/{full_id}/connect-info")

    if json_output:
        _print_json(connect_info)
        return

    _adaptive_connect(connect_info)


@app.command(help="停止沙盒 (停止并释放资源，等价于 rm)")
def stop(
    sandbox_id: str | None = typer.Argument(None, help="沙盒 ID（支持前缀匹配）"),
    all_sandboxes: bool = typer.Option(False, "--all", help="停止所有沙盒"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """停止指定沙盒或所有沙盒。

    OpenSandbox 沙盒是临时环境，stop 会停止并释放资源。
    如需保留沙盒状态，请使用 sbx pause。
    """
    if all_sandboxes:
        result = _api_delete(
            "/sandboxes", params={"all": "true"}, timeout=API_LONG_TIMEOUT
        )
        if json_output:
            _print_json(result)
        else:
            count = result.get("deleted", "")
            total = result.get("total", "")
            if count and total:
                console.print(f"[green]已停止 {count}/{total} 个沙盒[/green]")
            else:
                console.print("[green]已停止所有沙盒[/green]")
        return

    if sandbox_id is None:
        error_console.print("[bold red]错误:[/bold red] 请指定沙盒 ID 或使用 --all")
        raise typer.Exit(1)

    full_id = _resolve_sandbox_id(sandbox_id)
    result = _api_delete(f"/sandboxes/{full_id}")
    if json_output:
        _print_json(result)
    else:
        console.print(f"[green]沙盒 {full_id[:12]} 已停止[/green]")


@app.command(help="销毁沙盒 (停止并永久移除)")
def rm(
    sandbox_id: str | None = typer.Argument(None, help="沙盒 ID（支持前缀匹配）"),
    all_sandboxes: bool = typer.Option(False, "--all", help="销毁所有沙盒"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """销毁指定沙盒或所有沙盒，停止并永久移除。"""
    if all_sandboxes:
        result = _api_delete(
            "/sandboxes", params={"all": "true"}, timeout=API_LONG_TIMEOUT
        )
        if json_output:
            _print_json(result)
        else:
            count = result.get("deleted", "")
            total = result.get("total", "")
            if count and total:
                console.print(f"[green]已销毁 {count}/{total} 个沙盒[/green]")
            else:
                console.print("[green]已销毁所有沙盒[/green]")
        return

    if sandbox_id is None:
        error_console.print("[bold red]错误:[/bold red] 请指定沙盒 ID 或使用 --all")
        raise typer.Exit(1)

    full_id = _resolve_sandbox_id(sandbox_id)
    result = _api_delete(f"/sandboxes/{full_id}")
    if json_output:
        _print_json(result)
    else:
        console.print(f"[green]沙盒 {full_id[:12]} 已销毁[/green]")


@app.command(help="暂停沙盒")
def pause(
    sandbox_id: str = typer.Argument(help="沙盒 ID（支持前缀匹配）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """暂停沙盒（cgroup freeze），不消耗 CPU。"""
    full_id = _resolve_sandbox_id(sandbox_id)
    result = _api_post(f"/sandboxes/{full_id}/pause")
    if json_output:
        _print_json(result)
    else:
        console.print(f"[green]{result.get('message', f'沙盒 {full_id[:12]} 已暂停')}[/green]")


@app.command(help="恢复沙盒")
def resume(
    sandbox_id: str = typer.Argument(help="沙盒 ID（支持前缀匹配）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """恢复已暂停的沙盒。"""
    full_id = _resolve_sandbox_id(sandbox_id)
    result = _api_post(f"/sandboxes/{full_id}/resume")
    if json_output:
        _print_json(result)
    else:
        console.print(
            f"[green]{result.get('message', f'沙盒 {full_id[:12]} 已恢复运行')}[/green]"
        )


# ===========================================================================
# 功能 #17: 模板管理命令组
# ===========================================================================


@template_app.command("list", help="列出所有模板")
def template_list(
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """列出所有模板及状态。"""
    templates = _api_get("/templates")

    if json_output:
        _print_json(templates)
        return

    if not templates:
        console.print("[dim]当前没有模板[/dim]")
        return

    table = Table(title="模板列表")
    table.add_column("名称", style="cyan")
    table.add_column("描述")
    table.add_column("状态", style="bold")
    table.add_column("来源")
    table.add_column("连接方式")
    table.add_column("镜像大小")
    table.add_column("更新时间")

    for t in templates:
        st = _status_style(t["status"])
        size = "-"
        if t.get("size_bytes") and t["size_bytes"] > 0:
            size_mb = t["size_bytes"] / (1024 * 1024)
            size = f"{size_mb:.1f} MB"

        table.add_row(
            t["name"],
            t.get("description") or "-",
            f"[{st}]{t['status']}[/{st}]" if st else t["status"],
            t.get("source") or "-",
            t.get("connect_type") or "-",
            size,
            t["updated_at"][:19] if t.get("updated_at") else "-",
        )

    console.print(table)


@template_app.command("build", help="构建模板")
def template_build(
    name: str | None = typer.Argument(None, help="模板名称"),
    all_templates: bool = typer.Option(False, "--all", help="构建所有未构建的模板"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """构建指定模板或所有未构建的模板。"""
    if all_templates:
        # Get all templates and build unbuilt ones
        templates = _api_get("/templates")
        unbuilt = [t for t in templates if t["status"] in ("unbuilt", "failed")]

        if not unbuilt:
            console.print("[green]所有模板已构建[/green]")
            return

        console.print(f"将构建 {len(unbuilt)} 个模板: {', '.join(t['name'] for t in unbuilt)}\n")

        results = []
        for t in unbuilt:
            tname = t["name"]
            console.print(f"[bold]正在触发构建: {tname}[/bold]")
            try:
                _api_post(f"/templates/{tname}/build")
            except typer.Exit:
                results.append({"name": tname, "success": False, "message": "构建触发失败"})
                continue

            # Poll build status with spinner
            _poll_build_status(tname)
            results.append({"name": tname, "success": True, "message": "构建完成"})

        if json_output:
            _print_json(results)
        return

    if name is None:
        error_console.print("[bold red]错误:[/bold red] 请指定模板名称或使用 --all")
        raise typer.Exit(1)

    # Build single template
    result = _api_post(f"/templates/{name}/build")
    if json_output:
        _print_json(result)
        return

    console.print(f"[green]{result.get('message', f'模板 {name} 构建已启动')}[/green]")

    # Poll build status
    _poll_build_status(name)


def _poll_build_status(name: str, poll_interval: float = 2.0, max_wait: float = 300.0) -> None:
    """Poll template build status with a Rich spinner."""
    t0 = time.monotonic()
    with console.status(f"[bold green]正在构建模板 {name}...") as spinner:
        while True:
            elapsed = time.monotonic() - t0
            if elapsed > max_wait:
                error_console.print(
                    f"[bold yellow]警告:[/bold yellow] 构建超时 ({max_wait:.0f}s)，"
                    f"请手动检查状态: sbx template build {name}"
                )
                return

            try:
                status = _api_get(f"/templates/{name}/build-status")
            except typer.Exit:
                return

            current = status.get("status", "unknown")
            if current == "ready":
                console.print(f"[bold green]模板 {name} 构建成功![/bold green]")
                return
            elif current == "failed":
                err = status.get("build_error") or "未知错误"
                error_console.print(
                    f"[bold red]模板 {name} 构建失败:[/bold red] {err}"
                )
                return
            elif current in ("building", "unbuilt"):
                spinner.update(
                    f"[bold green]正在构建模板 {name}... ({elapsed:.0f}s)"
                )
            else:
                spinner.update(f"[bold green]模板 {name}: {current} ({elapsed:.0f}s)")

            time.sleep(poll_interval)


@template_app.command("init", help="生成模板配置文件脚手架")
def template_init(
    name: str = typer.Argument(help="模板名称"),
    output_dir: str = typer.Option(".", "--dir", "-d", help="输出目录"),
) -> None:
    """生成带注释的模板配置文件脚手架。"""
    scaffold = f"""# Sandbox Manager 模板配置文件
# 模板名称: {name}
#
# 使用方法:
#   1. 编辑此文件，填写构建配置
#   2. 将此文件放到 templates/ 目录下
#   3. 执行 sbx template build {name}

name: {name}
description: "自定义模板 - {name}"

# 基础 Docker 镜像
base_image: "ubuntu:22.04"

# 连接类型: shell | url | port
connect_type: shell

# 连接端口（url/port 类型时使用）
# connect_port: 8080

# 容器启动命令（不填默认为 tail -f /dev/null 保持容器运行）
entrypoint:
  - "tail"
  - "-f"
  - "/dev/null"

# 环境变量
env:
  DEBIAN_FRONTEND: noninteractive

# 端口映射（格式: 名称: 容器端口）
ports: {{}}

# 安装命令列表（按顺序执行）
install_commands:
  - "apt-get update"
  - "apt-get install -y curl wget git"
  # 添加更多安装命令...
"""
    out_path = Path(output_dir) / f"{name}.yaml"
    out_path.write_text(scaffold, encoding="utf-8")
    console.print(f"[green]已生成模板配置文件:[/green] {out_path}")
    console.print(f"编辑后执行: [cyan]sbx template build {name}[/cyan]")


@template_app.command("show", help="查看模板详情")
def template_show(
    name: str = typer.Argument(help="模板名称"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """查看指定模板的详细信息。"""
    template = _api_get(f"/templates/{name}")

    if json_output:
        _print_json(template)
        return

    st = _status_style(template["status"])
    size = "-"
    if template.get("size_bytes") and template["size_bytes"] > 0:
        size_mb = template["size_bytes"] / (1024 * 1024)
        size = f"{size_mb:.1f} MB"

    panel_content = (
        f"[bold]名称:[/bold] {template['name']}\n"
        f"[bold]描述:[/bold] {template.get('description') or '-'}\n"
        f"[bold]状态:[/bold] [{st}]{template['status']}[/{st}]\n"
        f"[bold]来源:[/bold] {template.get('source') or '-'}\n"
        f"[bold]连接类型:[/bold] {template.get('connect_type') or '-'}\n"
        f"[bold]连接端口:[/bold] {template.get('connect_port') or '-'}\n"
        f"[bold]基础镜像:[/bold] {template.get('base_image') or '-'}\n"
        f"[bold]Docker 镜像:[/bold] {template.get('docker_image') or '-'}\n"
        f"[bold]镜像大小:[/bold] {size}\n"
        f"[bold]创建时间:[/bold] {template.get('created_at', '-')[:19]}\n"
        f"[bold]更新时间:[/bold] {template.get('updated_at', '-')[:19]}"
    )

    # Entrypoint
    entrypoint = template.get("entrypoint", [])
    if entrypoint:
        panel_content += f"\n[bold]启动命令:[/bold] {' '.join(entrypoint)}"

    # Env
    env = template.get("env", {})
    if env:
        panel_content += "\n[bold]环境变量:[/bold]"
        for k, v in env.items():
            panel_content += f"\n  {k}={v}"

    # Ports
    ports = template.get("ports", {})
    if ports:
        panel_content += "\n[bold]端口映射:[/bold]"
        for pname, pval in ports.items():
            panel_content += f"\n  {pname}: {pval}"

    # Install commands
    cmds = template.get("install_commands", [])
    if cmds:
        panel_content += f"\n[bold]安装命令:[/bold] ({len(cmds)} 条)"
        for i, cmd in enumerate(cmds, 1):
            panel_content += f"\n  {i}. {cmd}"

    # Build error
    if template.get("build_error"):
        panel_content += f"\n[bold red]构建错误:[/bold red] {template['build_error']}"

    console.print(Panel(panel_content, title=f"模板详情: {template['name']}", border_style="cyan"))


@template_app.command("rm", help="删除模板")
def template_rm(
    name: str = typer.Argument(help="模板名称"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """删除模板，同时清理对应的 Docker 镜像。"""
    result = _api_delete(f"/templates/{name}")
    if json_output:
        _print_json(result)
    else:
        console.print(f"[green]{result.get('message', f'模板 {name} 已删除')}[/green]")


@app.command(help="将运行中沙盒保存为模板")
def snapshot(
    sandbox_id: str = typer.Argument(help="沙盒 ID（支持前缀匹配）"),
    name: str = typer.Option(..., "--name", "-n", help="新模板名称"),
    description: str = typer.Option("", "--desc", "-d", help="模板描述"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """将运行中的沙盒快照保存为新模板。"""
    full_id = _resolve_sandbox_id(sandbox_id)

    with console.status("[bold green]正在保存快照..."):
        body: dict = {"name": name}
        if description:
            body["description"] = description
        result = _api_post(f"/sandboxes/{full_id}/save-template", json_body=body)

    if json_output:
        _print_json(result)
    else:
        console.print(f"[green]{result.get('message', f'快照已保存为模板 {name}')}[/green]")


# ===========================================================================
# 功能 #18: 系统管理命令
# ===========================================================================


@app.command(help="显示系统状态")
def status(
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """显示 Sandbox Manager 系统状态。"""
    data = _api_get("/status")

    if json_output:
        _print_json(data)
        return

    api_ok = data.get("api_running", False)
    osb_ok = data.get("opensandbox_connected", False)
    active = data.get("active_sandboxes", 0)
    built = data.get("built_templates", 0)
    total = data.get("total_templates", 0)

    api_icon = "[green]OK[/green]" if api_ok else "[red]不可用[/red]"
    osb_icon = "[green]已连接[/green]" if osb_ok else "[red]未连接[/red]"

    panel_content = (
        f"[bold]API 服务:[/bold]       {api_icon}\n"
        f"[bold]OpenSandbox:[/bold]    {osb_icon}\n"
        f"[bold]活跃沙盒:[/bold]       {active}\n"
        f"[bold]已构建模板:[/bold]     {built}/{total}"
    )

    console.print(Panel(panel_content, title="Sandbox Manager 系统状态", border_style="cyan"))


@config_app.command("show", help="显示当前配置")
def config_show(
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """显示当前配置。"""
    config: dict = {
        "api_url": _get_api_base(),
        "config_file": str(CONFIG_FILE),
    }

    # Read config file if exists
    if CONFIG_FILE.exists():
        try:
            import yaml

            with open(CONFIG_FILE) as f:
                file_cfg = yaml.safe_load(f) or {}
            config["file_config"] = file_cfg
        except Exception:
            config["file_config"] = {"error": "无法读取配置文件"}
    else:
        config["file_config"] = {}

    if json_output:
        _print_json(config)
        return

    panel_content = (
        f"[bold]API 地址:[/bold]     {config['api_url']}\n"
        f"[bold]配置文件:[/bold]     {config['config_file']}"
    )

    file_cfg = config.get("file_config", {})
    if file_cfg:
        panel_content += "\n\n[bold]配置文件内容:[/bold]"
        for k, v in file_cfg.items():
            panel_content += f"\n  {k}: {v}"
    else:
        panel_content += "\n\n[dim]配置文件不存在，使用默认配置[/dim]"

    console.print(Panel(panel_content, title="配置信息", border_style="cyan"))


@config_app.command("set", help="修改配置项")
def config_set(
    key: str = typer.Argument(help="配置键名，如 api_url"),
    value: str = typer.Argument(help="配置值"),
) -> None:
    """修改配置项，保存到 ~/.sandbox-manager/config.yaml。"""
    import yaml

    # Ensure config dir exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing config
    config: dict = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}

    # Update
    config[key] = value

    # Write back
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)

    console.print(f"[green]已设置:[/green] {key} = {value}")
    console.print(f"[dim]配置文件: {CONFIG_FILE}[/dim]")


@app.command(help="显示版本信息")
def version() -> None:
    """显示 Sandbox Manager 版本信息。"""
    console.print(f"Sandbox Manager v{__version__}")


# ---------------------------------------------------------------------------
# Entry point (for `python -m sandbox_manager.cli`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
