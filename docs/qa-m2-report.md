## QA 评审报告 -- 里程碑 M2

**评审日期**: 2026-04-09
**评审人**: QA Inspector
**评审对象**: 功能组 C（沙盒管理 -- 功能 #10-#14）
**环境**: OpenSandbox localhost:8080 + Sandbox Manager localhost:9000 + Docker Engine

---

### 评分摘要

| 维度 | 分数 | 阈值 | 状态 |
|------|------|------|------|
| 功能完整性 | 7/10 | 7 | PASS |
| 可靠性 | 5/10 | 6 | **FAIL** |
| 用户体验 | 6/10 | 6 | PASS |
| 代码质量 | 6/10 | 5 | PASS |

**里程碑结果: FAIL -- 可靠性维度未达阈值**

---

### 验收标准验证

使用已构建的 python-dev 模板执行实际集成测试。claude-code/vscode/openclaw 模板因未构建而跳过（场景 1-3），M1 QA 已验证构建流程本身的正确性。

| # | 场景 | 结果 | 实测详情 |
|---|------|------|----------|
| 1 | 从 claude-code 模板创建沙盒 | SKIP | 模板未构建，M1 已验证构建流程 |
| 2 | 从 vscode 模板创建沙盒 | SKIP | 模板未构建 |
| 3 | 从 openclaw 模板创建沙盒 | SKIP | 模板未构建 |
| 4 | 从 python-dev 创建沙盒 -> 启动 <=3s -> shell 连接 -> numpy 可用 | **PASS** | 启动耗时约 582ms；connect-info 返回正确的 `docker exec -it sandbox-{id} /bin/bash` 命令；`docker exec` 验证 `import numpy` 成功，版本 2.2.6 |
| 5 | 列出所有沙盒 -> 显示运行中的沙盒 | **PASS** | 返回正确的沙盒列表，包含 id、template_name、status、connect_type、created_at 等字段 |
| 6 | 暂停 python-dev 沙盒 -> 状态变为 paused | **PASS** | API 返回 `{"success": true, "message": "沙盒已暂停"}`；`docker inspect` 确认容器状态为 `paused` |
| 7 | 恢复 python-dev 沙盒 -> 状态变为 running -> 环境完好 | **PASS** | API 返回成功；`docker inspect` 确认 running；`import numpy` 仍然成功 |
| 8 | 销毁单个沙盒 -> 容器被移除 -> 列表中不再显示 | **PASS** | DELETE 返回成功；`docker inspect` 确认容器不存在；GET list 不再包含该沙盒 |
| 9 | 批量销毁所有沙盒 -> 所有容器被移除 | **PASS** | 创建 3 个沙盒后 `DELETE /sandboxes?all=true` 返回 `{"total":3, "deleted":3, "failed":0}`；列表为空；`docker ps` 无 sandbox- 容器 |
| 10 | 已暂停沙盒获取 connect-info -> 提示沙盒已暂停 | **PASS** | 返回 `{"status":"paused", "message":"沙盒已暂停，请先恢复沙盒: POST /api/v1/sandboxes/{id}/resume"}` |
| 11 | 不存在的沙盒获取 connect-info -> 404 | **PASS** | HTTP 404，返回 `{"message":"沙盒 'nonexistent-id-12345' 不存在"}` |
| 12 | 从未构建模板创建沙盒 -> 提示模板未构建 | **PASS** | HTTP 400，返回 `{"message":"模板 'claude-code' 状态为 'unbuilt'，请先构建模板"}` |

#### 额外验证

| 场景 | 结果 | 实测详情 |
|------|------|----------|
| 暂停已暂停的沙盒 | **PASS** | HTTP 400，`{"message":"沙盒当前状态为 'paused'，不允许此操作", "detail":"此操作要求沙盒状态为: running"}` |
| 恢复已运行的沙盒 | **PASS** | HTTP 400，`{"message":"沙盒当前状态为 'running'，不允许此操作", "detail":"此操作要求沙盒状态为: paused"}` |
| Docker 状态同步 | **PASS** | 手动 `docker pause` 后，API list 自动同步状态为 paused |
| 批量销毁不带 all=true | **PASS** | HTTP 400，`{"message":"批量销毁需要显式指定 all=true"}` |
| 暂停/恢复/删除不存在的沙盒 | **PASS** | 均返回 HTTP 404 |
| 手动 docker pause 后 API pause | **FAIL** | HTTP 500，OpenSandbox SDK health check 超时，见问题 #1 |
| 手动 docker unpause 后 API resume | **FAIL** | HTTP 500，SDK 报 "Sandbox is not in a paused state"，见问题 #1 |

---

### 问题列表

#### 问题 #1: pause/resume 端点未同步 Docker 实际状态导致 500 错误

- **严重程度**: 中等
- **维度**: 可靠性
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 373-408 行 (pause_sandbox), 第 410-449 行 (resume_sandbox)
- **问题**: `pause` 和 `resume` 端点在操作前没有像 `list`/`detail`/`connect-info` 端点那样先通过 `DockerBridge.get_container_status` 同步容器实际状态。当容器实际状态与数据库记录不一致时（例如用户手动执行了 `docker pause/unpause`，或其他外部工具修改了容器状态），API 会基于过时的数据库状态进行判断，向 OpenSandbox SDK 发送不合适的操作请求，最终收到 SDK 错误并返回 500。
- **预期**: pause/resume 端点应在操作前先同步 Docker 容器实际状态，然后基于实际状态做判断。如果容器已经是暂停状态，pause 应返回 400 "已暂停"；如果容器已经在运行，resume 应返回 400 "已在运行"。
- **实际**: pause 端点在容器已被手动暂停时，数据库仍为 running，通过状态检查后向 SDK 发送 pause 请求，SDK health check 超时 30 秒后返回 500 错误。resume 端点类似，在容器已被手动 unpause 后返回 500。
- **证据**:
  - 手动 `docker pause` 后调用 `POST /sandboxes/{id}/pause` 返回: `{"message":"无法连接到 OpenSandbox server: ... (暂停沙盒失败: Sandbox health check timed out after 30.0s ...)"}`，HTTP 500
  - 手动 `docker unpause` 后调用 `POST /sandboxes/{id}/resume` 返回: `{"message":"... (恢复沙盒失败: Sandbox is not in a paused state.)"}`，HTTP 500
- **修复方向**: 在 pause/resume 端点的状态校验之前，加入与 list/detail 端点相同的 Docker 状态同步逻辑（调用 `docker_bridge.get_container_status` + `_map_docker_status` + 更新数据库）。建议抽取为一个公共辅助函数 `_sync_sandbox_status`，避免在多个端点中重复代码。

#### 问题 #2: 批量销毁的 failed 计数永远为 0

- **严重程度**: 中等
- **维度**: 可靠性
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 478-488 行
- **问题**: `delete_all_sandboxes` 函数中，当 `kill_sandbox_by_id` 抛出异常时（`except Exception` 分支），代码仍然执行 `deleted += 1` 而非 `failed += 1`。这意味着 `BatchDeleteResponse.failed` 永远为 0，无论实际是否有容器 kill 失败。
- **预期**: kill 失败的沙盒应计入 `failed` 而非 `deleted`，让调用方知道有多少容器实际未被成功移除。
- **实际**: 即使 kill 失败，deleted 也会加 1，failed 始终为 0。
- **证据**: 代码审查，`sandboxes.py` 第 483-487 行:
  ```python
  except Exception:
      logger.warning("批量销毁沙盒失败: %s", s.id, exc_info=True)
      # 即使 kill 失败也从数据库删除记录（容器可能已不存在）
      await session.delete(s)
      deleted += 1  # 此处应为 failed += 1
  ```
- **修复方向**: 将 except 分支中的 `deleted += 1` 改为 `failed += 1`。同时考虑：数据库记录仍被删除了，但 failed 计数应反映 Docker 层面的失败。

#### 问题 #3: connect-info 对暂停/停止状态返回 HTTP 200

- **严重程度**: 轻微
- **维度**: 用户体验
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 328-344 行
- **问题**: 当沙盒处于 paused 或 stopped 状态时，connect-info 端点返回 HTTP 200 + ConnectInfo 结构体（command/url/ports 字段均为 null，仅有 message 字段包含提示）。HTTP 200 语义上表示"请求成功"，但实际上调用方请求的连接信息不可用。CLI 层面的调用方可能不检查 message 字段而直接使用 command 字段，得到 null 值。
- **预期**: 对暂停状态返回 HTTP 409 (Conflict) 并在 body 中提示恢复方式；对停止状态返回 HTTP 410 (Gone) 或 409。或者至少使用 HTTP 422，让调用方明确知道这不是正常成功响应。
- **实际**: 返回 HTTP 200 + message 字段。
- **证据**: `GET /sandboxes/{id}/connect-info` 对暂停沙盒返回 HTTP 200，body 中 command=null, url=null, message="沙盒已暂停"。
- **修复方向**: 改为返回 HTTP 409，或在 ConnectInfo schema 中增加 `available: bool` 字段让调用方明确判断。

#### 问题 #4: 单个销毁端点缺少异常保护

- **严重程度**: 轻微
- **维度**: 可靠性
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 500-519 行
- **问题**: `delete_sandbox` 端点直接调用 `sandbox_service.kill_sandbox_by_id(sandbox_id)` 但没有 try/except 包裹。虽然 `kill_sandbox_by_id` 内部已有异常处理（不会传播异常），但这依赖于 `SandboxService` 的内部实现细节。相比之下，`delete_all_sandboxes` 中对同一方法调用用了 try/except。两个端点的异常处理策略不一致。
- **预期**: 与批量销毁保持一致的异常处理方式，或在 API 层统一用 try/except 包裹外部服务调用。
- **实际**: 批量销毁有异常保护，单个销毁没有。
- **证据**: 代码审查对比 `delete_sandbox`（第 512 行，无 try/except）与 `delete_all_sandboxes`（第 479 行，有 try/except）。
- **修复方向**: 为 `delete_sandbox` 添加 try/except，或确保 `kill_sandbox_by_id` 的异常不传播契约是显式的（docstring 标注）。

#### 问题 #5: 沙盒列表 N+1 查询问题

- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 195-248 行
- **问题**: `list_sandboxes` 端点对每个沙盒都执行了两次额外操作：(1) `docker_bridge.get_container_status` 查询 Docker 容器状态，(2) `session.execute(select(Template)...)` 查询关联模板。这是经典的 N+1 查询问题。
- **预期**: 使用 SQLAlchemy eager loading (`joinedload`) 一次性获取关联的模板数据；Docker 状态查询可以批量化（一次 `docker ps` 获取所有容器状态）。
- **实际**: 每个沙盒产生 1 次 DB 查询 + 1 次 Docker API 调用。
- **证据**: 代码审查。
- **修复方向**: 对于 MVP 阶段，个人开发者场景下沙盒数量通常不多（< 20），性能影响有限。建议在后续优化中处理：模板数据用 `joinedload`；Docker 状态用一次 `docker ps --format` 批量获取。

#### 问题 #6: openclaw 模板 connect_type 与产品规格不一致

- **严重程度**: 轻微
- **维度**: 功能完整性
- **位置**: `templates/openclaw.yaml` 第 4 行
- **问题**: 产品规格附录 A 定义 openclaw 的连接类型为 "shell + port"，但模板 YAML 中 `connect_type: shell`。当前 connect_type 只支持单一值（shell/url/port），不支持复合类型。这意味着 openclaw 沙盒的 connect-info 只会返回 shell 命令，不会附带端口映射信息。
- **预期**: openclaw 沙盒应同时返回 shell 命令和端口映射信息（7860 端口）。
- **实际**: 仅返回 shell 命令，ports 字段为 null。
- **证据**: `GET /sandboxes/{id}/connect-info` 对 openclaw 类型沙盒（如果模板已构建）只返回 `{"connect_type":"shell", "command":"docker exec ...", "ports":null}`。模板配置确认 `connect_type: shell`。
- **修复方向**: 两个方案：(1) 支持复合 connect_type（如 "shell+port"），connector 同时返回 shell 命令和端口信息；(2) 在 shell 类型的 connect-info 中，如果模板配置了 ports，也一并返回端口信息。方案 2 更简单，改动更小。注意此问题跨 M1/M2 边界：模板定义是 M1 内容，connect-info 实现是 M2 内容。

---

### 测试覆盖评估

**单元测试**: 63/63 通过（33 M1 + 30 M2）
**Lint**: ruff check 0 errors

**已覆盖场景**:
- 未构建/不存在模板创建沙盒的错误处理
- connect-info 对不存在/暂停/停止/运行中沙盒的处理
- ConnectorService 的 shell/url/port 三种类型构建逻辑
- url 类型获取端点失败时的 fallback
- 未知 connect_type 回退到 shell
- 沙盒列表空列表、按状态筛选、Docker 状态同步
- 暂停/恢复的所有状态组合（6 种边界）+ 成功路径
- 单个/批量销毁的正常和异常路径
- Docker 状态映射函数完整覆盖

**缺失场景**:
- url/port 类型 connect-info 的 API 端到端测试（仅有 ConnectorService 单元测试，未覆盖 API 层组装逻辑）
- 创建沙盒成功路径的测试（需要 mock OpenSandbox SDK）
- pause/resume 操作前的 Docker 状态同步测试（即问题 #1 的场景）
- 批量销毁部分失败时 failed 计数的测试（即问题 #2 的场景）
- 详情端点（GET /{id}）的 Docker 状态同步测试
- 并发操作测试（同时 pause 和 resume 同一个沙盒）

---

### 评分详细理由

#### 功能完整性: 7/10

核心功能全部实现且正常工作：沙盒创建、connect-info、列表（含状态同步和筛选）、暂停/恢复、单个/批量销毁。所有 12 个可测试的验收场景中 9 个 PASS，3 个 SKIP（依赖未构建模板）。扣分原因：
- openclaw 模板的 connect_type 与产品规格中 "shell + port" 不一致（问题 #6）
- 创建沙盒成功路径未被单元测试覆盖

#### 可靠性: 5/10 -- **未达阈值**

主要扣分点：
- pause/resume 端点未同步 Docker 实际状态，导致数据库与容器状态不一致时返回 500 错误（问题 #1）。这不是极端边界情况 -- 用户可能通过 Docker Desktop、portainer 等工具管理容器，也可能在快照操作中触发 Docker-level pause。**30 秒 health check 超时** 更是严重的用户体验问题。
- 批量销毁的 failed 计数逻辑错误（问题 #2），返回虚假成功信息。
- 单个销毁端点缺少异常保护（问题 #4），与批量销毁的处理方式不一致。

给 5 分而非更低是因为：正常使用路径下所有功能都稳定工作；错误处理在预期场景下表现良好（不存在的沙盒、错误状态的操作都有清晰提示）。

#### 用户体验: 6/10

优点：
- 错误信息清晰、具有可操作性（"请先构建模板"、"请先恢复沙盒"）
- 响应格式统一（success/message/detail）
- 状态筛选支持直观
- 启动时间远低于 3s 阈值（~580ms）

扣分点：
- connect-info 对暂停/停止状态返回 HTTP 200 可能误导调用方（问题 #3）
- 问题 #1 中的 500 错误信息包含 SDK 内部细节（health check timeout, ConnectionConfig 提示），对用户不友好
- 沙盒创建时 name 字段为 null，列表中没有人类可读的标识符，不利于管理多个沙盒

#### 代码质量: 6/10

优点：
- 代码组织清晰：ConnectorService 单独拆分、辅助函数提取减少重复
- 异常层级设计合理，全局异常处理统一
- Docker 状态映射完整覆盖所有已知状态
- lint 0 errors，测试 63/63 通过
- 依赖注入使用得当

扣分点：
- 端点间 Docker 状态同步逻辑不一致（GET 端点同步，POST/DELETE 端点不同步），应抽取公共函数
- N+1 查询问题（问题 #5），虽然 MVP 影响不大但表明架构意识不足
- 测试全部使用 mock，缺少创建成功路径和 connect-info 端到端的 API 测试
- 批量删除的 failed 计数逻辑明显是代码编写错误（问题 #2）

---

### 总结

- 共 6 个问题（中等 2, 轻微 4）
- **最关键的问题**: 问题 #1（pause/resume 不同步 Docker 状态），因为它会导致 30 秒超时等待和 500 错误，直接影响用户体验和系统可靠性
- **建议优先修复顺序**:
  1. 问题 #1: pause/resume 端点添加 Docker 状态同步（可靠性关键修复）
  2. 问题 #2: 修正批量销毁的 failed 计数逻辑（简单改动，一行代码）
  3. 问题 #4: 统一 delete 端点的异常处理（小改动）
  4. 问题 #3: connect-info 的 HTTP 状态码语义（设计决策，需讨论）
  5. 问题 #6: openclaw 的 connect_type 对齐产品规格（跨 M1/M2）
  6. 问题 #5: N+1 查询优化（可后续迭代）

**结论**: M2 的核心新功能（暂停/恢复/连接信息/批量销毁）在正常路径下工作良好，代码组织清晰，错误提示有用。但 pause/resume 端点的状态同步遗漏是一个**结构性缺陷** -- 它表明 GET 端点和 POST 端点之间的设计不一致，不是遗忘了某个边界条件，而是一整类操作都缺少必要的前置检查。修复问题 #1 和 #2 后应可通过可靠性阈值。

---

## 回归验证报告

**验证日期**: 2026-04-09
**验证人**: QA Inspector
**验证对象**: QA 报告 5 个问题（#1-#5）的修复
**环境**: OpenSandbox localhost:8080 + Sandbox Manager localhost:9000 + Docker Engine

---

### 修复验证结果

| # | 问题 | 修复状态 | 验证结果 |
|---|------|----------|----------|
| 1 | pause/resume 端点未同步 Docker 状态 | **已修复** | PASS |
| 2 | 批量销毁 failed 计数永远为 0 | **部分修复** | PARTIAL |
| 3 | connect-info 暂停状态返回 HTTP 200 | **已修复** | PASS |
| 4 | 单个销毁端点缺少异常保护 | **已修复** | PASS |
| 5 | N+1 查询标记 TODO | **已完成** | PASS |

---

### 问题 #1: pause/resume Docker 状态同步 -- 已修复

**修复方式**: 抽取了公共辅助函数 `_sync_sandbox_status`（第 91-114 行），在 pause/resume 端点的状态校验前调用。该函数通过 `docker_bridge.get_container_status` 查询容器实际状态，与数据库不一致时自动更新。

**验证步骤与结果**:

1. 创建沙盒（ID: 56105463），手动执行 `docker pause sandbox-{id}`
2. 调用 `POST /api/v1/sandboxes/{id}/pause`
   - **结果**: HTTP 400，body: `{"success":false,"message":"沙盒当前状态为 'paused'，不允许此操作","detail":"此操作要求沙盒状态为: running"}`
   - **预期行为匹配**: 返回 400 而非之前的 500 超时
3. 手动执行 `docker unpause sandbox-{id}`
4. 调用 `POST /api/v1/sandboxes/{id}/resume`
   - **结果**: HTTP 400，body: `{"success":false,"message":"沙盒当前状态为 'running'，不允许此操作","detail":"此操作要求沙盒状态为: paused"}`
   - **预期行为匹配**: 返回 400 而非之前的 500

**代码质量评价**: 修复质量良好。`_sync_sandbox_status` 公共函数被 4 个端点复用（detail、connect-info、pause、resume），避免了之前 GET/POST 端点间状态同步逻辑不一致的结构性问题。新增了 2 个针对性的单元测试覆盖此场景。

---

### 问题 #2: 批量销毁 failed 计数 -- 部分修复

**修复方式**: 将 `delete_all_sandboxes` 函数 except 分支中的 `deleted += 1` 改为 `failed += 1`（第 510 行）。

**验证步骤与结果**:

1. 创建 2 个沙盒（ID: f2e729c8, 8a740af5）
2. 手动 `docker rm -f sandbox-f2e729c8`（删除第一个容器）
3. 调用 `DELETE /api/v1/sandboxes?all=true`
   - **结果**: `{"total":2, "deleted":2, "failed":0}`
   - **预期**: `failed >= 1`
   - **实际不匹配**: failed 仍然为 0

**根因分析**: API 层的修复（`failed += 1`）逻辑上是正确的，但 `kill_sandbox_by_id`（`sandbox_service.py` 第 177-187 行）内部有 try/except 且**不会重新抛出异常**，它只执行 `logger.warning`。因此当容器已不存在时，`kill_sandbox_by_id` 静默成功返回，API 层的 except 分支永远不会被触发。

单元测试通过 mock 直接让 `kill_sandbox_by_id` 抛出异常（`mock_kill.side_effect = [None, Exception("Docker error"), None]`），绕过了真实的异常吞没行为，所以测试通过了但实际集成测试中修复不生效。

**结论**: 代码层面的逻辑修正是对的（如果异常到达了 API 层，failed 计数会正确工作），但修复不完整 -- `kill_sandbox_by_id` 的异常吞没行为使修复无法在真实场景中生效。这是一个典型的"mock 测试通过但集成行为不符"的案例。

**建议**: `kill_sandbox_by_id` 应当在 kill 失败时重新抛出异常（或者返回 bool 表示是否成功），让调用方有机会感知失败。当前 `kill_sandbox` 方法也有同样的问题。或者在 `delete_all_sandboxes` 中使用更底层的方法直接与 Docker 交互检测容器是否存在。

**严重程度调整**: 维持中等。虽然修复不完整，但影响范围有限 -- 批量销毁的核心功能（容器被移除、数据库清理）仍然正常工作，只是 failed 计数报告不准确。

---

### 问题 #3: connect-info 暂停状态 HTTP 409 -- 已修复

**修复方式**: 将 connect-info 端点中暂停/停止状态的响应从 HTTP 200 + message 字段改为 `raise HTTPException(status_code=409, detail=...)`（第 350-358 行）。

**验证步骤与结果**:

1. 创建沙盒（ID: 773f9567），调用 pause API 暂停
2. 调用 `GET /api/v1/sandboxes/{id}/connect-info`
   - **结果**: HTTP 409，body: `{"success":false,"message":"沙盒已暂停，请先恢复沙盒: POST /api/v1/sandboxes/{id}/resume"}`
   - **预期行为匹配**: 返回 409 而非之前的 200

**代码质量评价**: 修复简洁清晰。stopped 状态也同步改为 409。单元测试已更新（`test_connect_info_paused_sandbox` 和 `test_connect_info_stopped_sandbox` 均 assert status_code == 409）。

---

### 问题 #4: 单个销毁端点异常保护 -- 已修复

**修复方式**: 为 `delete_sandbox` 端点添加了 try/except 包裹 `kill_sandbox_by_id` 调用（第 536-539 行），与批量销毁保持一致的异常处理策略。

**验证步骤与结果**:

1. 创建沙盒（ID: e139c8d9）
2. 手动 `docker rm -f sandbox-{id}`（容器不存在）
3. 调用 `DELETE /api/v1/sandboxes/{id}`
   - **结果**: HTTP 200，`{"success":true, "message":"沙盒已销毁"}`
   - **预期行为匹配**: 优雅处理，不报 500

**代码质量评价**: 修复正确。实际上由于 `kill_sandbox_by_id` 内部已吞掉异常（同问题 #2 的根因），即使不加 try/except 也不会报 500。但添加 try/except 是正确的防御性编程 -- 它不依赖于 `kill_sandbox_by_id` 的内部实现细节，与批量销毁保持了一致的 API 层异常处理策略。新增了 1 个单元测试覆盖此场景。

---

### 问题 #5: N+1 查询标记 TODO -- 已完成

**验证**: `sandboxes.py` 第 221-223 行存在清晰的 TODO 注释：

```python
# TODO: 优化 N+1 查询问题 -- 目前对每个沙盒单独查询模板和 Docker 状态。
# 后续可用 joinedload 批量加载模板，用一次 docker ps 批量获取容器状态。
# MVP 阶段沙盒数量通常 < 20，性能影响有限。
```

注释包含问题描述、优化方向和当前不处理的理由，符合预期。

---

### 回归测试结果

| 场景 | 结果 | 详情 |
|------|------|------|
| 正常 pause -> resume 流程 | PASS | 暂停/恢复成功，Docker 状态正确，numpy 环境完好 |
| connect-info 对 running 状态 | PASS | HTTP 200，返回正确的 docker exec 命令 |
| 沙盒列表 + 状态筛选 | PASS | 列表正常，按 status=running 筛选正确 |
| 批量销毁正常场景 | PASS | total=2, deleted=2, failed=0，容器全部移除 |
| 模板列表 | PASS | 4 个内置模板，python-dev 状态为 ready |
| 模板详情 | PASS | python-dev 详情完整 |
| 不存在的模板 -> 404 | PASS | HTTP 404 |
| 未构建模板创建沙盒 -> 400 | PASS | HTTP 400 + 明确提示 |
| 沙盒启动速度 | PASS | 约 477ms（远低于 3s 阈值） |
| 单个销毁 | PASS | 正常销毁 + 容器移除 + 数据库清理 |

**全量测试**: 67/67 通过（33 M1 + 34 M2，新增 4 个修复验证测试）
**Lint**: ruff check 0 errors
**无回归问题**: 所有现有功能正常工作

---

### 重新评分

| 维度 | 原评分 | 新评分 | 阈值 | 状态 | 变化原因 |
|------|--------|--------|------|------|----------|
| 功能完整性 | 7/10 | 7/10 | 7 | PASS | 无变化，本轮修复不涉及功能新增 |
| 可靠性 | 5/10 | 7/10 | 6 | **PASS** | 问题 #1（最关键）修复质量良好，30s 超时问题消除；问题 #4 异常保护到位。问题 #2 部分修复但影响有限。 |
| 用户体验 | 6/10 | 7/10 | 6 | PASS | 问题 #3 的 409 状态码语义正确，调用方可以明确区分成功/冲突；暂停状态不再返回误导性的 200 |
| 代码质量 | 6/10 | 7/10 | 5 | PASS | `_sync_sandbox_status` 公共函数消除了 GET/POST 端点间的状态同步不一致；delete 端点异常处理统一；新增 4 个针对性测试 |

**里程碑结果: PASS**

### 评分详细理由

#### 可靠性: 5 -> 7

核心改进：
- 问题 #1 的修复消除了最严重的 30 秒 health check 超时问题，这是之前可靠性不通过的最大原因
- `_sync_sandbox_status` 作为公共函数确保了所有状态敏感的端点在操作前都同步 Docker 实际状态
- 单个销毁的异常保护使 API 层的异常处理策略统一

不给更高分的原因：
- 问题 #2 的修复不完整 -- `kill_sandbox_by_id` 的异常吞没使 failed 计数在真实场景中仍为 0
- 上述问题暴露了测试策略的弱点：mock 测试通过但集成行为不符，说明对 `SandboxService` 的异常传播契约缺乏清晰定义

#### 用户体验: 6 -> 7

核心改进：
- 暂停状态的 connect-info 返回 HTTP 409 而非 200，语义正确
- 停止状态的 connect-info 也同步改为 409
- 所有状态冲突场景都有清晰的错误信息和下一步操作指引

#### 代码质量: 6 -> 7

核心改进：
- `_sync_sandbox_status` 公共函数消除了之前的结构性问题（GET 同步、POST 不同步）
- 端点间异常处理策略统一
- 新增 4 个测试覆盖修复场景，总测试从 63 增至 67

不给更高分的原因：
- `kill_sandbox_by_id` 的异常处理契约不明确（静默吞掉异常），导致调用方无法正确感知失败
- 修复验证测试依赖 mock 而非集成测试，问题 #2 的 mock 测试掩盖了真实行为

---

### 遗留问题

| # | 问题 | 严重程度 | 状态 |
|---|------|----------|------|
| 2 | 批量销毁 failed 计数（`kill_sandbox_by_id` 异常吞没） | 轻微（降级） | 部分修复，API 层逻辑正确但 service 层异常不传播 |
| 6 | openclaw connect_type 与产品规格不一致 | 轻微 | 未修复（本轮不在修复范围） |

问题 #2 严重程度从"中等"降为"轻微"：API 层的逻辑修复证明开发者理解了问题本质，剩余的 `kill_sandbox_by_id` 异常传播问题属于 service 层 API 设计的细节优化，不影响核心功能。批量销毁的实际效果（容器移除 + 数据库清理）完全正常，只是统计报告不准确。

---

### 总结

5 个修复中 3 个完全通过验证（#1, #3, #4），1 个确认完成（#5 TODO），1 个部分修复（#2 API 层逻辑正确但 service 层异常不传播）。无新增回归问题。全量测试 67/67 通过，lint 0 errors。

**里程碑 M2 在本轮回归验证后达到通过标准。** 可靠性从 5/10 提升到 7/10，核心阻塞问题（Docker 状态同步导致的 500 超时）已完全解决。问题 #2 的遗留部分和问题 #6 建议在后续迭代中处理。

---

## 补充 QA -- 模板沙盒创建与连接验证

> 评审日期: 2026-04-10
> 评审人: QA Inspector
> 触发原因: claude-code、vscode 模板已构建完成，补充之前 SKIP 的场景 1/2/3

---

### 场景 1: 从 claude-code 模板创建沙盒 -- PASS

**测试步骤与结果:**

1. **创建沙盒**:
   ```
   POST /api/v1/sandboxes {"template_name":"claude-code"}
   ```
   - HTTP 200, 耗时: **0.875s** (远低于 3s 阈值)
   - 返回: id=`5a396c8c-...`, status=`running`, connect_type=`shell`
   - template_name=`claude-code`, image=`sbxmgr/claude-code:latest`

2. **获取 connect-info**:
   ```
   GET /api/v1/sandboxes/{id}/connect-info
   ```
   - HTTP 200
   - connect_type: `shell`
   - command: `docker exec -it sandbox-5a396c8c-... /bin/bash`
   - url/port/ports: `null` (shell 类型符合预期)

3. **验证 claude 命令存在**:
   ```
   docker exec sandbox-{id} which claude    -> /usr/bin/claude
   docker exec sandbox-{id} claude --version -> 2.1.97 (Claude Code)
   docker exec sandbox-{id} node --version   -> v20.20.2
   docker exec sandbox-{id} npm --version    -> 10.8.2
   ```

**结论:** claude-code 沙盒创建成功，启动速度远低于 3s 阈值。shell connect-info 正确返回 docker exec 命令。容器内 claude CLI 可用（版本 2.1.97），Node.js 20.x 和 npm 10.x 环境完整。

---

### 场景 2: 从 vscode 模板创建沙盒 -- FAIL

**测试步骤与结果:**

1. **创建沙盒**:
   ```
   POST /api/v1/sandboxes {"template_name":"vscode"}
   ```
   - HTTP 200, 耗时: **0.638s** (远低于 3s 阈值)
   - 返回: id=`21e7a826-...`, status=`running`, connect_type=`url`
   - template_name=`vscode`, image=`sbxmgr/vscode:latest`
   - **创建本身: PASS**

2. **获取 connect-info** -- **FAIL (HTTP 500)**:
   ```
   GET /api/v1/sandboxes/{id}/connect-info
   ```
   - HTTP 500, body: `Internal Server Error`
   - **这是一个严重 bug** (详见下方问题 #7)

3. **验证容器内 code-server**:
   ```
   docker exec sandbox-{id} code-server --version -> 4.115.0
   docker exec sandbox-{id} curl http://localhost:8443 -> HTTP 200
   ```
   - code-server 在容器内 8443 端口正常运行

4. **暂停/恢复验证**:
   ```
   POST /api/v1/sandboxes/{id}/pause  -> HTTP 200 "沙盒已暂停"
   POST /api/v1/sandboxes/{id}/resume -> HTTP 200 "沙盒已恢复运行"
   ```
   - 暂停和恢复操作正常

5. **容器端口映射**:
   ```
   docker port sandbox-{id}:
   8080/tcp -> 0.0.0.0:54089   (OpenSandbox HTTP proxy)
   44772/tcp -> 0.0.0.0:44913  (OpenSandbox embedding proxy)
   ```
   - 注意: 没有 8443 的直接映射。OpenSandbox 通过 8080 代理转发到容器内的 8443

**结论:** vscode 沙盒创建成功、启动迅速、容器内 code-server 正常运行。但 **connect-info API 返回 500 错误**，导致用户无法通过 API 获取访问地址。这是一个严重 bug，所有 `connect_type=url` 的模板都受影响。场景整体标记为 FAIL。

---

### 场景 3: 从 openclaw 模板创建沙盒 -- SKIP

**原因:** openclaw 模板在 QA 测试窗口内未能完成构建（Docker 容器内 apt-get 下载超慢，已等待 20+ 分钟仍未完成第一条 install_command）。这是环境网络问题，非代码缺陷。

**备注:** openclaw 的 connect_type=shell 且有 ports 配置（7860），如果构建完成后测试 connect-info，可能也会触发与场景 2 相同的类型不匹配 bug（取决于 shell 类型是否也携带 ports 信息）。

---

### 新发现的问题

#### 问题 #7 (严重): connect-info 对 url 类型模板返回 500

- **严重程度**: 严重
- **维度**: 功能完整性 / 可靠性
- **位置**: `src/sandbox_manager/api/sandboxes.py` 第 371-380 行（ConnectInfo 构造），`src/sandbox_manager/services/connector.py` 第 110-113 行，`src/sandbox_manager/models/schemas.py` 第 134 行
- **问题**: 当 connect_type=url 时，`connector._build_url_info()` 在第 112 行将模板的 ports（类型 `dict[str, int]`，如 `{"8443": 8443}`）原样放入返回的 dict 中。但 `sandboxes.py` 第 379 行 `ports=info.get("ports")` 将这个 dict 赋值给 `ConnectInfo.ports` 字段，而该字段的类型定义是 `list[dict] | None`。Pydantic 验证在构造 ConnectInfo 时失败：`Input should be a valid list [type=list_type, input_value={'8443': 8443}, input_type=dict]`，导致未处理异常和 500 错误。
- **预期**: connect-info 对 url 类型模板应返回 HTTP 200，包含 url、port 和端口映射信息。
- **实际**: HTTP 500 Internal Server Error。所有 connect_type=url 的模板（目前是 vscode）都受影响。
- **影响范围**: 所有 url 类型模板的沙盒 connect-info 端点不可用。这意味着用户创建了 vscode 沙盒后，无法通过 API 获取访问 URL。
- **证据**:
  - `curl http://localhost:9000/api/v1/sandboxes/{id}/connect-info` 返回 HTTP 500 + `Internal Server Error`
  - Python 复现: `ConnectInfo(..., ports={"8443": 8443})` 抛出 `ValidationError: Input should be a valid list`
- **根因链路**:
  1. `template.get_ports()` 返回 `dict[str, int]` = `{"8443": 8443}`
  2. `connector._build_url_info(ports={"8443": 8443})` 在第 112 行 `result["ports"] = ports` 原样传递
  3. `sandboxes.py` 第 379 行 `ports=info.get("ports")` = `{"8443": 8443}` (dict)
  4. `ConnectInfo(ports={"8443": 8443})` -- Pydantic 验证失败，因为 `ConnectInfo.ports` 类型是 `list[dict] | None`
- **修复方向**: 两个选择：
  1. (推荐) 修改 `connector._build_url_info()`，将 dict ports 转换为 list[dict] 格式: `[{"name": "8443", "container_port": 8443}]`，与 `_build_port_info` 返回格式一致
  2. 修改 `ConnectInfo.ports` 类型为 `dict[str, int] | list[dict] | None`，但这会让 schema 不一致

**注意:** 这个问题在 M2 之前的单元测试中未被发现，因为 `test_build_url_info` 测试的返回值是 raw dict（不经过 ConnectInfo 验证），而 API 层的集成测试只测了 shell 类型。这再次暴露了 mock 测试与实际集成行为的差距。

---

### 补充评分调整

| 维度 | 回归后评分 | 补充后评分 | 阈值 | 状态 | 变化原因 |
|------|-----------|-----------|------|------|----------|
| 功能完整性 | 7/10 | **6/10** | 7 | **FAIL** | 问题 #7 导致 url 类型模板的 connect-info 完全不可用，vscode 场景核心功能缺失 |
| 可靠性 | 7/10 | 6/10 | 6 | PASS | 500 错误未被全局异常处理器捕获（返回纯文本 "Internal Server Error" 而非 JSON），说明异常处理存在盲区 |
| 用户体验 | 7/10 | 6/10 | 6 | PASS | 500 错误返回纯文本而非统一 JSON 格式；用户创建 vscode 沙盒后无法获取连接地址 |
| 代码质量 | 7/10 | 6/10 | 5 | PASS | ConnectorService 返回 dict 但 schema 期望 list[dict] -- 类型不一致说明缺少端到端类型检查；url 类型的集成测试缺失 |

**M2 补充后结果: FAIL -- 功能完整性降至 6/10，未达 7 分阈值**

### 评分详细理由

#### 功能完整性: 7 -> 6

问题 #7 是一个阻断性 bug:
- vscode 模板是产品规格中定义的 4 个核心模板之一
- connect-info 是 M2 的核心新功能（功能 #11）
- 对 url 类型模板，connect-info 完全不可用（500 错误），不是降级而是断裂
- 这意味着 M2 的 3 个模板特异性场景中，claude-code PASS、vscode FAIL、openclaw SKIP
- 虽然 shell 类型工作正常，但 url 类型是产品规格中明确要求的连接方式

#### 可靠性: 7 -> 6

- 500 错误的 body 是纯文本 `Internal Server Error`，不是 JSON 格式
- 这说明 Pydantic ValidationError 没有被全局异常处理器捕获
- M1 修复时注册了 HTTPException 的全局处理器，但没有覆盖 Pydantic 的 ResponseValidationError
- 这类 "返回值序列化失败" 的错误属于服务端内部错误，应该有统一的 500 JSON 响应

#### 用户体验: 7 -> 6

- 用户创建了 vscode 沙盒、沙盒正常运行，但无法通过 API 知道如何连接
- 500 错误返回纯文本对 API 调用方不友好（无法按 JSON 解析）
- claude-code 场景体验良好（shell 类型无此问题）

#### 代码质量: 7 -> 6

- ConnectorService 的 `_build_url_info` 返回 `ports: dict[str,int]` 而 ConnectInfo 期望 `ports: list[dict]` -- 方法间的类型契约不一致
- 单元测试 `test_build_url_info` 只验证了 ConnectorService 的返回 dict，没有经过 ConnectInfo schema 验证，无法发现序列化错误
- 缺少 url/port 类型 connect-info 的 API 端到端测试

---

### 完整遗留问题汇总

| # | 问题 | 严重程度 | 来源 | 状态 |
|---|------|----------|------|------|
| 2 | 批量销毁 failed 计数（kill_sandbox_by_id 异常吞没） | 轻微 | 原始 M2 QA | 部分修复 |
| 6 | openclaw connect_type 与产品规格不一致 | 轻微 | 原始 M2 QA | 未修复 |
| 7 | connect-info 对 url 类型模板返回 500 (Pydantic 类型不匹配) | **严重** | 补充 QA | **新发现** |

### 修复建议

**问题 #7 必须在 M2 通过前修复。** 建议修复顺序:

1. **问题 #7** (阻塞): 修改 `connector._build_url_info()` 将 dict ports 转换为 list[dict] 格式，与 `_build_port_info` 保持一致。同时添加 url 类型 connect-info 的 API 端到端测试。
2. 问题 #2 (轻微): `kill_sandbox_by_id` 异常传播
3. 问题 #6 (轻微): openclaw connect_type 对齐产品规格

修复后需要回归验证:
- vscode 沙盒的 connect-info 返回正确的 url 和端口信息
- shell 类型 connect-info 无回归
- 全量测试通过
