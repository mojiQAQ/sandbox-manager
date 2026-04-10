"""Pydantic Schemas - API 请求和响应模型

所有 API 响应的 key 使用英文，description 使用中文。
"""

from datetime import datetime

from pydantic import BaseModel, Field

# --- 通用 ---


class ApiResponse(BaseModel):
    """统一 API 响应格式"""

    success: bool = True
    message: str = ""
    data: dict | list | None = None


class ErrorResponse(BaseModel):
    """错误响应"""

    success: bool = False
    message: str
    detail: str | None = None


# --- 模板 ---


class TemplateBase(BaseModel):
    """模板基础字段"""

    name: str = Field(..., description="模板名称，如 claude-code")
    description: str = Field(default="", description="模板描述")
    base_image: str = Field(..., description="基础 Docker 镜像")
    connect_type: str = Field(default="shell", description="连接类型: shell | url | port")
    connect_port: int | None = Field(default=None, description="连接端口（url/port 类型时使用）")
    entrypoint: list[str] = Field(default_factory=list, description="容器启动命令")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    ports: dict[str, int] = Field(default_factory=dict, description="端口映射")
    install_commands: list[str] = Field(default_factory=list, description="安装命令列表")


class TemplateListItem(BaseModel):
    """模板列表项"""

    id: str
    name: str
    description: str
    status: str = Field(description="状态: unbuilt | building | ready | failed")
    source: str = Field(description="来源: builtin | custom | snapshot")
    connect_type: str
    docker_image: str
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime


class TemplateDetail(TemplateListItem):
    """模板详情"""

    base_image: str
    docker_image_id: str | None = None
    entrypoint: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    ports: dict[str, int] = Field(default_factory=dict)
    install_commands: list[str] = Field(default_factory=list)
    connect_port: int | None = None
    build_error: str | None = None


class TemplateBuildStatus(BaseModel):
    """模板构建状态"""

    name: str
    status: str
    build_error: str | None = None


# --- 沙盒 ---


class CreateSandboxRequest(BaseModel):
    """创建沙盒请求"""

    template_name: str | None = Field(default=None, description="模板名称（与 image 二选一）")
    image: str | None = Field(
        default=None, description="直接指定 Docker 镜像（与 template_name 二选一）"
    )
    name: str | None = Field(default=None, description="沙盒自定义名称")
    env: dict[str, str] = Field(default_factory=dict, description="额外环境变量")


class SandboxListItem(BaseModel):
    """沙盒列表项"""

    id: str
    name: str | None = None
    template_name: str | None = None
    status: str = Field(description="状态: running | paused | stopped")
    image: str
    created_at: datetime
    connect_type: str | None = None
    docker_container_name: str


class SandboxDetail(SandboxListItem):
    """沙盒详情"""

    template_id: str | None = None


class ConnectInfo(BaseModel):
    """沙盒连接信息

    根据 connect_type 不同，字段有所区别:
    - shell: command 包含 docker exec 命令
    - url: url 包含访问地址，port 包含端口号
    - port: ports 包含端口映射列表
    """

    connect_type: str = Field(description="连接类型: shell | url | port")
    sandbox_id: str = Field(description="沙盒 ID")
    container_name: str = Field(description="Docker 容器名")
    status: str = Field(description="沙盒当前状态")
    # shell 类型
    command: str | None = Field(default=None, description="shell 连接命令")
    # url 类型
    url: str | None = Field(default=None, description="访问 URL")
    port: int | None = Field(default=None, description="主连接端口")
    # port 类型
    ports: list[dict] | None = Field(default=None, description="端口映射列表")
    # 提示信息
    message: str | None = Field(default=None, description="提示信息")


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""

    success: bool = True
    total: int = Field(description="总数")
    deleted: int = Field(description="成功删除数")
    failed: int = Field(description="失败数")
    message: str = ""


class SaveTemplateRequest(BaseModel):
    """快照保存为模板请求"""

    name: str = Field(
        ...,
        description="新模板名称，只允许小写字母、数字、连字符和下划线，必须以字母或数字开头",
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        min_length=1,
        max_length=100,
    )
    description: str = Field(default="", description="模板描述")
    connect_type: str | None = Field(default=None, description="连接类型，默认继承原模板")
    entrypoint: list[str] | None = Field(default=None, description="启动命令，默认继承原模板")


# --- 系统状态 ---


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "ok"
    version: str
    opensandbox_connected: bool
    database_ok: bool


class SystemStatus(BaseModel):
    """系统状态"""

    api_running: bool = True
    opensandbox_connected: bool
    active_sandboxes: int
    built_templates: int
    total_templates: int
