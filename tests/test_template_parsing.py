"""测试: 模板 YAML 解析"""

import tempfile

import pytest

from sandbox_manager.services.docker_bridge import DockerBridge
from sandbox_manager.services.sandbox_service import SandboxService
from sandbox_manager.services.template_service import TemplateService


@pytest.fixture
def template_service():
    return TemplateService(SandboxService(), DockerBridge())


def test_parse_valid_template(template_service):
    """应正确解析有效的模板 YAML"""
    config = template_service.parse_template_yaml("templates/claude-code.yaml")
    assert config["name"] == "claude-code"
    assert config["base_image"] == "ubuntu:22.04"
    assert config["connect_type"] == "shell"
    assert len(config["install_commands"]) == 4


def test_parse_all_builtin_templates(template_service):
    """应正确解析所有内置模板"""
    for name in ["claude-code", "vscode", "openclaw", "python-dev"]:
        config = template_service.parse_template_yaml(f"templates/{name}.yaml")
        assert config["name"] == name
        assert "base_image" in config


def test_parse_missing_file(template_service):
    """不存在的文件应报错"""
    from sandbox_manager.exceptions import InvalidTemplateConfigError

    with pytest.raises(InvalidTemplateConfigError, match="不存在"):
        template_service.parse_template_yaml("templates/nonexistent.yaml")


def test_parse_missing_required_field(template_service):
    """缺少必填字段应报错"""
    from sandbox_manager.exceptions import InvalidTemplateConfigError

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write("description: 'test'\n")
        f.flush()

        with pytest.raises(InvalidTemplateConfigError, match="name"):
            template_service.parse_template_yaml(f.name)


def test_parse_invalid_connect_type(template_service):
    """无效的 connect_type 应报错"""
    from sandbox_manager.exceptions import InvalidTemplateConfigError

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write("name: test\nbase_image: ubuntu:22.04\nconnect_type: invalid\n")
        f.flush()

        with pytest.raises(InvalidTemplateConfigError, match="connect_type"):
            template_service.parse_template_yaml(f.name)


def test_parse_defaults(template_service):
    """缺省字段应使用默认值"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write("name: minimal\nbase_image: alpine:latest\n")
        f.flush()

        config = template_service.parse_template_yaml(f.name)
        assert config["connect_type"] == "shell"
        assert config["entrypoint"] == ["tail", "-f", "/dev/null"]
        assert config["env"] == {}
        assert config["ports"] == {}
        assert config["install_commands"] == []
