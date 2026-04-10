"""测试: M3 CLI 工具

测试覆盖:
- 功能 #15: sbx start（一键启动）
- 功能 #16: sbx list / connect / stop / rm / pause / resume
- 功能 #17: sbx template list / build / init / show / rm / snapshot
- 功能 #18: sbx status / config / version

使用 httpx mock 模拟 API 响应，不需要运行 FastAPI 服务。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from sandbox_manager.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

TEMPLATE_PYTHON_DEV = {
    "id": "tpl-001",
    "name": "python-dev",
    "description": "Python 3.11 开发环境",
    "status": "ready",
    "source": "builtin",
    "connect_type": "shell",
    "docker_image": "sbxmgr/python-dev:latest",
    "size_bytes": 524288000,
    "created_at": "2026-04-09T10:00:00",
    "updated_at": "2026-04-09T10:00:00",
    "base_image": "ubuntu:22.04",
    "docker_image_id": "sha256:abc123",
    "entrypoint": ["tail", "-f", "/dev/null"],
    "env": {"DEBIAN_FRONTEND": "noninteractive"},
    "ports": {},
    "install_commands": ["apt-get update", "apt-get install -y python3"],
    "connect_port": None,
    "build_error": None,
}

TEMPLATE_VSCODE = {
    "id": "tpl-002",
    "name": "vscode",
    "description": "VS Code Web (code-server)",
    "status": "ready",
    "source": "builtin",
    "connect_type": "url",
    "docker_image": "sbxmgr/vscode:latest",
    "size_bytes": 1048576000,
    "created_at": "2026-04-09T10:00:00",
    "updated_at": "2026-04-09T10:00:00",
    "connect_port": 8080,
    "base_image": "ubuntu:22.04",
}

TEMPLATE_UNBUILT = {
    "id": "tpl-003",
    "name": "claude-code",
    "description": "Claude Code 开发环境",
    "status": "unbuilt",
    "source": "builtin",
    "connect_type": "shell",
    "docker_image": "sbxmgr/claude-code:latest",
    "size_bytes": None,
    "created_at": "2026-04-09T10:00:00",
    "updated_at": "2026-04-09T10:00:00",
}

ALL_TEMPLATES = [TEMPLATE_PYTHON_DEV, TEMPLATE_VSCODE, TEMPLATE_UNBUILT]

SANDBOX_1 = {
    "id": "d91a0b2c-1234-5678-9abc-def012345678",
    "name": "my-sandbox",
    "template_name": "python-dev",
    "template_id": "tpl-001",
    "status": "running",
    "image": "sbxmgr/python-dev:latest",
    "created_at": "2026-04-09T11:00:00",
    "connect_type": "shell",
    "docker_container_name": "sandbox-d91a0b2c-1234-5678-9abc-def012345678",
}

SANDBOX_2 = {
    "id": "e82b1c3d-2345-6789-0bcd-ef1234567890",
    "name": None,
    "template_name": "vscode",
    "template_id": "tpl-002",
    "status": "paused",
    "image": "sbxmgr/vscode:latest",
    "created_at": "2026-04-09T12:00:00",
    "connect_type": "url",
    "docker_container_name": "sandbox-e82b1c3d-2345-6789-0bcd-ef1234567890",
}

ALL_SANDBOXES = [SANDBOX_1, SANDBOX_2]

CONNECT_INFO_SHELL = {
    "connect_type": "shell",
    "sandbox_id": SANDBOX_1["id"],
    "container_name": SANDBOX_1["docker_container_name"],
    "status": "running",
    "command": f"docker exec -it {SANDBOX_1['docker_container_name']} /bin/bash",
    "url": None,
    "port": None,
    "ports": None,
}

CONNECT_INFO_URL = {
    "connect_type": "url",
    "sandbox_id": SANDBOX_2["id"],
    "container_name": SANDBOX_2["docker_container_name"],
    "status": "running",
    "command": None,
    "url": "http://localhost:8080",
    "port": 8080,
    "ports": None,
}

SYSTEM_STATUS = {
    "api_running": True,
    "opensandbox_connected": True,
    "active_sandboxes": 2,
    "built_templates": 2,
    "total_templates": 4,
}


def _mock_response(data, status_code=200):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = data
    resp.text = json.dumps(data, ensure_ascii=False)
    return resp


def _make_mock_client(routes: dict):
    """Create a mock httpx.Client context manager that routes requests.

    routes: dict mapping (method, path) -> response_data or (status, data)

    Path matching uses longest-prefix-match so that e.g.
    "/sandboxes/d91/connect-info" matches before "/sandboxes".
    An exact match always wins.
    """
    mock_client = MagicMock(spec=httpx.Client)

    def _find(method_filter: str, path: str):
        """Find the best matching route using longest prefix match."""
        best_match = None
        best_len = -1
        for (method, prefix), value in routes.items():
            if method != method_filter:
                continue
            # exact match wins immediately
            if path == prefix:
                return value
            if path.startswith(prefix) and len(prefix) > best_len:
                best_match = value
                best_len = len(prefix)
        return best_match

    def _to_response(value):
        if value is None:
            return _mock_response({"message": "Route not found"}, 404)
        if isinstance(value, tuple):
            status, data = value
            return _mock_response(data, status)
        return _mock_response(value)

    def _get(path, **kwargs):
        return _to_response(_find("GET", path))

    def _post(path, **kwargs):
        return _to_response(_find("POST", path))

    def _delete(path, **kwargs):
        return _to_response(_find("DELETE", path))

    mock_client.get.side_effect = _get
    mock_client.post.side_effect = _post
    mock_client.delete.side_effect = _delete
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return mock_client


# ===========================================================================
# 功能 #18: sbx version
# ===========================================================================


class TestVersion:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Sandbox Manager" in result.output
        assert "0.1.0" in result.output


# ===========================================================================
# 功能 #16: sbx list
# ===========================================================================


class TestList:
    def test_list_sandboxes_table(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "d91a0b2c" in result.output
        assert "python-dev" in result.output
        assert "running" in result.output
        assert "paused" in result.output

    def test_list_sandboxes_json(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["id"] == SANDBOX_1["id"]

    def test_list_sandboxes_empty(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): [],
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "没有沙盒" in result.output

    def test_list_api_unreachable(self):
        with patch(
            "sandbox_manager.cli.httpx.Client",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 1
        assert "无法连接" in result.output


# ===========================================================================
# 功能 #15: sbx start
# ===========================================================================


class TestStart:
    def test_start_shell_template(self):
        """Test start with a shell-type template (should call os.execvp)."""
        mock_client = _make_mock_client({
            ("GET", "/templates/python-dev"): TEMPLATE_PYTHON_DEV,
            ("POST", "/sandboxes"): SANDBOX_1,
            ("GET", "/sandboxes/"): CONNECT_INFO_SHELL,
        })

        with (
            patch("sandbox_manager.cli.httpx.Client", return_value=mock_client),
            patch("sandbox_manager.cli.os.execvp") as mock_execvp,
        ):
            result = runner.invoke(app, ["start", "python-dev"])

        assert result.exit_code == 0
        assert "沙盒已创建" in result.output
        mock_execvp.assert_called_once_with(
            "docker",
            ["docker", "exec", "-it", SANDBOX_1["docker_container_name"], "/bin/bash"],
        )

    def test_start_url_template(self):
        """Test start with a url-type template (should open browser)."""
        mock_client = _make_mock_client({
            ("GET", "/templates/vscode"): TEMPLATE_VSCODE,
            ("POST", "/sandboxes"): SANDBOX_2,
            ("GET", "/sandboxes/"): CONNECT_INFO_URL,
        })

        with (
            patch("sandbox_manager.cli.httpx.Client", return_value=mock_client),
            patch("sandbox_manager.cli.webbrowser.open") as mock_open,
        ):
            result = runner.invoke(app, ["start", "vscode"])

        assert result.exit_code == 0
        assert "沙盒已创建" in result.output
        mock_open.assert_called_once_with("http://localhost:8080")

    def test_start_unbuilt_template(self):
        """Test start with an unbuilt template shows guidance."""
        mock_client = _make_mock_client({
            ("GET", "/templates/claude-code"): TEMPLATE_UNBUILT,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["start", "claude-code"])

        assert result.exit_code == 1
        assert "尚未构建" in result.output
        assert "sbx template build" in result.output

    def test_start_nonexistent_template(self):
        """Test start with nonexistent template shows available templates."""
        error_resp = {"message": "模板 'nonexistent' 不存在", "detail": "..."}
        mock_client = _make_mock_client({
            ("GET", "/templates/nonexistent"): (404, error_resp),
            ("GET", "/templates"): ALL_TEMPLATES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["start", "nonexistent"])

        assert result.exit_code == 1
        assert "不存在" in result.output

    def test_start_json_output(self):
        """Test start with --json flag returns JSON instead of connecting."""
        mock_client = _make_mock_client({
            ("GET", "/templates/python-dev"): TEMPLATE_PYTHON_DEV,
            ("POST", "/sandboxes"): SANDBOX_1,
            ("GET", "/sandboxes/"): CONNECT_INFO_SHELL,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["start", "python-dev", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sandbox" in data
        assert "connect_info" in data


# ===========================================================================
# 功能 #16: sbx connect / stop / rm / pause / resume
# ===========================================================================


class TestConnect:
    def test_connect_by_prefix(self):
        """Test connecting by sandbox ID prefix."""
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("GET", "/sandboxes/d91"): CONNECT_INFO_SHELL,
        })

        with (
            patch("sandbox_manager.cli.httpx.Client", return_value=mock_client),
            patch("sandbox_manager.cli.os.execvp") as mock_execvp,
        ):
            result = runner.invoke(app, ["connect", "d91"])

        assert result.exit_code == 0
        mock_execvp.assert_called_once()

    def test_connect_nonexistent(self):
        """Test connecting to nonexistent sandbox."""
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["connect", "zzz"])

        assert result.exit_code == 1
        assert "找不到" in result.output

    def test_connect_json(self):
        """Test connect with --json flag."""
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("GET", "/sandboxes/d91"): CONNECT_INFO_SHELL,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["connect", "d91", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["connect_type"] == "shell"


class TestStop:
    def test_stop_single(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("DELETE", "/sandboxes/d91"): {"success": True, "message": "沙盒已销毁"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["stop", "d91"])

        assert result.exit_code == 0
        assert "已销毁" in result.output or "已停止" in result.output

    def test_stop_all(self):
        mock_client = _make_mock_client({
            ("DELETE", "/sandboxes"): {
                "success": True,
                "total": 2,
                "deleted": 2,
                "failed": 0,
                "message": "已销毁 2/2 个沙盒",
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["stop", "--all"])

        assert result.exit_code == 0
        assert "已停止" in result.output

    def test_stop_no_arg(self):
        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 1


class TestRm:
    def test_rm_single(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("DELETE", "/sandboxes/d91"): {"success": True, "message": "沙盒已销毁"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["rm", "d91"])

        assert result.exit_code == 0

    def test_rm_all(self):
        mock_client = _make_mock_client({
            ("DELETE", "/sandboxes"): {
                "success": True,
                "total": 2,
                "deleted": 2,
                "failed": 0,
                "message": "已销毁 2/2 个沙盒",
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["rm", "--all"])

        assert result.exit_code == 0

    def test_rm_json(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("DELETE", "/sandboxes/d91"): {"success": True, "message": "沙盒已销毁"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["rm", "d91", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True


class TestPause:
    def test_pause(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("POST", "/sandboxes/d91"): {"success": True, "message": "沙盒已暂停"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["pause", "d91"])

        assert result.exit_code == 0
        assert "已暂停" in result.output

    def test_pause_json(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("POST", "/sandboxes/d91"): {"success": True, "message": "沙盒已暂停"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["pause", "d91", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True


class TestResume:
    def test_resume(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("POST", "/sandboxes/e82"): {"success": True, "message": "沙盒已恢复运行"},
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["resume", "e82"])

        assert result.exit_code == 0
        assert "已恢复" in result.output


# ===========================================================================
# 功能 #17: sbx template
# ===========================================================================


class TestTemplateList:
    def test_template_list_table(self):
        mock_client = _make_mock_client({
            ("GET", "/templates"): ALL_TEMPLATES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "list"])

        assert result.exit_code == 0
        # Rich table may truncate long names, so check for partial matches
        assert "python" in result.output.lower()
        assert "vscode" in result.output
        assert "ready" in result.output
        assert "unbuilt" in result.output

    def test_template_list_json(self):
        mock_client = _make_mock_client({
            ("GET", "/templates"): ALL_TEMPLATES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3


class TestTemplateBuild:
    def test_build_single(self):
        """Test building a single template with polling."""
        build_status_ready = {"name": "python-dev", "status": "ready", "build_error": None}
        mock_client = _make_mock_client({
            ("POST", "/templates/python-dev/build"): {
                "success": True,
                "message": "构建已启动",
            },
            ("GET", "/templates/python-dev/build-status"): build_status_ready,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "build", "python-dev"])

        assert result.exit_code == 0
        assert "构建成功" in result.output or "构建已启动" in result.output

    def test_build_all(self):
        """Test building all unbuilt templates."""
        build_status = {"name": "claude-code", "status": "ready", "build_error": None}
        mock_client = _make_mock_client({
            ("GET", "/templates"): ALL_TEMPLATES,
            ("POST", "/templates/claude-code/build"): {
                "success": True,
                "message": "构建已启动",
            },
            ("GET", "/templates/claude-code/build-status"): build_status,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "build", "--all"])

        assert result.exit_code == 0

    def test_build_no_arg(self):
        result = runner.invoke(app, ["template", "build"])
        assert result.exit_code == 1


class TestTemplateInit:
    def test_init_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["template", "init", "my-template", "--dir", tmpdir])

        assert result.exit_code == 0
        assert "已生成模板配置文件" in result.output

    def test_init_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner.invoke(app, ["template", "init", "test-tpl", "--dir", tmpdir])
            content = (Path(tmpdir) / "test-tpl.yaml").read_text()

        assert "name: test-tpl" in content
        assert "base_image" in content
        assert "connect_type" in content
        assert "install_commands" in content


class TestTemplateShow:
    def test_show_template(self):
        mock_client = _make_mock_client({
            ("GET", "/templates/python-dev"): TEMPLATE_PYTHON_DEV,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "show", "python-dev"])

        assert result.exit_code == 0
        assert "python-dev" in result.output
        assert "Python 3.11" in result.output

    def test_show_template_json(self):
        mock_client = _make_mock_client({
            ("GET", "/templates/python-dev"): TEMPLATE_PYTHON_DEV,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "show", "python-dev", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "python-dev"


class TestTemplateRm:
    def test_rm_template(self):
        mock_client = _make_mock_client({
            ("DELETE", "/templates/python-dev"): {
                "success": True,
                "message": "模板 'python-dev' 已删除",
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "rm", "python-dev"])

        assert result.exit_code == 0
        assert "已删除" in result.output

    def test_rm_template_json(self):
        mock_client = _make_mock_client({
            ("DELETE", "/templates/python-dev"): {
                "success": True,
                "message": "模板 'python-dev' 已删除",
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "rm", "python-dev", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True


class TestSnapshot:
    def test_snapshot(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("POST", "/sandboxes/d91"): {
                "success": True,
                "message": "快照保存成功: 模板 'my-env'",
                "data": {"template_name": "my-env", "size_bytes": 524288000},
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["snapshot", "d91", "--name", "my-env"])

        assert result.exit_code == 0
        assert "快照" in result.output

    def test_snapshot_json(self):
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("POST", "/sandboxes/d91"): {
                "success": True,
                "message": "快照保存成功",
                "data": {"template_name": "my-env"},
            },
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["snapshot", "d91", "--name", "my-env", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True


# ===========================================================================
# 功能 #18: sbx status / config
# ===========================================================================


class TestStatus:
    def test_status(self):
        mock_client = _make_mock_client({
            ("GET", "/status"): SYSTEM_STATUS,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "API" in result.output
        assert "OpenSandbox" in result.output

    def test_status_json(self):
        mock_client = _make_mock_client({
            ("GET", "/status"): SYSTEM_STATUS,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["api_running"] is True
        assert data["active_sandboxes"] == 2

    def test_status_api_unreachable(self):
        with patch(
            "sandbox_manager.cli.httpx.Client",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "无法连接" in result.output


class TestConfig:
    def test_config_show(self):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "API" in result.output

    def test_config_show_json(self):
        result = runner.invoke(app, ["config", "show", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "api_url" in data

    def test_config_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            with patch("sandbox_manager.cli.CONFIG_DIR", Path(tmpdir)):
                with patch("sandbox_manager.cli.CONFIG_FILE", config_file):
                    result = runner.invoke(app, ["config", "set", "api_url", "http://localhost:8080"])

            assert result.exit_code == 0
            assert "已设置" in result.output
            assert config_file.exists()
            content = config_file.read_text()
            assert "http://localhost:8080" in content


# ===========================================================================
# 错误处理
# ===========================================================================


class TestErrorHandling:
    def test_api_unreachable_clear_message(self):
        """Error scenario 15: API service not running."""
        with patch(
            "sandbox_manager.cli.httpx.Client",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 1
        assert "无法连接" in result.output
        assert "docker-compose" in result.output

    def test_wrong_template_name(self):
        """Error scenario 16: wrong template name."""
        error_resp = {"message": "模板 'wrong' 不存在", "success": False}
        mock_client = _make_mock_client({
            ("GET", "/templates/wrong"): (404, error_resp),
            ("GET", "/templates"): ALL_TEMPLATES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["start", "wrong"])

        assert result.exit_code == 1
        assert "不存在" in result.output

    def test_wrong_sandbox_id(self):
        """Error scenario 17: wrong sandbox ID."""
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["connect", "nonexistent"])

        assert result.exit_code == 1
        assert "找不到" in result.output

    def test_prefix_match_multiple(self):
        """Test that multiple prefix matches shows disambiguation."""
        sandboxes_with_same_prefix = [
            {**SANDBOX_1, "id": "d91a0b2c-1111"},
            {**SANDBOX_1, "id": "d91a0b2c-2222"},
        ]
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): sandboxes_with_same_prefix,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["connect", "d91"])

        assert result.exit_code == 1
        assert "匹配到多个" in result.output

    def test_timeout_error_friendly_message(self):
        """QA fix #2: TimeoutException should show friendly message, not traceback."""
        with patch(
            "sandbox_manager.cli.httpx.Client",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 1
        assert "请求超时" in result.output

    def test_timeout_on_delete(self):
        """QA fix #2: TimeoutException on DELETE also handled."""
        with patch(
            "sandbox_manager.cli.httpx.Client",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = runner.invoke(app, ["rm", "--all"])

        assert result.exit_code == 1
        assert "请求超时" in result.output

    def test_connect_paused_sandbox_friendly_message(self):
        """QA fix #4: Paused sandbox connect shows CLI command, not API path."""
        error_resp = {
            "message": "沙盒已暂停，请先恢复沙盒: POST /api/v1/sandboxes/{id}/resume"
        }
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
            ("GET", f"/sandboxes/{SANDBOX_2['id']}/connect-info"): (409, error_resp),
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["connect", "e82"])

        assert result.exit_code == 1
        assert "sbx resume" in result.output
        assert "POST /api" not in result.output


# ===========================================================================
# JSON 输出验证
# ===========================================================================


class TestJsonOutput:
    def test_list_json_valid(self):
        """QA scenario 18: sbx list --json outputs valid JSON."""
        mock_client = _make_mock_client({
            ("GET", "/sandboxes"): ALL_SANDBOXES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        # Ensure it's valid JSON
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_template_list_json_valid(self):
        mock_client = _make_mock_client({
            ("GET", "/templates"): ALL_TEMPLATES,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["template", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_status_json_valid(self):
        mock_client = _make_mock_client({
            ("GET", "/status"): SYSTEM_STATUS,
        })

        with patch("sandbox_manager.cli.httpx.Client", return_value=mock_client):
            result = runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
