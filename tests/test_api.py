"""测试: API 端点（使用 FastAPI TestClient）"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """创建测试客户端"""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    monkeypatch.setattr("sandbox_manager.config.settings.database_path", db_path)

    # 重置引擎状态
    import sandbox_manager.db.engine as engine_mod

    engine_mod._engine = None
    engine_mod._session_factory = None

    # 重置依赖注入单例
    import sandbox_manager.dependencies as deps

    deps._docker_bridge = None
    deps._sandbox_service = None
    deps._template_service = None

    from sandbox_manager.main import app

    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """健康检查端点应返回 200"""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.1.0"
    assert data["database_ok"] is True


def test_status_endpoint(client):
    """系统状态端点应返回 200"""
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_running"] is True
    assert data["total_templates"] >= 0


def test_list_templates(client):
    """模板列表端点应返回 4 个内置模板"""
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) == 4
    names = {t["name"] for t in templates}
    assert "claude-code" in names
    assert "vscode" in names
    assert "python-dev" in names
    assert "openclaw" in names


def test_get_template_detail(client):
    """模板详情端点应返回完整信息"""
    resp = client.get("/api/v1/templates/claude-code")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "claude-code"
    assert data["connect_type"] == "shell"
    assert data["status"] == "unbuilt"
    assert data["source"] == "builtin"
    assert data["base_image"] == "ubuntu:22.04"
    assert isinstance(data["install_commands"], list)
    assert len(data["install_commands"]) > 0


def test_get_nonexistent_template(client):
    """不存在的模板应返回 404"""
    resp = client.get("/api/v1/templates/nonexistent")
    assert resp.status_code == 404


def test_list_sandboxes_empty(client):
    """沙盒列表初始应为空"""
    resp = client.get("/api/v1/sandboxes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_nonexistent_sandbox(client):
    """不存在的沙盒应返回 404"""
    resp = client.get("/api/v1/sandboxes/nonexistent-id")
    assert resp.status_code == 404


def test_create_sandbox_no_params(client):
    """创建沙盒不提供参数应返回 400"""
    resp = client.post("/api/v1/sandboxes", json={})
    assert resp.status_code == 400


def test_create_sandbox_unbuilt_template(client):
    """从未构建的模板创建沙盒应返回 400"""
    resp = client.post(
        "/api/v1/sandboxes",
        json={"template_name": "claude-code"},
    )
    assert resp.status_code == 400
    assert "构建" in resp.json()["detail"]


def test_delete_nonexistent_sandbox(client):
    """删除不存在的沙盒应返回 404"""
    resp = client.delete("/api/v1/sandboxes/nonexistent-id")
    assert resp.status_code == 404


def test_build_status_unbuilt(client):
    """未构建模板的 build-status 应返回 unbuilt"""
    resp = client.get("/api/v1/templates/claude-code/build-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unbuilt"
    assert data["name"] == "claude-code"
