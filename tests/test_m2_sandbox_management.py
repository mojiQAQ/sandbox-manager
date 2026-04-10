"""测试: M2 沙盒管理 API 端点

测试覆盖:
- 功能 #10: 创建沙盒增强（未构建模板的错误处理）
- 功能 #11: 自适应连接（connect-info 端点）
- 功能 #12: 沙盒列表与状态（按状态筛选）
- 功能 #13: 沙盒暂停与恢复
- 功能 #14: 批量销毁

因为这些测试不启动真正的 OpenSandbox server，所以使用 mock 来模拟外部依赖。
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

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
    deps._connector_service = None

    from sandbox_manager.main import app

    with TestClient(app) as c:
        yield c


def _insert_sandbox(client, sandbox_id="test-sandbox-001", status="running"):
    """辅助函数: 直接向数据库插入沙盒记录"""
    import asyncio

    from sandbox_manager.db.engine import _get_session_factory
    from sandbox_manager.models.database import ActiveSandbox

    async def _insert():
        factory = _get_session_factory()
        async with factory() as session:
            # 获取第一个模板的 ID
            from sqlalchemy import select

            from sandbox_manager.models.database import Template

            result = await session.execute(
                select(Template).where(Template.name == "python-dev")
            )
            template = result.scalar_one_or_none()

            sandbox = ActiveSandbox(
                id=sandbox_id,
                template_id=template.id if template else None,
                name="test-sandbox",
                status=status,
                image="sbxmgr/python-dev:latest",
                docker_container_name=f"sandbox-{sandbox_id}",
            )
            session.add(sandbox)
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_insert())
    return sandbox_id


# --- 功能 #10: 创建沙盒增强 ---


class TestCreateSandboxEnhanced:
    """测试沙盒创建增强功能"""

    def test_create_from_unbuilt_template(self, client):
        """从未构建的模板创建沙盒应返回 400 并提示构建"""
        resp = client.post(
            "/api/v1/sandboxes",
            json={"template_name": "claude-code"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "构建" in data["message"] or "构建" in data.get("detail", "")

    def test_create_from_nonexistent_template(self, client):
        """从不存在的模板创建沙盒应返回 404"""
        resp = client.post(
            "/api/v1/sandboxes",
            json={"template_name": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_create_without_params(self, client):
        """不提供参数创建沙盒应返回 400"""
        resp = client.post("/api/v1/sandboxes", json={})
        assert resp.status_code == 400


# --- 功能 #11: 自适应连接 ---


class TestConnectInfo:
    """测试自适应连接端点"""

    def test_connect_info_nonexistent_sandbox(self, client):
        """获取不存在沙盒的连接信息应返回 404"""
        resp = client.get("/api/v1/sandboxes/nonexistent/connect-info")
        assert resp.status_code == 404

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_connect_info_paused_sandbox(self, mock_status, client):
        """获取已暂停沙盒的连接信息应返回 409"""
        sandbox_id = _insert_sandbox(client, sandbox_id="paused-sbx-001", status="paused")
        mock_status.return_value = "paused"

        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/connect-info")
        assert resp.status_code == 409
        data = resp.json()
        assert "暂停" in data["message"]

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_connect_info_stopped_sandbox(self, mock_status, client):
        """获取已停止沙盒的连接信息应返回 409"""
        sandbox_id = _insert_sandbox(client, sandbox_id="stopped-sbx-001", status="stopped")
        mock_status.return_value = "exited"

        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/connect-info")
        assert resp.status_code == 409
        data = resp.json()
        assert "停止" in data["message"]

    @patch("sandbox_manager.services.connector.ConnectorService.get_connect_info")
    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_connect_info_running_shell(self, mock_status, mock_connect, client):
        """运行中的 shell 类型沙盒应返回 docker exec 命令"""
        sandbox_id = _insert_sandbox(client, sandbox_id="running-shell-001", status="running")
        mock_status.return_value = "running"
        mock_connect.return_value = {
            "connect_type": "shell",
            "command": f"docker exec -it sandbox-{sandbox_id} /bin/bash",
            "sandbox_id": sandbox_id,
            "container_name": f"sandbox-{sandbox_id}",
        }

        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/connect-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connect_type"] == "shell"
        assert data["command"] is not None
        assert "docker exec" in data["command"]
        assert data["status"] == "running"


# --- 功能 #12: 沙盒列表与状态 ---


class TestSandboxList:
    """测试沙盒列表端点"""

    def test_list_empty(self, client):
        """初始沙盒列表应为空"""
        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_list_with_status_filter(self, mock_status, client):
        """支持按状态筛选沙盒"""
        _insert_sandbox(client, sandbox_id="run-sbx-001", status="running")
        _insert_sandbox(client, sandbox_id="pause-sbx-002", status="paused")
        mock_status.return_value = "running"

        # 不筛选 - 返回全部
        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        # mock 返回 running，所以 paused 的也会被同步为 running
        # 这里的关键测试点是 API 支持 status 查询参数

        # 按 running 筛选
        resp = client.get("/api/v1/sandboxes?status=running")
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["status"] == "running"

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_list_syncs_container_status(self, mock_status, client):
        """列表应同步容器实际状态"""
        # 数据库中记录为 running，但 Docker 容器已退出
        _insert_sandbox(client, sandbox_id="sync-sbx-001", status="running")
        mock_status.return_value = "exited"

        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        found = [s for s in data if s["id"] == "sync-sbx-001"]
        assert len(found) == 1
        assert found[0]["status"] == "stopped"


# --- 功能 #13: 暂停与恢复 ---


class TestPauseResume:
    """测试暂停与恢复端点"""

    def test_pause_nonexistent(self, client):
        """暂停不存在的沙盒应返回 404"""
        resp = client.post("/api/v1/sandboxes/nonexistent/pause")
        assert resp.status_code == 404

    def test_resume_nonexistent(self, client):
        """恢复不存在的沙盒应返回 404"""
        resp = client.post("/api/v1/sandboxes/nonexistent/resume")
        assert resp.status_code == 404

    def test_pause_already_paused(self, client):
        """暂停已暂停的沙盒应返回 400（Docker 状态同步后判断）"""
        sandbox_id = _insert_sandbox(client, sandbox_id="paused-sbx-p01", status="paused")
        with patch(
            "sandbox_manager.services.docker_bridge.DockerBridge.get_container_status",
            return_value="paused",
        ):
            resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/pause")
        assert resp.status_code == 400

    def test_resume_already_running(self, client):
        """恢复正在运行的沙盒应返回 400（Docker 状态同步后判断）"""
        sandbox_id = _insert_sandbox(client, sandbox_id="running-sbx-r01", status="running")
        with patch(
            "sandbox_manager.services.docker_bridge.DockerBridge.get_container_status",
            return_value="running",
        ):
            resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        assert resp.status_code == 400

    def test_pause_stopped_sandbox(self, client):
        """暂停已停止的沙盒应返回 400（Docker 状态同步后判断）"""
        sandbox_id = _insert_sandbox(client, sandbox_id="stopped-sbx-s01", status="stopped")
        with patch(
            "sandbox_manager.services.docker_bridge.DockerBridge.get_container_status",
            return_value="exited",
        ):
            resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/pause")
        assert resp.status_code == 400

    def test_resume_stopped_sandbox(self, client):
        """恢复已停止的沙盒应返回 400（Docker 状态同步后判断）"""
        sandbox_id = _insert_sandbox(client, sandbox_id="stopped-sbx-s02", status="stopped")
        with patch(
            "sandbox_manager.services.docker_bridge.DockerBridge.get_container_status",
            return_value="exited",
        ):
            resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        assert resp.status_code == 400

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    @patch("sandbox_manager.services.sandbox_service.SandboxService.pause_sandbox")
    def test_pause_success(self, mock_pause, mock_status, client):
        """成功暂停运行中的沙盒"""
        mock_pause.return_value = None
        mock_status.return_value = "running"
        sandbox_id = _insert_sandbox(client, sandbox_id="pause-ok-001", status="running")

        resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "暂停" in data["message"]
        mock_pause.assert_called_once_with(sandbox_id)

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    @patch("sandbox_manager.services.sandbox_service.SandboxService.resume_sandbox")
    def test_resume_success(self, mock_resume, mock_status, client):
        """成功恢复已暂停的沙盒"""
        mock_resume.return_value = MagicMock()
        mock_status.return_value = "paused"
        sandbox_id = _insert_sandbox(client, sandbox_id="resume-ok-001", status="paused")

        resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "恢复" in data["message"]
        mock_resume.assert_called_once_with(sandbox_id)


# --- 功能 #14: 销毁与批量销毁 ---


class TestDeleteSandbox:
    """测试销毁沙盒端点"""

    def test_delete_nonexistent(self, client):
        """删除不存在的沙盒应返回 404"""
        resp = client.delete("/api/v1/sandboxes/nonexistent")
        assert resp.status_code == 404

    @patch("sandbox_manager.services.sandbox_service.SandboxService.kill_sandbox_by_id")
    def test_delete_single(self, mock_kill, client):
        """成功删除单个沙盒"""
        mock_kill.return_value = None
        sandbox_id = _insert_sandbox(client, sandbox_id="del-sbx-001", status="running")

        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # 再查应该 404
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 404

    def test_batch_delete_without_all(self, client):
        """批量删除必须显式传入 all=true"""
        resp = client.delete("/api/v1/sandboxes")
        assert resp.status_code == 400

    def test_batch_delete_all_false(self, client):
        """批量删除 all=false 应返回 400"""
        resp = client.delete("/api/v1/sandboxes?all=false")
        assert resp.status_code == 400

    @patch("sandbox_manager.services.sandbox_service.SandboxService.kill_sandbox_by_id")
    def test_batch_delete_success(self, mock_kill, client):
        """成功批量删除所有沙盒"""
        mock_kill.return_value = None
        _insert_sandbox(client, sandbox_id="batch-del-001", status="running")
        _insert_sandbox(client, sandbox_id="batch-del-002", status="paused")
        _insert_sandbox(client, sandbox_id="batch-del-003", status="stopped")

        resp = client.delete("/api/v1/sandboxes?all=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 3
        assert data["deleted"] == 3

        # 列表应为空
        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        assert resp.json() == []


# --- ConnectorService 单元测试 ---


class TestConnectorService:
    """测试 ConnectorService"""

    def test_build_shell_info(self):
        """shell 类型应返回 docker exec 命令"""
        from sandbox_manager.services.connector import ConnectorService
        from sandbox_manager.services.sandbox_service import SandboxService

        service = ConnectorService(sandbox_service=MagicMock(spec=SandboxService))
        info = service._build_shell_info("test-id", "sandbox-test-id")

        assert info["connect_type"] == "shell"
        assert "docker exec -it sandbox-test-id /bin/bash" == info["command"]
        assert info["sandbox_id"] == "test-id"

    @pytest.mark.asyncio
    async def test_build_url_info(self):
        """url 类型应返回访问 URL"""
        from sandbox_manager.services.connector import ConnectorService

        mock_service = MagicMock()
        mock_service.get_endpoint = AsyncMock(return_value="http://endpoint:8443")
        service = ConnectorService(sandbox_service=mock_service)

        info = await service._build_url_info("test-id", "sandbox-test-id", 8443, {"8443": 8443})

        assert info["connect_type"] == "url"
        assert info["url"] == "http://endpoint:8443"
        assert info["port"] == 8443

    @pytest.mark.asyncio
    async def test_build_url_info_fallback(self):
        """url 类型获取端点失败时应回退到 localhost"""
        from sandbox_manager.services.connector import ConnectorService

        mock_service = MagicMock()
        mock_service.get_endpoint = AsyncMock(side_effect=Exception("connection failed"))
        service = ConnectorService(sandbox_service=mock_service)

        info = await service._build_url_info("test-id", "sandbox-test-id", 8443, None)

        assert info["connect_type"] == "url"
        assert info["url"] == "http://localhost:8443"

    @pytest.mark.asyncio
    async def test_build_port_info(self):
        """port 类型应返回端口映射列表"""
        from sandbox_manager.services.connector import ConnectorService

        mock_service = MagicMock()
        mock_service.get_endpoint = AsyncMock(return_value="http://endpoint:7860")
        service = ConnectorService(sandbox_service=mock_service)

        info = await service._build_port_info(
            "test-id", "sandbox-test-id", 7860, {"7860": 7860}
        )

        assert info["connect_type"] == "port"
        assert len(info["ports"]) >= 1
        assert info["ports"][0]["container_port"] == 7860

    @pytest.mark.asyncio
    async def test_get_connect_info_shell(self):
        """get_connect_info 对 shell 类型应返回正确结构"""
        from sandbox_manager.services.connector import ConnectorService

        service = ConnectorService(sandbox_service=MagicMock())
        info = await service.get_connect_info(
            sandbox_id="test-id",
            sandbox_status="running",
            connect_type="shell",
        )

        assert info["connect_type"] == "shell"
        assert "docker exec" in info["command"]

    @pytest.mark.asyncio
    async def test_get_connect_info_unknown_type_fallback(self):
        """未知 connect_type 应回退到 shell"""
        from sandbox_manager.services.connector import ConnectorService

        service = ConnectorService(sandbox_service=MagicMock())
        info = await service.get_connect_info(
            sandbox_id="test-id",
            sandbox_status="running",
            connect_type="unknown",
        )

        assert info["connect_type"] == "shell"


# --- DockerBridge 状态同步测试 ---


class TestDockerStatusMapping:
    """测试 Docker 状态映射"""

    def test_status_mapping(self):
        """Docker 状态应正确映射为沙盒状态"""
        from sandbox_manager.api.sandboxes import _map_docker_status

        assert _map_docker_status("running") == "running"
        assert _map_docker_status("paused") == "paused"
        assert _map_docker_status("exited") == "stopped"
        assert _map_docker_status("created") == "stopped"
        assert _map_docker_status("dead") == "stopped"
        assert _map_docker_status(None) == "stopped"
        assert _map_docker_status("unknown-state") == "stopped"


# --- QA 修复: 状态同步与异常处理补充测试 ---


class TestPauseResumeDockerSync:
    """测试 pause/resume 端点的 Docker 状态同步（QA 问题 #1）"""

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_pause_after_external_docker_pause(self, mock_status, client):
        """外部 docker pause 后，API pause 应同步状态并返回 400 而非 500"""
        # 数据库记录为 running，但 Docker 已被外部暂停
        sandbox_id = _insert_sandbox(client, sandbox_id="ext-pause-001", status="running")
        mock_status.return_value = "paused"

        resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/pause")
        # 应该同步为 paused 后返回 400（已暂停），而不是 500
        assert resp.status_code == 400

    @patch("sandbox_manager.services.docker_bridge.DockerBridge.get_container_status")
    def test_resume_after_external_docker_unpause(self, mock_status, client):
        """外部 docker unpause 后，API resume 应同步状态并返回 400 而非 500"""
        # 数据库记录为 paused，但 Docker 已被外部恢复
        sandbox_id = _insert_sandbox(client, sandbox_id="ext-unpause-001", status="paused")
        mock_status.return_value = "running"

        resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        # 应该同步为 running 后返回 400（已在运行），而不是 500
        assert resp.status_code == 400


class TestBatchDeleteFailedCount:
    """测试批量销毁的 failed 计数（QA 问题 #2）"""

    @patch("sandbox_manager.services.sandbox_service.SandboxService.kill_sandbox_by_id")
    def test_batch_delete_partial_failure(self, mock_kill, client):
        """批量销毁部分失败时 failed 计数应正确反映"""
        _insert_sandbox(client, sandbox_id="batch-f-001", status="running")
        _insert_sandbox(client, sandbox_id="batch-f-002", status="running")
        _insert_sandbox(client, sandbox_id="batch-f-003", status="running")

        # 第二个 kill 失败
        mock_kill.side_effect = [None, Exception("Docker error"), None]

        resp = client.delete("/api/v1/sandboxes?all=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["deleted"] == 2
        assert data["failed"] == 1


class TestDeleteSandboxExceptionHandling:
    """测试单个销毁端点的异常处理（QA 问题 #4）"""

    @patch("sandbox_manager.services.sandbox_service.SandboxService.kill_sandbox_by_id")
    def test_delete_single_kill_failure(self, mock_kill, client):
        """kill 失败时仍应成功删除数据库记录并返回 200"""
        mock_kill.side_effect = Exception("Docker connection lost")
        sandbox_id = _insert_sandbox(client, sandbox_id="del-fail-001", status="running")

        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # 数据库记录应已删除
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 404
