## 里程碑 M2 QA 修复报告

### 修复的 QA 问题

#### 问题 #1 [中等]: pause/resume 端点未同步 Docker 实际状态导致 500 错误
- **修复方式**: 抽取公共辅助函数 `_sync_sandbox_status(session, sandbox, docker_bridge)`，在 pause/resume 端点的状态校验前调用。同时重构 get_sandbox 和 get_connect_info 端点复用此函数，消除内联重复代码。
- **关键决策**: pause/resume 端点新增 `docker_bridge: DockerBridge = Depends(get_docker_bridge)` 依赖参数，与 GET 端点保持一致的状态同步策略。list_sandboxes 因批量处理特殊性保留原有内联逻辑（统一 commit 而非逐个 commit）。
- **效果**: 外部 `docker pause/unpause` 后，API 能正确同步状态并返回 400（状态不匹配）而非 500。

#### 问题 #2 [中等]: 批量销毁的 failed 计数永远为 0
- **修复方式**: 将 `delete_all_sandboxes` 的 except 分支中 `deleted += 1` 改为 `failed += 1`。
- **效果**: 批量销毁部分失败时，failed 计数正确反映 Docker 层面的失败数量。

#### 问题 #3 [轻微]: connect-info 对暂停/停止状态返回 HTTP 200
- **修复方式**: 改为 `raise HTTPException(status_code=409, detail=...)`，与项目统一的异常响应格式保持一致（通过全局 http_exception_handler 统一序列化）。
- **关键决策**: 使用字符串 detail 而非 dict detail，因为全局异常处理器会将 dict 转为 str()，破坏结构化数据。保持与项目其他 HTTPException 用法一致。

#### 问题 #4 [轻微]: 单个销毁端点缺少异常保护
- **修复方式**: 为 `delete_sandbox` 的 `kill_sandbox_by_id` 调用添加 try/except 包裹。kill 失败时记录 warning 日志，仍然继续删除数据库记录（与批量销毁行为一致）。

#### 问题 #5 [轻微]: 沙盒列表 N+1 查询
- **修复方式**: 在 `list_sandboxes` 函数中添加 TODO 注释，说明可用 joinedload 批量加载模板、用一次 docker ps 批量获取容器状态。MVP 阶段沙盒数量 < 20，不阻塞发布。

### 新建/修改的文件
- `src/sandbox_manager/api/sandboxes.py` -- 核心修复：新增 `_sync_sandbox_status` 辅助函数；重构 detail/connect-info 使用统一同步函数；pause/resume 添加状态同步；connect-info 暂停/停止改为 409；批量销毁 failed 计数修正；单个销毁添加异常保护；list 添加 N+1 TODO
- `tests/test_m2_sandbox_management.py` -- 更新已有测试适配行为变更；新增 4 个测试覆盖 QA 发现的缺失场景

### 自测结果
- lint/typecheck: ruff check 0 errors
- 测试套件: 67/67 passed (0 回归)
- 新增测试: 4 个
  - `TestPauseResumeDockerSync::test_pause_after_external_docker_pause` -- 外部 docker pause 后 API pause 返回 400
  - `TestPauseResumeDockerSync::test_resume_after_external_docker_unpause` -- 外部 docker unpause 后 API resume 返回 400
  - `TestBatchDeleteFailedCount::test_batch_delete_partial_failure` -- 批量销毁部分失败时 failed 计数正确
  - `TestDeleteSandboxExceptionHandling::test_delete_single_kill_failure` -- 单个销毁 kill 失败时仍返回 200

### 验收标准自检
- [x] pause/resume 端点在操作前同步 Docker 容器实际状态
- [x] 外部 docker pause 后 API pause 返回 400 而非 500
- [x] 外部 docker unpause 后 API resume 返回 400 而非 500
- [x] 批量销毁部分失败时 failed 计数正确
- [x] connect-info 对暂停/停止状态返回 HTTP 409
- [x] 单个销毁端点有异常保护
- [x] N+1 查询标记 TODO

### 已知问题
- QA 报告中的问题 #6（openclaw 模板 connect_type 与产品规格不一致）未在本次修复范围内，因为用户只要求修复 5 个问题且问题 #6 跨 M1/M2 边界

### 状态: 提交 QA
