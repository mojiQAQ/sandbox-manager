"""配置管理 - 基于 Pydantic Settings，支持环境变量和 .env 文件

优先级: 默认值 < .env 文件 < 环境变量 (SBXMGR_ 前缀)
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Sandbox Manager 全局配置"""

    model_config = SettingsConfigDict(
        env_prefix="SBXMGR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- OpenSandbox 连接 ---
    opensandbox_host: str = "localhost"
    opensandbox_port: int = 8080
    opensandbox_api_key: str = ""
    opensandbox_protocol: str = "http"

    # --- 数据库 ---
    database_path: str = "data/sandbox_manager.db"

    # --- Docker ---
    docker_image_prefix: str = "sbxmgr"

    # --- 沙盒默认配置 ---
    default_timeout_minutes: int = 60

    # --- 服务 ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # --- 外部访问地址（用于替换 OpenSandbox 返回的内部域名）---
    external_host: str = ""

    # --- 内置模板路径 ---
    builtin_templates_dir: str = "templates"

    @property
    def opensandbox_url(self) -> str:
        """OpenSandbox server 完整 URL"""
        return f"{self.opensandbox_protocol}://{self.opensandbox_host}:{self.opensandbox_port}"

    @property
    def database_url(self) -> str:
        """SQLite 异步连接 URL"""
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def database_dir(self) -> Path:
        """数据库文件所在目录"""
        return Path(self.database_path).parent


# 全局单例
settings = Settings()
