## QA 评审报告 -- 里程碑 M1

> 评审日期: 2026-04-09
> 评审人: QA Inspector
> 测试环境: macOS Darwin 24.5.0, OpenSandbox server localhost:8080, Sandbox Manager API localhost:9000

---

### 评分摘要

| 维度 | 分数 | 阈值 | 状态 |
|------|------|------|------|
| 功能完整性 | 8/10 | 7 | PASS |
| 可靠性 | 6/10 | 6 | PASS (临界) |
| 用户体验 | 6/10 | 6 | PASS (临界) |
| 代码质量 | 6/10 | 5 | PASS |

**里程碑结果: PASS (有条件通过)**

M1 核心功能（模板注册、构建、快照）均可正常工作，快照这个核心差异化功能经过端到端验证确认可靠。但在健康检查准确性、响应格式一致性、输入验证等方面存在需要修复的问题。建议在 M2 开始前修复所有中等严重度问题。

---

### 验收标准验证

#### 已通过的场景（之前 E2E 测试已验证）
- [x] PASS 场景 2: 日志显示 OpenSandbox 连接成功和 DB 初始化 -- 已验证
- [x] PASS 场景 4: 4 个内置模板注册为 "unbuilt" -- 已验证
- [x] PASS 场景 5: python-dev 构建成功 -- 已验证
- [x] PASS 场景 13: 删除模板会清理 Docker 镜像 -- 已验证

#### 本次测试的场景

**场景 11-12: 快照验证 (核心功能) -- PASS**
- 测试步骤:
  1. `POST /api/v1/sandboxes {"template_name":"python-dev"}` 创建沙盒 (id=48c17292)
  2. `docker exec sandbox-48c17292... apt-get install -y cowsay` 安装 cowsay
  3. `docker exec sandbox-48c17292... /usr/games/cowsay "hello"` 确认安装成功
  4. `POST /api/v1/sandboxes/{id}/save-template {"name":"python-dev-with-cowsay"}` 执行快照
  5. `POST /api/v1/sandboxes {"template_name":"python-dev-with-cowsay"}` 从快照模板创建新沙盒
  6. `docker exec sandbox-6fa2563c... /usr/games/cowsay "snapshot works!"` 确认 cowsay 可用
  7. `docker exec sandbox-6fa2563c... python3 -c "import numpy"` 确认原始依赖也保留
- 结果: 快照功能完整可靠。快照生成新模板，从新模板创建的沙盒中已安装的包和原始依赖都保留。
- 额外验证:
  - 快照模板的 source="snapshot", status="ready" 正确
  - 快照继承了原模板的 connect_type="shell" 和 entrypoint
  - 快照模板详情中 base_image 指向原始模板镜像

**场景 14: 构建失败错误处理 -- PASS**
- 测试步骤:
  1. 创建包含错误安装命令的模板 YAML (`apt-get install -y this-package-does-not-exist-at-all`)
  2. 重启服务让其注册
  3. `POST /api/v1/templates/bad-template/build` 触发构建
  4. 轮询 `GET /api/v1/templates/bad-template/build-status` 等待完成
- 结果: 构建失败后 status="failed"，build_error 内容为:
  ```
  第 2 步失败 (exit code 100): apt-get install -y this-package-does-not-exist-at-all
  E: Unable to locate package this-package-does-not-exist-at-all
  ```
- 评价: 错误信息包含步骤编号、exit code、失败命令和具体原因，对用户来说是可操作的。

**场景 15: OpenSandbox 断连错误处理 -- PARTIAL PASS**
- 测试步骤:
  1. `kill` OpenSandbox server 进程
  2. `POST /api/v1/sandboxes {"template_name":"python-dev"}` 尝试创建沙盒
  3. 检查 `/api/v1/health` 和 `/api/v1/status` 响应
  4. 重启 OpenSandbox server
- 结果:
  - 创建沙盒: 返回 HTTP 500，错误信息 "无法连接到 OpenSandbox server: http://localhost:8080 (Network connectivity error: All connection attempts failed)" -- PASS，错误信息明确
  - `/api/v1/health`: 返回 `opensandbox_connected: true` -- FAIL (见问题 #1)
  - `/api/v1/status`: 返回 `opensandbox_connected: true` -- FAIL (见问题 #2)

**场景 10: python-dev 模板详情完整性 -- PASS**
- `GET /api/v1/templates/python-dev` 返回完整信息:
  - name, description, status, source, connect_type, base_image 全部正确
  - docker_image, docker_image_id (SHA256), size_bytes (358MB) 都有值
  - install_commands 包含 2 条命令，与 YAML 配置一致
  - entrypoint, env, ports 都正确
  - build_error 为 null

**场景 3: 数据持久性 -- PASS**
- 测试步骤:
  1. 记录当前模板状态 (python-dev: ready, 其余 3 个: unbuilt)
  2. kill 并重启 Sandbox Manager 进程
  3. 重新查询模板列表
- 结果: 所有模板数据完全保留，python-dev 的 "ready" 状态和 size_bytes 值不变。

**场景 6-8: claude-code/vscode/openclaw 模板构建 -- SKIP**
- 跳过原因: 每个构建需要 5-10 分钟且需要下载外部依赖。python-dev 构建已验证过构建流程的正确性。

**场景 1: docker-compose 部署 -- SKIP**
- 跳过原因: 当前环境是手动启动的，docker-compose 容器化方案需要单独验证。

**场景 9: 4 个模板全部就绪 -- SKIP**
- 跳过原因: 依赖场景 6-8

#### 额外测试

- **从未构建模板创建沙盒**: HTTP 400, "模板 'claude-code' 状态为 'unbuilt'，请先构建模板" -- PASS
- **不提供 template_name 和 image**: HTTP 400, "必须指定 template_name 或 image" -- PASS
- **不存在的模板/沙盒**: 均返回 HTTP 404 -- PASS
- **重复快照名称**: HTTP 409, "模板 'xxx' 已存在" -- PASS
- **容器已手动删除后通过 API 删除沙盒**: 优雅处理，返回成功 -- PASS
- **快照不存在的沙盒**: HTTP 404, "沙盒 'xxx' 不存在" -- PASS

---

### 问题列表

#### 问题 #1: /health 端点不检测 OpenSandbox 实际连通性 [中等]
- **严重程度**: 中等
- **维度**: 可靠性
- **位置**: `src/sandbox_manager/api/health.py:38-39`
- **问题**: health 端点中 opensandbox_ok 被硬编码为 True，注释说"如果 API 能启动说明初始化时检查过了"。当 OpenSandbox server 宕机后，health 端点仍报告 `opensandbox_connected: true`。
- **预期**: health 端点应实时检测 OpenSandbox 连通性，或至少有一个轻量级的 ping 机制（例如检查 OpenSandbox 的 /health 端点）。
- **实际**: 硬编码返回 True，完全不检测。
- **证据**: 停止 OpenSandbox server 后，`curl localhost:9000/api/v1/health` 仍返回 `{"opensandbox_connected":true}`。
- **修复方向**: 对 OpenSandbox server 的 /health 端点发起 HTTP GET，设置短超时（1-2s）。如果 OpenSandbox SDK 没有 ping 方法，可以直接用 httpx/aiohttp 请求。

#### 问题 #2: /status 端点用 Docker 连通性替代 OpenSandbox 连通性 [中等]
- **严重程度**: 中等
- **维度**: 可靠性
- **位置**: `src/sandbox_manager/api/health.py:79`
- **问题**: status 端点中 `opensandbox_connected` 字段实际调用的是 `docker_bridge.check_docker()`，检测的是 Docker Engine 是否可用，而不是 OpenSandbox server。
- **预期**: 检查 OpenSandbox server 的可达性。
- **实际**: 检查 Docker Engine 的可达性。Docker Engine 正常运行但 OpenSandbox 宕机时返回错误结果。
- **证据**: 停止 OpenSandbox server 后 `curl localhost:9000/api/v1/status` 返回 `{"opensandbox_connected":true}`（因为 Docker 还在跑）。
- **修复方向**: 使用 `sandbox_service.check_connection()` 或者对 OpenSandbox HTTP 端点做一个轻量级检查（不建议每次都创建/销毁测试沙盒）。

#### 问题 #3: DockerBridge 中 async 方法实际执行同步阻塞 I/O [中等]
- **严重程度**: 中等
- **维度**: 代码质量
- **位置**: `src/sandbox_manager/services/docker_bridge.py` -- 全部 4 个 async 方法
- **问题**: `commit_container`、`get_image_info`、`remove_image`、`check_docker` 声明为 `async` 但没有使用任何 `await`。它们内部使用同步的 `docker.DockerClient` API，会阻塞 asyncio 事件循环。
- **预期**: 同步 I/O 操作应通过 `asyncio.to_thread()` 或 `loop.run_in_executor()` 包装，避免阻塞事件循环。
- **实际**: 直接在协程中调用同步方法，在 docker commit（耗时操作）期间，整个 API 服务可能对其他请求无响应。
- **证据**: 代码分析确认 4 个 async 函数均无 await 调用。
- **修复方向**: 将同步 Docker 操作包装在 `asyncio.to_thread()` 中。例如:
  ```python
  image = await asyncio.to_thread(container.commit, repository=repo, tag=tag)
  ```

#### 问题 #4: API 错误响应格式不统一 [轻微]
- **严重程度**: 轻微
- **维度**: 用户体验
- **位置**: `src/sandbox_manager/api/templates.py`, `src/sandbox_manager/api/sandboxes.py` 中使用 HTTPException 的地方
- **问题**: 产品规格要求"统一响应格式"。当前存在两种错误响应格式:
  - 通过全局异常处理器的: `{"success":false, "message":"...", "detail":"..."}`
  - 通过 HTTPException 抛出的: `{"detail":"..."}`
- **预期**: 所有错误响应使用统一格式。
- **实际**: 部分 API handler 直接使用 `raise HTTPException(status_code=400, detail="...")` 而不是抛出自定义异常。
- **证据**: `curl POST /api/v1/sandboxes {"template_name":"claude-code"}` 返回 `{"detail":"..."}` 而非 `{"success":false,"message":"...","detail":"..."}`。
- **修复方向**: 用 `TemplateNotReadyError` 替代 handler 中直接抛 HTTPException 的地方，或注册 FastAPI 的全局 HTTPException handler 来统一格式。

#### 问题 #5: 模板名/快照名缺少输入验证 [轻微]
- **严重程度**: 轻微
- **维度**: 可靠性 / 代码质量
- **位置**: `src/sandbox_manager/models/schemas.py:115-121` (SaveTemplateRequest.name)
- **问题**: `SaveTemplateRequest.name` 没有任何格式验证。接受空字符串、特殊字符（如 `; rm -rf /`、空格等）。虽然 Docker SDK 会拒绝非法的镜像名，但错误会以 500 而非 400 返回。
- **预期**: 模板名应只允许小写字母、数字、连字符和下划线，长度 1-100 字符。
- **实际**: 接受任意字符串，包括空字符串 `""`。
- **证据**: Python 验证 `SaveTemplateRequest(name='test; rm -rf /', description='hack')` 和 `SaveTemplateRequest(name='', description='')` 均通过。
- **修复方向**: 在 Pydantic schema 中添加 `name: str = Field(..., pattern=r'^[a-z0-9][a-z0-9_-]*$', min_length=1, max_length=100)`。

#### 问题 #6: ruff lint 有 3 个未使用导入警告 [轻微]
- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `tests/test_database.py:3` (asyncio), `tests/test_database.py:9` (Settings), `tests/test_template_parsing.py:4` (Path)
- **问题**: 3 个测试文件中有未使用的 import。
- **预期**: 零 lint 警告。
- **实际**: ruff 报告 3 个 F401 错误。M1 交付报告声称 "ruff lint: PASS (0 errors)" 但实际不通过。
- **证据**: `python3 -m ruff check src/ tests/` 返回 3 个 F401 错误。
- **修复方向**: 删除未使用的导入。

---

### 测试覆盖评估

#### 已覆盖
- 配置管理: 4 个测试（默认值、URL 生成、环境变量覆盖）
- 异常层级: 11 个测试（每种异常类型的消息和 detail）
- YAML 解析: 6 个测试（有效配置、所有内置模板、缺失文件、缺失字段、无效值、默认值）
- 数据库: 2 个异步测试（初始化+注册、CRUD）
- API 端点: 11 个测试（健康检查、状态、模板列表/详情/404、沙盒列表/404/创建验证、构建状态）

#### 缺失
- **集成测试**: 没有真正调用 OpenSandbox 创建沙盒的测试（所有测试都是 mock 或只测试不涉及外部依赖的路径）
- **构建流程测试**: `_do_build` 方法没有单元测试（虽然逻辑最复杂）
- **快照流程测试**: `save_sandbox_as_template` 没有测试
- **Docker Bridge 测试**: 0 个直接测试
- **错误路径测试**: 缺少 OpenSandbox 连接失败时创建沙盒的测试
- **并发测试**: 没有模板重复构建的并发测试
- **边界值测试**: 没有对空名称、超长名称、特殊字符名称的测试

测试整体评价: 33 个测试覆盖了基础的 happy path 和简单的错误路径，但缺少对核心业务逻辑（构建、快照）的直接测试。测试数量看似不少，但 11 个是简单的异常类构造测试，实际有效测试约 22 个。

---

### 代码质量总评

**优点:**
1. 项目结构清晰，分层合理（API -> Service -> Bridge/DB）
2. 异常层级设计良好，每个异常都有可操作的 detail 信息
3. 配置管理使用 Pydantic Settings，支持环境变量覆盖
4. 数据库使用 async SQLAlchemy + WAL 模式，考虑了并发
5. 模板构建是异步任务，不阻塞 API
6. 异常状态的清理机制（服务重启后 building -> failed）
7. 全局异常处理器确保未捕获的自定义异常不会泄露堆栈

**不足:**
1. DockerBridge 的 async 函数实际阻塞事件循环
2. health/status 端点的 OpenSandbox 连通性检测是假的
3. 缺少输入验证（模板名）
4. 错误响应格式不统一
5. lint 报告与实际不符
6. 核心业务逻辑（构建、快照）没有单元测试

---

### 评分理由

**功能完整性 8/10**: M1 要求的所有核心功能（模板注册、构建、CRUD、快照）均正常工作。4 个内置模板注册正确，python-dev 构建成功，快照端到端验证通过，构建失败有明确错误报告。扣分原因: health/status 接口中 OpenSandbox 连通性检测功能实质缺失（虽然有字段但不真正检测）。

**可靠性 6/10**: 主要操作的错误处理基本到位（创建失败、模板不存在、重复名称等都有合适的错误码和消息）。但 health/status 端点的 OpenSandbox 检测是假的，这意味着运维监控会得到错误信息。DockerBridge 阻塞事件循环在高负载下可能导致 API 超时。模板名没有输入验证可能导致意外的 500 错误。

**用户体验 6/10**: API 接口设计合理，错误消息包含可操作的建议（如"请使用 GET /api/v1/templates 查看可用模板列表"）。构建失败报告了具体步骤和原因。但错误响应格式不统一（有的返回 `{"detail":"..."}` 有的返回 `{"success":false,"message":"...","detail":"..."}`），会给 CLI 层的消费带来麻烦。

**代码质量 6/10**: 项目结构清晰，命名规范，异常层级设计良好。但 async 函数不 await 是一个基本的异步编程错误，health 端点的"假检测"说明代码中存在临时方案没有被标记为 TODO，lint 报告声称 0 error 但实际有 3 个。测试覆盖了基础路径但核心业务逻辑（构建、快照）缺少直接测试。

---

### 总结

- 共 6 个问题（0 个严重, 3 个中等, 3 个轻微）
- 最关键的问题是: #1 和 #2 (health/status 端点的 OpenSandbox 连通性检测是假的)，以及 #3 (DockerBridge 阻塞事件循环)
- 建议优先修复:
  1. **问题 #1 + #2**: health/status 端点的 OpenSandbox 连通性检测 -- 影响运维可观测性
  2. **问题 #3**: DockerBridge async 方法中的同步阻塞 -- 影响并发时的 API 可用性
  3. **问题 #5**: 模板名输入验证 -- 防止意外的 500 错误
  4. **问题 #4 + #6**: 响应格式统一和 lint 修复 -- 代码规范

---

## 回归验证报告

> 验证日期: 2026-04-09
> 验证人: QA Inspector
> 触发原因: coder 提交了针对 6 个 QA 问题的修复

### 问题修复验证

| # | 问题 | 严重程度 | 验证方式 | 结果 |
|---|------|----------|----------|------|
| 1 | /health 端点不检测 OpenSandbox 连通性 | 中等 | 代码审查 + 主对话实测 | FIXED |
| 2 | /status 端点用 Docker 替代 OpenSandbox | 中等 | 代码审查 + 主对话实测 | FIXED |
| 3 | DockerBridge async 方法执行同步阻塞 | 中等 | 代码审查 | FIXED |
| 4 | API 错误响应格式不统一 | 轻微 | API 实测 | FIXED |
| 5 | 模板名/快照名缺少输入验证 | 轻微 | API 实测 | FIXED |
| 6 | ruff lint 有 3 个 F401 | 轻微 | ruff check | FIXED |

**6/6 问题全部修复。**

### 逐项验证详情

**问题 #1 -- FIXED**
- `health.py:37` 现在调用 `await sandbox_service.ping_opensandbox()`
- `sandbox_service.py:40-58` 实现了 `ping_opensandbox()` 方法，通过 `httpx.AsyncClient` 请求 `{opensandbox_url}/health`，超时 2 秒
- 原来的硬编码 `True` 已完全移除
- 主对话已验证: 停止 OpenSandbox 后 `/health` 返回 `opensandbox_connected: false`，恢复后返回 `true`

**问题 #2 -- FIXED**
- `health.py:76` 现在调用 `await sandbox_service.ping_opensandbox()`，替代了原来的 `docker_bridge.check_docker()`
- 与问题 #1 使用相同的 ping 机制，确保 health 和 status 端点行为一致

**问题 #3 -- FIXED (代码审查)**
- `docker_bridge.py` 中所有 4 个 async 方法均已使用 `asyncio.to_thread()` 包装同步 Docker 调用:
  - `commit_container`: `containers.get`(行71), `container.pause`(行82), `container.commit`(行86), `container.unpause`(行94), `image.reload`(行101) -- 5 处
  - `get_image_info`: `images.get`(行116) -- 1 处
  - `remove_image`: `images.remove`(行134) -- 1 处
  - `check_docker`: `client.ping`(行146) -- 1 处
- 共计 8 处同步调用全部正确包装，不再阻塞事件循环

**问题 #4 -- FIXED**
- `main.py:210-223` 注册了全局 `HTTPException` handler，将所有 HTTPException 响应统一为 `{"success": false, "message": "...", "detail": "..."}` 格式
- 实测验证:
  - `POST /sandboxes {"template_name":"claude-code"}` 返回 `{"success":false,"message":"模板 'claude-code' 状态为 'unbuilt'...","detail":"..."}`
  - `POST /sandboxes {}` 返回 `{"success":false,"message":"必须指定 template_name 或 image","detail":"..."}`
  - `GET /sandboxes/nonexistent` 返回 `{"success":false,"message":"沙盒 'nonexistent-id' 不存在","detail":"..."}`
  - `GET /templates/nonexistent` 返回 `{"success":false,"message":"模板 'nonexistent-template' 不存在","detail":"..."}`
- 注意: Pydantic `RequestValidationError`（422）仍使用 FastAPI 默认的 `{"detail": [...]}` 数组格式。这是合理的 -- 422 带有结构化位置信息（loc/type/msg），统一为简单字符串反而会丢失信息。不作为问题。

**问题 #5 -- FIXED**
- `schemas.py:118-124` 的 `SaveTemplateRequest.name` 添加了:
  - `pattern=r"^[a-z0-9][a-z0-9_-]*$"` -- 只允许小写字母、数字、连字符、下划线，必须以字母/数字开头
  - `min_length=1` -- 不接受空字符串
  - `max_length=100` -- 限制长度
- 实测验证:
  - `name="test; rm -rf /"` -> 422 string_pattern_mismatch
  - `name=""` -> 422 string_too_short
  - `name="UPPERCASE"` -> 422 string_pattern_mismatch
  - `name="valid-name-123"` -> 通过验证，进入业务逻辑（返回 sandbox not found）

**问题 #6 -- FIXED**
- `python3 -m ruff check src/ tests/` 输出 "All checks passed!"
- 3 个 F401 未使用导入已全部清理

### 回归测试

| 测试项 | 结果 |
|--------|------|
| 单元测试套件 (33 tests) | 33/33 passed (10.06s) |
| `GET /api/v1/health` | 正常: `{"status":"ok","opensandbox_connected":true,"database_ok":true}` |
| `GET /api/v1/status` | 正常: 4 个模板、1 个已构建 |
| `GET /api/v1/templates` | 正常: 4 个模板列表完整 |
| `GET /api/v1/templates/python-dev` | 正常: 详情包含完整配置 |
| `POST /api/v1/sandboxes` (python-dev) | 正常: 沙盒创建成功并返回详情 |
| `GET /api/v1/sandboxes` | 正常: 列表显示新建沙盒 |
| `DELETE /api/v1/sandboxes/{id}` | 正常: 沙盒销毁成功 |
| ruff lint | 0 errors |

**无回归问题。**

### 修复后重新评分

| 维度 | 修复前 | 修复后 | 变化原因 |
|------|--------|--------|----------|
| 功能完整性 | 8/10 | 8/10 | 不变。修复的问题不属于功能缺失 |
| 可靠性 | 6/10 | 7/10 | +1: health/status 连通性检测修复(+0.5)，DockerBridge 不再阻塞事件循环(+0.5)，输入验证完善(+0.5)，总计约 +1 |
| 用户体验 | 6/10 | 7/10 | +1: 错误响应格式统一，输入验证返回清晰的错误提示 |
| 代码质量 | 6/10 | 7/10 | +1: lint 零警告，async 方法正确使用 await，代码规范性提升 |

**里程碑 M1 最终结果: PASS**

### 结论

coder 对 6 个问题的修复全部到位，修复质量良好。具体而言:
- 中等问题的修复（#1/#2/#3）设计合理 -- ping_opensandbox 使用轻量级 HTTP GET 而非创建/销毁沙盒，asyncio.to_thread 包装粒度恰当
- 轻微问题的修复（#4/#5/#6）实现正确且没有过度设计
- 全量测试通过，未引入回归
- M1 可以正式关闭，进入 M2

---

## 补充 QA -- 模板构建验证

> 评审日期: 2026-04-10
> 评审人: QA Inspector
> 触发原因: claude-code 和 vscode 模板已构建完成，补充之前 SKIP 的场景 5/7/8/9/1

---

### 场景 5: claude-code 模板构建 -- PASS

**验证步骤:**
1. `GET /api/v1/templates/claude-code` 获取模板详情
2. 验证 Docker 镜像存在并核对 size

**实测结果:**
- status: `ready`
- size_bytes: `229380211` (218.8MB)
- docker_image: `sbxmgr/claude-code:latest`
- docker_image_id: `sha256:3100b0bc62f6...` (与 `docker inspect` 输出一致)
- install_commands: 4 条 (apt-get + nodesource + nodejs + npm install @anthropic-ai/claude-code)
- connect_type: `shell`
- base_image: `ubuntu:22.04`
- build_error: `null`
- Docker 实际镜像: `sbxmgr/claude-code:latest`, 798MB (磁盘解压大小)
- `docker inspect` Size: 229380211 bytes -- **与 API 报告的 size_bytes 完全一致**

**结论:** claude-code 模板构建成功，所有元数据正确。

---

### 场景 7: vscode 模板构建 -- PASS

**验证步骤:**
1. `GET /api/v1/templates/vscode` 获取模板详情
2. 验证 Docker 镜像存在并核对 size
3. 验证 connect_type 和 ports 配置

**实测结果:**
- status: `ready`
- size_bytes: `416828262` (397.5MB)
- docker_image: `sbxmgr/vscode:latest`
- docker_image_id: `sha256:e3e1e65fcf80...` (与 `docker inspect` 输出一致)
- install_commands: 2 条 (apt-get + code-server install)
- connect_type: `url` -- 与 YAML 一致
- connect_port: `8443`
- ports: `{"8443": 8443}`
- entrypoint: `["code-server", "--bind-addr", "0.0.0.0:8443", "--auth", "none"]`
- env: `{"PASSWORD": ""}`
- base_image: `ubuntu:22.04`
- build_error: `null`
- Docker 实际镜像: `sbxmgr/vscode:latest`, 1.44GB (磁盘解压大小)
- `docker inspect` Size: 416828262 bytes -- **与 API 报告的 size_bytes 完全一致**

**结论:** vscode 模板构建成功，所有元数据正确。connect_type=url 和 ports 配置正确。

---

### 场景 8: openclaw 模板构建 -- PARTIAL (网络超时)

**测试过程:**

1. 初始状态: openclaw 状态为 `building`（之前触发的构建）
2. 轮询构建状态，最终发现构建失败:
   ```
   status: failed
   build_error: "第 2 步失败 (exit code 1): pip3 install openclaw-gateway
   ERROR: Could not find a version that satisfies the requirement openclaw-gateway"
   ```
3. **根因**: 数据库中的 install_commands 仍为旧版本 (`pip3 install openclaw-gateway`)，而 YAML 已更新为 `npm install -g openclaw`。`register_builtin_templates` 逻辑为 "已存在则跳过"，不会用 YAML 覆盖更新。
4. **修复**: 删除旧的 openclaw 模板 -> 重启服务 -> 重新注册（使用更新后的 YAML）
5. 重新触发构建后，构建沙盒成功创建（ubuntu:22.04），apt-get 开始执行
6. 轮询 20+ 分钟后，apt-get install 仍在下载（Docker 容器内网络极慢）
7. 构建仍在进行中，单条命令超时设为 10 分钟，总超时 30 分钟

**发现的问题:**
- **M1 新问题: 内置模板 YAML 更新后数据库不同步** (详见下方问题列表)

**结论:** openclaw 构建因环境网络问题未能在 QA 窗口内完成。构建流程本身工作正常（临时沙盒创建、命令执行、状态上报都正确），失败原因是外部依赖下载超时。标记为 PARTIAL。

---

### 场景 9: 4 个模板全部就绪 -- PARTIAL

**当前状态:**
| 模板 | 状态 | 大小 |
|------|------|------|
| python-dev | ready | 342.2MB |
| claude-code | ready | 218.8MB |
| vscode | ready | 397.5MB |
| openclaw | building | N/A |

**结论:** 3/4 模板就绪。openclaw 因网络问题仍在构建中。标记为 PARTIAL。

---

### 场景 1: Docker 部署验证 -- PARTIAL PASS

**测试方法:** 由于端口 8080/8000 被现有服务占用，无法完整启动 docker-compose，仅验证 Dockerfile 构建能力和 docker-compose 配置语法。

**验证结果:**

1. **Dockerfile 语法检查**: PASS
   - 结构完整: FROM + WORKDIR + RUN + COPY + RUN + EXPOSE + CMD 全部正确
   - 基础镜像: `python:3.11-slim`
   - 工作目录: `/app`
   - 依赖安装: `pip install --no-cache-dir .` (从 pyproject.toml)
   - 数据目录: `/app/data` (构建时创建)
   - 暴露端口: 8000
   - 启动命令: `uvicorn sandbox_manager.main:app --host 0.0.0.0 --port 8000`

2. **docker-compose.yaml 语法验证**: PASS
   - `docker compose config --quiet` 通过
   - 两个服务定义正确: opensandbox-server + sandbox-manager
   - 健康检查: opensandbox-server 有 healthcheck
   - 依赖: sandbox-manager depends_on opensandbox-server (service_healthy)
   - 卷挂载: docker.sock + sandbox-data 持久卷 + templates 只读挂载
   - 环境变量: SBXMGR_OPENSANDBOX_HOST/PORT/DATABASE_PATH 全部正确

3. **Docker build**: FAIL (外部原因)
   - `docker build -t sandbox-manager-test:qa-test .` 因 Docker Hub auth.docker.io 网络超时失败
   - 本地没有 `python:3.11-slim` 基础镜像可用
   - 这是网络环境问题，非 Dockerfile 缺陷

**结论:** Dockerfile 和 docker-compose 配置本身正确无误，但因 Docker Hub 网络不可达无法完成实际构建。标记为 PARTIAL PASS。

---

### 补充发现的问题

#### 问题 #7: 内置模板 YAML 更新后数据库不同步

- **严重程度**: 轻微
- **维度**: 用户体验 / 可靠性
- **位置**: `src/sandbox_manager/services/template_service.py` 第 127-156 行 (`register_builtin_templates`)
- **问题**: `register_builtin_templates` 的逻辑是 "只注册数据库中不存在的模板，已存在的跳过"。当开发者修改了内置模板的 YAML 配置（如更改 install_commands），重启服务后数据库中的旧配置不会被更新。这导致 openclaw 的首次构建使用了旧的 `pip3 install openclaw-gateway` 而非 YAML 中更新后的 `npm install -g openclaw`。
- **预期**: 服务重启时检测 YAML 是否有变更（至少对 unbuilt/failed 状态的模板），如果有变更则更新数据库。
- **实际**: 完全跳过已存在的模板，即使 YAML 内容已改变。
- **证据**: 数据库中 openclaw 的 install_commands 为 `['..python3-pip', 'pip3 install openclaw-gateway']`，而 YAML 文件为 `['...nodejs npm', 'npm install -g openclaw']`。需要手动删除模板并重启才能生效。
- **修复方向**: 对 unbuilt 或 failed 状态的模板，比较 YAML 内容（计算 hash 或逐字段比较），如有变更则更新数据库记录。ready 状态的模板因已构建镜像，不应自动覆盖。

---

### M1 补充评分调整

补充测试后 M1 各维度评分无需调整:
- **功能完整性**: 维持 8/10。3 个模板构建验证全部通过（claude-code、vscode、python-dev），openclaw 因网络超时非功能问题。问题 #7 为轻微缺陷。
- **可靠性**: 维持 7/10。构建流程对失败情况有正确的错误报告（openclaw 第一次失败时准确报告了步骤/exit code/stderr）。
- **用户体验**: 维持 7/10。模板详情接口返回了完整、准确的元数据。
- **代码质量**: 维持 7/10。

**M1 最终结果: PASS (已含补充验证)**
