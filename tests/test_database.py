"""测试: 数据库初始化和模板注册"""

import os
import tempfile

import pytest


@pytest.fixture
def tmp_db_path():
    """创建临时数据库路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test.db")


@pytest.mark.asyncio
async def test_db_init_and_template_registration(tmp_db_path, monkeypatch):
    """数据库初始化应创建表，模板注册应写入 4 个内置模板"""
    monkeypatch.setattr("sandbox_manager.config.settings.database_path", tmp_db_path)

    # 重置引擎状态（因为 monkeypatch 改了 settings）
    import sandbox_manager.db.engine as engine_mod

    engine_mod._engine = None
    engine_mod._session_factory = None

    from sandbox_manager.db.engine import _get_session_factory, close_db, init_db
    from sandbox_manager.services.docker_bridge import DockerBridge
    from sandbox_manager.services.sandbox_service import SandboxService
    from sandbox_manager.services.template_service import TemplateService

    await init_db()

    ts = TemplateService(SandboxService(), DockerBridge())
    factory = _get_session_factory()

    async with factory() as session:
        count = await ts.register_builtin_templates(session)
        assert count == 4, f"应注册 4 个模板，实际注册了 {count} 个"

        # 验证模板数据
        templates = await ts.list_templates(session)
        names = {t.name for t in templates}
        assert names == {"claude-code", "vscode", "openclaw", "python-dev"}

        # 验证所有模板状态为 unbuilt
        for t in templates:
            assert t.status == "unbuilt"
            assert t.source == "builtin"

    # 重复注册应返回 0
    async with factory() as session:
        count2 = await ts.register_builtin_templates(session)
        assert count2 == 0

    await close_db()


@pytest.mark.asyncio
async def test_template_crud(tmp_db_path, monkeypatch):
    """模板 CRUD 基本操作"""
    monkeypatch.setattr("sandbox_manager.config.settings.database_path", tmp_db_path)

    import sandbox_manager.db.engine as engine_mod

    engine_mod._engine = None
    engine_mod._session_factory = None

    from sandbox_manager.db.engine import _get_session_factory, close_db, init_db
    from sandbox_manager.exceptions import TemplateNotFoundError
    from sandbox_manager.services.docker_bridge import DockerBridge
    from sandbox_manager.services.sandbox_service import SandboxService
    from sandbox_manager.services.template_service import TemplateService

    await init_db()

    ts = TemplateService(SandboxService(), DockerBridge())
    factory = _get_session_factory()

    async with factory() as session:
        await ts.register_builtin_templates(session)

        # 获取详情
        template = await ts.get_template(session, "claude-code")
        assert template.name == "claude-code"
        assert template.connect_type == "shell"

        # 获取不存在的模板
        with pytest.raises(TemplateNotFoundError):
            await ts.get_template(session, "nonexistent")

    await close_db()
