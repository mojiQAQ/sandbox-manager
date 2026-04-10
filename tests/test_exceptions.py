"""测试: 异常层级"""

from sandbox_manager.exceptions import (
    DockerError,
    OpenSandboxConnectionError,
    SandboxManagerError,
    SandboxNotFoundError,
    SandboxStateError,
    TemplateAlreadyExistsError,
    TemplateBuildError,
    TemplateBuildInProgressError,
    TemplateNotFoundError,
    TemplateNotReadyError,
)


def test_base_exception():
    """基础异常应包含 message 和 detail"""
    e = SandboxManagerError("测试消息", detail="详细信息")
    assert e.message == "测试消息"
    assert e.detail == "详细信息"
    assert str(e) == "测试消息"


def test_template_not_found():
    """模板不存在异常应包含模板名和引导信息"""
    e = TemplateNotFoundError("claude-code")
    assert "claude-code" in e.message
    assert e.template_name == "claude-code"
    assert e.detail is not None


def test_sandbox_not_found():
    """沙盒不存在异常应包含沙盒 ID"""
    e = SandboxNotFoundError("abc-123")
    assert "abc-123" in e.message
    assert e.sandbox_id == "abc-123"


def test_template_not_ready():
    """模板未就绪异常应包含当前状态"""
    e = TemplateNotReadyError("claude-code", "unbuilt")
    assert "unbuilt" in e.message
    assert e.status == "unbuilt"


def test_template_already_exists():
    """模板已存在异常"""
    e = TemplateAlreadyExistsError("my-template")
    assert "my-template" in e.message


def test_template_build_in_progress():
    """模板构建中异常"""
    e = TemplateBuildInProgressError("claude-code")
    assert "claude-code" in e.message


def test_sandbox_state_error():
    """沙盒状态不允许操作异常"""
    e = SandboxStateError("abc-123", "stopped", ["running", "paused"])
    assert "stopped" in e.message
    assert e.expected_states == ["running", "paused"]


def test_opensandbox_connection_error():
    """OpenSandbox 连接异常"""
    e = OpenSandboxConnectionError("http://localhost:8080", "connection refused")
    assert "localhost:8080" in e.message
    assert "connection refused" in e.message


def test_docker_error():
    """Docker 操作异常"""
    e = DockerError("commit 容器", "container not found")
    assert "commit" in e.message


def test_template_build_error():
    """模板构建失败异常"""
    e = TemplateBuildError("claude-code", 2, "npm install", 1, "not found")
    assert e.step == 2
    assert e.exit_code == 1
    assert "npm install" in e.detail
