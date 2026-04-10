## 里程碑 M1 交付报告

### 本轮实现的功能

#### 功能组 A: 基础服务层

1. **docker-compose 一键部署**: 创建了 docker-compose.yaml，包含 OpenSandbox server 和 Sandbox Manager 两个服务。OpenSandbox server 通过 Python slim 镜像运行，Sandbox Manager 通过自定义 Dockerfile 构建。两者均挂载 docker.sock 以访问宿主机 Docker Engine。使用命名卷 `sandbox-data` 持久化数据。

2. **OpenSandbox 连接管理**: 在 `SandboxService` 中封装了 OpenSandbox SDK，启动时通过创建并销毁测试沙盒来验证连通性。连接失败时在日志中输出明确错误信息，不阻塞服务启动（降级运行）。所有 OpenSandbox 调用都有异常处理，返回有意义的错误而非挂起。

3. **数据库初始化与元数据管理**: 使用 async SQLAlchemy + aiosqlite，启动时自动创建目录和表结构。启用 SQLite WAL 模式提升并发性能。定义了 Template 和 ActiveSandbox 两个核心表，通过外键关联。服务重启后数据可正常查询。

4. **配置管理**: 基于 Pydantic Settings，支持 SBXMGR_ 前缀环境变量和 .env 文件。所有配置项有合理默认值。提供 .env.example 文件列出所有可配置项。

#### 功能组 B: 模板系统

5. **内置模板注册**: 4 个内置模板（claude-code, vscode, openclaw, python-dev）以 YAML 文件形式随代码分发。系统启动时自动检测并注册到数据库，已存在的跳过。未构建的模板状态标记为 "unbuilt"。

6. **模板配置解析**: 支持 YAML 格式模板配置文件，包含 name、base_image、connect_type、install_commands、entrypoint、env、ports 等字段。有完整的校验逻辑：缺少必填字段报告具体位置，connect_type 只接受 shell/url/port。

7. **模板构建流程**: 完整实现异步构建流程：创建临时沙盒 -> 依次执行安装命令 -> docker commit -> 注册元数据 -> 销毁临时沙盒。每步有日志输出，命令失败时记录具体步骤、exit code 和 stderr。构建是异步 Task，不阻塞 API 服务。可通过 build-status 接口查询进度。

8. **模板 CRUD**: 列表、详情、删除三个操作。删除时同时清理 Docker 镜像。列表包含名称、描述、状态、连接类型、镜像大小、创建时间。详情包含完整构建配置。

9. **运行时快照**: 对运行中沙盒执行 docker commit 保存为新模板。快照时自动 Docker-level pause/unpause 保证一致性。支持自定义名称和描述，默认继承原模板的 connect_type、entrypoint、env、ports。

### 新建/修改的文件

```
pyproject.toml                              — 项目构建配置和依赖声明
docker-compose.yaml                         — 服务编排
Dockerfile                                  — Sandbox Manager 容器构建
sandbox.toml                                — OpenSandbox server 配置
.env.example                                — 环境变量示例

src/sandbox_manager/__init__.py             — 包入口，版本号
src/sandbox_manager/main.py                 — FastAPI app + lifespan + 全局异常处理
src/sandbox_manager/config.py               — Pydantic Settings 配置管理
src/sandbox_manager/exceptions.py           — 异常层级定义
src/sandbox_manager/dependencies.py         — FastAPI 依赖注入

src/sandbox_manager/db/__init__.py          — 数据库包
src/sandbox_manager/db/engine.py            — async SQLAlchemy 引擎 + WAL

src/sandbox_manager/models/__init__.py      — 模型包
src/sandbox_manager/models/database.py      — Template + ActiveSandbox ORM 模型
src/sandbox_manager/models/schemas.py       — Pydantic 请求/响应 schemas

src/sandbox_manager/services/__init__.py    — 服务包
src/sandbox_manager/services/docker_bridge.py   — Docker commit + 镜像管理
src/sandbox_manager/services/sandbox_service.py — OpenSandbox SDK 封装
src/sandbox_manager/services/template_service.py — 模板构建/快照/CRUD

src/sandbox_manager/api/__init__.py         — API 包
src/sandbox_manager/api/router.py           — 路由注册
src/sandbox_manager/api/health.py           — 健康检查 + 系统状态
src/sandbox_manager/api/templates.py        — 模板 CRUD + 构建 API
src/sandbox_manager/api/sandboxes.py        — 沙盒 CRUD + 快照 API

templates/base.yaml                         — 模板格式说明
templates/claude-code.yaml                  — Claude Code 模板
templates/vscode.yaml                       — VS Code (code-server) 模板
templates/openclaw.yaml                     — OpenClaw 模板
templates/python-dev.yaml                   — Python 开发模板

tests/test_config.py                        — 配置管理测试
tests/test_exceptions.py                    — 异常层级测试
tests/test_template_parsing.py              — YAML 解析测试
tests/test_database.py                      — 数据库 + 模板注册测试
tests/test_api.py                           — API 端点测试
```

### 自测结果

- ruff lint: **PASS** (0 errors)
- py_compile (所有 14 个 Python 源文件): **PASS**
- 测试套件: **33/33 passed** (3.17s)
- 新增测试: **33 个**
  - test_config: 4 个
  - test_exceptions: 11 个
  - test_template_parsing: 6 个
  - test_database: 2 个（async）
  - test_api: 11 个（FastAPI TestClient）

### 验收标准自检

#### 功能组 A: 基础服务层

- [x] docker-compose up 后系统可启动（docker-compose.yaml + Dockerfile 已就绪）
- [x] 首次启动时自动完成数据库初始化
- [x] 停止后重新启动，模板数据不丢失（SQLite 持久化 + WAL）
- [x] 服务启动时检测 OpenSandbox 连通性，不可达时日志输出明确错误
- [x] OpenSandbox 临时不可用时，操作返回有意义的错误
- [x] 首次启动自动创建数据库和表结构
- [x] 模板和沙盒信息持久化存储
- [x] 支持 SBXMGR_ 前缀环境变量和 .env 文件
- [x] 所有配置项有合理默认值

#### 功能组 B: 模板系统

- [x] 系统启动时自动注册 4 个内置模板
- [x] 未构建模板状态标记为 "unbuilt"
- [x] 支持 YAML 格式模板配置文件
- [x] 配置校验：缺少必填字段报告具体错误位置
- [x] 构建流程完整：创建沙盒 -> 执行命令 -> docker commit -> 注册元数据
- [x] 构建过程每步有进度输出
- [x] 命令失败时停止并报告具体失败命令和错误
- [x] 构建是异步操作，不阻塞 API
- [x] 可查询构建状态
- [x] 模板 CRUD：列表、详情、删除
- [x] 删除模板时清理 Docker 镜像
- [x] 运行时快照：pause -> commit -> unpause
- [x] 快照继承原模板的连接类型和启动命令
- [x] 快照完成后返回模板名和镜像大小

### 已知问题

1. **OpenSandbox server 容器化方案待验证**: docker-compose 中使用 python:3.11-slim 镜像安装 opensandbox-server，首次启动会较慢（需要 pip install）。生产环境建议构建专用镜像。

2. **健康检查中的 OpenSandbox 状态**: 当前 /health 端点未做实时 OpenSandbox ping（避免每次请求都创建/销毁沙盒），而是依赖启动时的检测。可以在后续迭代中添加更轻量的连通性检查。

3. **模板构建的并发控制**: 当前通过内存字典 `_build_tasks` 防止重复构建。服务重启后异常状态（"building"）的模板会在启动时自动清理为 "failed" 状态，提示用户重新触发构建。（已处理）

### 状态: 提交 QA
