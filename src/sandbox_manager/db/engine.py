"""异步 SQLAlchemy 引擎 - SQLite + WAL 模式

提供:
- 异步引擎和 session factory
- 数据库初始化（创建目录、创建表、启用 WAL 模式）
- 全局 session 获取函数
"""

import logging
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sandbox_manager.config import settings

logger = logging.getLogger(__name__)

# 异步引擎（延迟初始化，在 init_db 中创建）
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    """获取或创建异步引擎"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        # 为底层同步引擎设置 WAL 模式
        @event.listens_for(_engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取或创建 session factory"""
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_db() -> None:
    """初始化数据库 - 创建目录和表结构"""
    from sandbox_manager.models.database import Base

    # 确保数据库目录存在
    db_dir = settings.database_dir
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    logger.info("数据库目录已就绪: %s", db_dir)

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 验证 WAL 模式
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        logger.info("数据库初始化完成，journal_mode=%s", mode)


async def close_db() -> None:
    """关闭数据库连接"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("数据库连接已关闭")


async def get_session() -> AsyncSession:
    """获取一个新的异步 session（用于 FastAPI 依赖注入）"""
    factory = _get_session_factory()
    async with factory() as session:
        yield session  # type: ignore[misc]
