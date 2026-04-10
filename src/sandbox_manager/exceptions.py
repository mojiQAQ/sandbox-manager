"""异常层级 - 所有自定义异常的定义

分为两大类:
- 用户错误: 返回明确提示信息，引导用户下一步操作
- 系统错误: 返回简洁描述，详细信息记录在日志中
"""


class SandboxManagerError(Exception):
    """基础异常"""

    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


# --- 用户错误 (4xx) ---


class NotFoundError(SandboxManagerError):
    """资源不存在"""

    pass


class TemplateNotFoundError(NotFoundError):
    """模板不存在"""

    def __init__(self, name: str):
        super().__init__(
            message=f"模板 '{name}' 不存在",
            detail="请使用 GET /api/v1/templates 查看可用模板列表",
        )
        self.template_name = name


class SandboxNotFoundError(NotFoundError):
    """沙盒不存在"""

    def __init__(self, sandbox_id: str):
        super().__init__(
            message=f"沙盒 '{sandbox_id}' 不存在",
            detail="请使用 GET /api/v1/sandboxes 查看活跃沙盒列表",
        )
        self.sandbox_id = sandbox_id


class TemplateNotReadyError(SandboxManagerError):
    """模板未构建"""

    def __init__(self, name: str, status: str):
        super().__init__(
            message=f"模板 '{name}' 状态为 '{status}'，无法使用",
            detail=f"请先执行 POST /api/v1/templates/{name}/build 构建模板",
        )
        self.template_name = name
        self.status = status


class TemplateAlreadyExistsError(SandboxManagerError):
    """模板已存在"""

    def __init__(self, name: str):
        super().__init__(
            message=f"模板 '{name}' 已存在",
            detail="如需重新构建，请先删除现有模板或直接触发构建",
        )
        self.template_name = name


class TemplateBuildInProgressError(SandboxManagerError):
    """模板正在构建中"""

    def __init__(self, name: str):
        super().__init__(
            message=f"模板 '{name}' 正在构建中，请勿重复触发",
            detail=f"请使用 GET /api/v1/templates/{name}/build-status 查看构建进度",
        )
        self.template_name = name


class InvalidTemplateConfigError(SandboxManagerError):
    """模板配置无效"""

    def __init__(self, message: str, field: str | None = None):
        detail = f"配置字段 '{field}' 有误" if field else None
        super().__init__(message=message, detail=detail)
        self.field = field


class SandboxStateError(SandboxManagerError):
    """沙盒状态不允许此操作"""

    def __init__(self, sandbox_id: str, current_state: str, expected_states: list[str]):
        expected = ", ".join(expected_states)
        super().__init__(
            message=f"沙盒 '{sandbox_id}' 当前状态为 '{current_state}'，不允许此操作",
            detail=f"此操作要求沙盒状态为: {expected}",
        )
        self.sandbox_id = sandbox_id
        self.current_state = current_state
        self.expected_states = expected_states


# --- 系统错误 (5xx) ---


class OpenSandboxConnectionError(SandboxManagerError):
    """无法连接到 OpenSandbox server"""

    def __init__(self, url: str, cause: str | None = None):
        msg = f"无法连接到 OpenSandbox server: {url}"
        if cause:
            msg += f" ({cause})"
        super().__init__(
            message=msg,
            detail="请确认 OpenSandbox server 已启动且地址配置正确",
        )
        self.url = url


class DockerError(SandboxManagerError):
    """Docker 操作失败"""

    def __init__(self, operation: str, cause: str | None = None):
        msg = f"Docker 操作失败: {operation}"
        if cause:
            msg += f" ({cause})"
        super().__init__(message=msg, detail="请确认 Docker daemon 已启动")
        self.operation = operation


class TemplateBuildError(SandboxManagerError):
    """模板构建失败"""

    def __init__(self, name: str, step: int, command: str, exit_code: int, stderr: str):
        super().__init__(
            message=f"模板 '{name}' 构建失败: 第 {step} 步命令执行失败 (exit code: {exit_code})",
            detail=f"失败命令: {command}\n错误输出: {stderr}",
        )
        self.template_name = name
        self.step = step
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
