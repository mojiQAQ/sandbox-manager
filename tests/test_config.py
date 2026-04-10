"""测试: 配置管理"""

import os

from sandbox_manager.config import Settings


def test_default_settings():
    """默认配置值应正确"""
    s = Settings()
    assert s.opensandbox_host == "localhost"
    assert s.opensandbox_port == 8080
    assert s.opensandbox_protocol == "http"
    assert s.docker_image_prefix == "sbxmgr"
    assert s.default_timeout_minutes == 60
    assert s.port == 8000


def test_opensandbox_url():
    """opensandbox_url 属性应正确拼接"""
    s = Settings()
    assert s.opensandbox_url == "http://localhost:8080"


def test_database_url():
    """database_url 属性应正确生成"""
    s = Settings()
    assert s.database_url.startswith("sqlite+aiosqlite:///")


def test_env_override():
    """环境变量应能覆盖默认值"""
    os.environ["SBXMGR_OPENSANDBOX_PORT"] = "9999"
    try:
        s = Settings()
        assert s.opensandbox_port == 9999
    finally:
        del os.environ["SBXMGR_OPENSANDBOX_PORT"]
