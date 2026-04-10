"""TemplateService - 模板管理核心服务

负责:
- 内置模板注册: 从 YAML 配置文件加载内置模板到数据库
- 模板配置解析: 解析和校验 YAML 格式的模板配置
- 模板构建: 创建临时沙盒 -> 执行安装命令 -> docker commit -> 注册元数据
- 模板 CRUD: 列表、详情、删除
- 运行时快照: 对运行中沙盒执行 docker commit 保存为模板
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sandbox_manager.config import settings
from sandbox_manager.exceptions import (
    InvalidTemplateConfigError,
    TemplateAlreadyExistsError,
    TemplateBuildError,
    TemplateBuildInProgressError,
    TemplateNotFoundError,
)
from sandbox_manager.models.database import ActiveSandbox, Template
from sandbox_manager.services.docker_bridge import DockerBridge
from sandbox_manager.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)

# 必填字段
REQUIRED_TEMPLATE_FIELDS = ["name", "base_image"]


class TemplateService:
    """模板管理服务"""

    def __init__(
        self,
        sandbox_service: SandboxService,
        docker_bridge: DockerBridge,
    ) -> None:
        self._sandbox_service = sandbox_service
        self._docker_bridge = docker_bridge
        # 正在进行中的构建任务
        self._build_tasks: dict[str, asyncio.Task] = {}

    # --- 模板配置解析 ---

    def parse_template_yaml(self, yaml_path: str | Path) -> dict:
        """解析 YAML 模板配置文件

        Returns:
            解析后的配置字典

        Raises:
            InvalidTemplateConfigError: 配置无效
        """
        path = Path(yaml_path)
        if not path.exists():
            raise InvalidTemplateConfigError(f"模板配置文件不存在: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise InvalidTemplateConfigError(f"YAML 解析失败: {e}")

        if not isinstance(config, dict):
            raise InvalidTemplateConfigError("模板配置必须是一个 YAML 映射")

        # 校验必填字段
        for field in REQUIRED_TEMPLATE_FIELDS:
            if field not in config:
                raise InvalidTemplateConfigError(
                    f"缺少必填字段: {field}",
                    field=field,
                )

        # 校验 connect_type
        connect_type = config.get("connect_type", "shell")
        if connect_type not in ("shell", "url", "port"):
            raise InvalidTemplateConfigError(
                f"connect_type 必须是 shell/url/port，当前为: {connect_type}",
                field="connect_type",
            )

        # 规范化默认值
        config.setdefault("description", "")
        config.setdefault("connect_type", "shell")
        config.setdefault("connect_port", None)
        config.setdefault("entrypoint", ["tail", "-f", "/dev/null"])
        config.setdefault("env", {})
        config.setdefault("ports", {})
        config.setdefault("install_commands", [])

        return config

    # --- 启动清理 ---

    async def cleanup_stale_builds(self, session: AsyncSession) -> int:
        """清理异常状态的模板（服务重启后 "building" 状态的模板应恢复为 "failed"）

        Returns:
            清理的模板数量
        """
        result = await session.execute(
            select(Template).where(Template.status == "building")
        )
        stale = list(result.scalars().all())
        for t in stale:
            t.status = "failed"
            t.build_error = "服务重启导致构建中断，请重新触发构建"
            logger.warning("清理异常构建状态: %s", t.name)

        if stale:
            await session.commit()

        return len(stale)

    # --- 内置模板注册 ---

    async def register_builtin_templates(self, session: AsyncSession) -> int:
        """注册内置模板（从 YAML 配置文件加载到数据库）

        只注册数据库中不存在的模板，已存在的跳过。

        Returns:
            新注册的模板数量
        """
        templates_dir = Path(settings.builtin_templates_dir)
        if not templates_dir.exists():
            logger.warning("内置模板目录不存在: %s", templates_dir)
            return 0

        registered = 0
        for yaml_file in sorted(templates_dir.glob("*.yaml")):
            # 跳过 base.yaml（它是基础配置，不是模板）
            if yaml_file.name == "base.yaml":
                continue

            try:
                config = self.parse_template_yaml(yaml_file)
            except InvalidTemplateConfigError as e:
                logger.error("跳过无效的模板配置 %s: %s", yaml_file.name, e.message)
                continue

            # 检查是否已存在
            result = await session.execute(
                select(Template).where(Template.name == config["name"])
            )
            if result.scalar_one_or_none() is not None:
                logger.debug("内置模板已存在，跳过: %s", config["name"])
                continue

            # 创建模板记录
            template = Template(
                id=str(uuid.uuid4()),
                name=config["name"],
                description=config.get("description", ""),
                base_image=config["base_image"],
                docker_image=self._docker_bridge.get_image_tag(config["name"]),
                entrypoint=json.dumps(config.get("entrypoint", [])),
                env=json.dumps(config.get("env", {})),
                connect_type=config.get("connect_type", "shell"),
                connect_port=config.get("connect_port"),
                ports=json.dumps(config.get("ports", {})),
                install_commands=json.dumps(config.get("install_commands", [])),
                status="unbuilt",
                source="builtin",
            )
            session.add(template)
            registered += 1
            logger.info("注册内置模板: %s", config["name"])

        if registered > 0:
            await session.commit()

        logger.info("内置模板注册完成: 新注册 %d 个", registered)
        return registered

    # --- 模板 CRUD ---

    async def list_templates(self, session: AsyncSession) -> list[Template]:
        """获取所有模板"""
        result = await session.execute(
            select(Template).order_by(Template.created_at)
        )
        return list(result.scalars().all())

    async def get_template(self, session: AsyncSession, name: str) -> Template:
        """获取模板详情

        Raises:
            TemplateNotFoundError: 模板不存在
        """
        result = await session.execute(
            select(Template).where(Template.name == name)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise TemplateNotFoundError(name)
        return template

    async def delete_template(self, session: AsyncSession, name: str) -> None:
        """删除模板（同时清理 Docker 镜像）

        Raises:
            TemplateNotFoundError: 模板不存在
        """
        template = await self.get_template(session, name)

        # 清理 Docker 镜像
        if template.docker_image:
            try:
                await self._docker_bridge.remove_image(template.docker_image, force=True)
            except Exception:
                logger.warning("清理 Docker 镜像失败: %s", template.docker_image, exc_info=True)

        await session.delete(template)
        await session.commit()
        logger.info("模板已删除: %s", name)

    # --- 模板构建 ---

    def get_build_status(self, name: str) -> str | None:
        """获取构建任务状态

        Returns:
            "building" 如果正在构建，否则 None
        """
        task = self._build_tasks.get(name)
        if task and not task.done():
            return "building"
        return None

    async def build_template(
        self,
        session: AsyncSession,
        name: str,
    ) -> None:
        """触发模板构建（异步任务）

        构建流程:
        1. 检查模板是否存在
        2. 检查是否已在构建中
        3. 启动异步构建任务

        Raises:
            TemplateNotFoundError: 模板不存在
            TemplateBuildInProgressError: 正在构建中
        """
        template = await self.get_template(session, name)

        # 检查是否正在构建
        if self.get_build_status(name) == "building":
            raise TemplateBuildInProgressError(name)

        # 更新状态为 building
        template.status = "building"
        template.build_error = None
        await session.commit()

        # 启动异步构建任务
        task = asyncio.create_task(self._do_build(name))
        self._build_tasks[name] = task

    async def _do_build(self, name: str) -> None:
        """执行实际的模板构建流程

        1. 通过 OpenSandbox SDK 创建临时沙盒（使用 base_image）
        2. 依次执行 install_commands
        3. 通过 Docker Bridge 执行 docker commit
        4. 销毁临时沙盒
        5. 更新数据库中的模板状态
        """
        from sandbox_manager.db.engine import _get_session_factory

        session_factory = _get_session_factory()

        async with session_factory() as session:
            # 重新加载模板（新 session）
            result = await session.execute(
                select(Template).where(Template.name == name)
            )
            template = result.scalar_one_or_none()
            if template is None:
                logger.error("构建任务找不到模板: %s", name)
                return

            sandbox = None
            try:
                # 第 1 步: 创建临时沙盒
                logger.info("[%s] 开始构建，基础镜像: %s", name, template.base_image)
                sandbox = await self._sandbox_service.create_sandbox(
                    image=template.base_image,
                    entrypoint=["tail", "-f", "/dev/null"],
                    timeout_minutes=30,  # 构建超时 30 分钟
                )
                logger.info("[%s] 临时沙盒已创建: %s", name, sandbox.id)

                # 第 2 步: 依次执行安装命令
                install_commands = template.get_install_commands()
                total = len(install_commands)
                for i, cmd in enumerate(install_commands, 1):
                    logger.info("[%s] 执行命令 (%d/%d): %s", name, i, total, cmd)
                    exit_code, stdout, stderr = await self._sandbox_service.run_command(
                        sandbox,
                        cmd,
                        timeout_seconds=600,  # 单条命令超时 10 分钟
                    )

                    if stdout:
                        logger.info("[%s] stdout: %s", name, stdout[:500])
                    if stderr:
                        logger.warning("[%s] stderr: %s", name, stderr[:500])

                    if exit_code != 0:
                        error = TemplateBuildError(
                            name=name,
                            step=i,
                            command=cmd,
                            exit_code=exit_code,
                            stderr=stderr[:2000],
                        )
                        template.status = "failed"
                        err_msg = f"第 {i} 步失败 (exit code {exit_code}): {cmd}"
                        template.build_error = f"{err_msg}\n{stderr[:2000]}"
                        await session.commit()
                        logger.error("[%s] 构建失败: %s", name, error.message)
                        return

                # 第 3 步: docker commit
                logger.info("[%s] 所有命令执行完成，开始 docker commit", name)
                image_id, size_bytes = await self._docker_bridge.commit_container(
                    sandbox_id=sandbox.id,
                    template_name=name,
                    pause=True,
                )

                # 第 4 步: 更新模板元数据
                template.status = "ready"
                template.docker_image_id = image_id
                template.size_bytes = size_bytes
                template.build_error = None
                await session.commit()

                logger.info(
                    "[%s] 构建成功: image_id=%s, size=%s bytes",
                    name,
                    image_id[:20],
                    size_bytes,
                )

            except TemplateBuildError:
                # 已在上面处理过
                pass
            except Exception as e:
                logger.error("[%s] 构建异常: %s", name, str(e), exc_info=True)
                template.status = "failed"
                template.build_error = str(e)[:2000]
                await session.commit()
            finally:
                # 第 5 步: 销毁临时沙盒
                if sandbox is not None:
                    try:
                        await self._sandbox_service.kill_sandbox(sandbox)
                        logger.info("[%s] 临时沙盒已销毁", name)
                    except Exception:
                        logger.warning("[%s] 销毁临时沙盒失败", name, exc_info=True)

                # 清理构建任务记录
                self._build_tasks.pop(name, None)

    # --- 运行时快照 ---

    async def save_sandbox_as_template(
        self,
        session: AsyncSession,
        sandbox_id: str,
        name: str,
        description: str = "",
        connect_type: str | None = None,
        entrypoint: list[str] | None = None,
    ) -> Template:
        """将运行中的沙盒快照保存为模板

        流程:
        1. 查找沙盒记录
        2. 检查模板名是否已存在
        3. Docker pause -> commit -> unpause
        4. 注册模板元数据

        Args:
            session: 数据库 session
            sandbox_id: 沙盒 ID
            name: 新模板名称
            description: 模板描述
            connect_type: 连接类型，默认继承原模板
            entrypoint: 启动命令，默认继承原模板

        Returns:
            新创建的 Template

        Raises:
            SandboxNotFoundError: 沙盒不存在
            TemplateAlreadyExistsError: 模板名已存在
        """
        from sandbox_manager.exceptions import SandboxNotFoundError

        # 查找沙盒
        result = await session.execute(
            select(ActiveSandbox).where(ActiveSandbox.id == sandbox_id)
        )
        sandbox = result.scalar_one_or_none()
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        # 检查模板名是否已存在
        result = await session.execute(
            select(Template).where(Template.name == name)
        )
        if result.scalar_one_or_none() is not None:
            raise TemplateAlreadyExistsError(name)

        # 获取原模板信息（用于继承配置）
        source_template = None
        if sandbox.template_id:
            result = await session.execute(
                select(Template).where(Template.id == sandbox.template_id)
            )
            source_template = result.scalar_one_or_none()

        # 执行 docker commit（内部会 pause/unpause）
        logger.info("快照沙盒 %s -> 模板 %s", sandbox_id, name)
        image_id, size_bytes = await self._docker_bridge.commit_container(
            sandbox_id=sandbox_id,
            template_name=name,
            pause=True,
        )

        # 确定配置（继承或覆盖）
        if connect_type is None and source_template:
            connect_type = source_template.connect_type
        if connect_type is None:
            connect_type = "shell"

        if entrypoint is None and source_template:
            final_entrypoint = source_template.get_entrypoint()
        elif entrypoint is not None:
            final_entrypoint = entrypoint
        else:
            final_entrypoint = ["tail", "-f", "/dev/null"]

        # 继承其他配置
        env = source_template.get_env() if source_template else {}
        ports = source_template.get_ports() if source_template else {}
        connect_port = source_template.connect_port if source_template else None

        # 创建模板记录
        template = Template(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            base_image=sandbox.image,
            docker_image=self._docker_bridge.get_image_tag(name),
            docker_image_id=image_id,
            entrypoint=json.dumps(final_entrypoint),
            env=json.dumps(env),
            connect_type=connect_type,
            connect_port=connect_port,
            ports=json.dumps(ports),
            install_commands="[]",  # 快照模板没有安装命令
            status="ready",
            source="snapshot",
            size_bytes=size_bytes,
        )
        session.add(template)
        await session.commit()

        logger.info(
            "快照保存成功: 模板=%s, image_id=%s, size=%d bytes",
            name,
            image_id[:20],
            size_bytes,
        )
        return template
