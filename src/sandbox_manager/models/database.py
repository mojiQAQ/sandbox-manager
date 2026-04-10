"""数据库模型 - SQLAlchemy ORM 定义

两个核心表:
- Template: 模板（沙盒蓝图），存储构建配置和元数据
- ActiveSandbox: 活跃沙盒实例，关联到 Template
"""

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """ORM 基类"""

    pass


class Template(Base):
    """模板表 - 存储模板配置和构建状态"""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    base_image: Mapped[str] = mapped_column(String(200), nullable=False)
    docker_image: Mapped[str] = mapped_column(String(200), nullable=False)
    docker_image_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entrypoint: Mapped[str] = mapped_column(Text, default="[]")  # JSON 序列化的 list
    env: Mapped[str] = mapped_column(Text, default="{}")  # JSON 序列化的 dict
    connect_type: Mapped[str] = mapped_column(String(20), default="shell")
    connect_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ports: Mapped[str] = mapped_column(Text, default="{}")  # JSON 序列化的 dict
    install_commands: Mapped[str] = mapped_column(Text, default="[]")  # JSON 序列化的 list
    status: Mapped[str] = mapped_column(String(20), default="unbuilt")
    build_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="builtin")
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关联的沙盒
    sandboxes: Mapped[list["ActiveSandbox"]] = relationship(
        "ActiveSandbox",
        back_populates="template",
        cascade="all",
    )

    # --- JSON 序列化辅助方法 ---

    def get_entrypoint(self) -> list[str]:
        return json.loads(self.entrypoint) if self.entrypoint else []

    def set_entrypoint(self, value: list[str]) -> None:
        self.entrypoint = json.dumps(value)

    def get_env(self) -> dict[str, str]:
        return json.loads(self.env) if self.env else {}

    def set_env(self, value: dict[str, str]) -> None:
        self.env = json.dumps(value)

    def get_ports(self) -> dict[str, int]:
        return json.loads(self.ports) if self.ports else {}

    def set_ports(self, value: dict[str, int]) -> None:
        self.ports = json.dumps(value)

    def get_install_commands(self) -> list[str]:
        return json.loads(self.install_commands) if self.install_commands else []

    def set_install_commands(self, value: list[str]) -> None:
        self.install_commands = json.dumps(value)


class ActiveSandbox(Base):
    """活跃沙盒表 - 记录正在运行的沙盒实例"""

    __tablename__ = "active_sandboxes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    image: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    docker_container_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 关联的模板
    template: Mapped[Template | None] = relationship(
        "Template",
        back_populates="sandboxes",
    )
