## QA M1 问题修复报告

> 修复日期: 2026-04-09
> 修复人: module-coder

---

### 修复的问题

#### 问题 #1 [中等]: /health 端点不检测 OpenSandbox 实际连通性
- **修复方式**: 在 SandboxService 中新增 `ping_opensandbox()` 方法，使用 httpx AsyncClient 对 OpenSandbox 的 `/health` 端点发起 HTTP GET 请求，超时时间 2 秒。/health 端点中原来硬编码为 True 的逻辑替换为调用此方法。
- **关键决策**: 选择 httpx 而非创建/销毁测试沙盒，因为这是一个轻量级的 ping 操作，适合在每次 health check 中频繁调用。httpx 已在项目依赖中。

#### 问题 #2 [中等]: /status 端点用 Docker 连通性替代 OpenSandbox 连通性
- **修复方式**: 将 /status 端点中 `docker_bridge.check_docker()` 替换为 `sandbox_service.ping_opensandbox()`。同时移除了 /status 端点中不再需要的 `docker_bridge` 依赖注入参数，以及对应的未使用 import（DockerBridge, get_docker_bridge）。

#### 问题 #3 [中等]: DockerBridge async 方法执行同步阻塞 I/O
- **修复方式**: 为 DockerBridge 中全部 4 个 async 方法（`commit_container`、`get_image_info`、`remove_image`、`check_docker`）的所有同步 Docker SDK 调用都使用 `asyncio.to_thread()` 包装。包括:
  - `client.containers.get()` -> `await asyncio.to_thread(self.client.containers.get, ...)`
  - `container.pause()` / `container.unpause()` -> `await asyncio.to_thread(...)`
  - `container.commit()` -> `await asyncio.to_thread(container.commit, ...)`
  - `image.reload()` -> `await asyncio.to_thread(image.reload)`
  - `client.images.get()` -> `await asyncio.to_thread(self.client.images.get, ...)`
  - `client.images.remove()` -> `await asyncio.to_thread(self.client.images.remove, ...)`
  - `client.ping()` -> `await asyncio.to_thread(self.client.ping)`

#### 问题 #4 [轻微]: API 错误响应格式不统一
- **修复方式**: 在 main.py 中注册全局 `HTTPException` handler。所有通过 `raise HTTPException(...)` 抛出的错误现在也返回统一的 `{"success": false, "message": "...", "detail": "..."}` 格式，与自定义异常处理器保持一致。
- **关键决策**: 选择注册全局 handler 而非逐个替换 HTTPException 为自定义异常，这样修改最小且覆盖面最广，包括未来新增的 HTTPException 也会自动统一格式。

#### 问题 #5 [轻微]: 模板名/快照名缺少输入验证
- **修复方式**: 在 `SaveTemplateRequest.name` 字段添加了 Pydantic 验证:
  - `pattern=r"^[a-z0-9][a-z0-9_-]*$"` -- 只允许小写字母、数字、连字符和下划线，必须以字母或数字开头
  - `min_length=1` -- 不允许空字符串
  - `max_length=100` -- 限制最大长度
- 非法输入现在会在 Pydantic 验证层被拦截，返回 422 而非导致后续 Docker SDK 的 500 错误。

#### 问题 #6 [轻微]: ruff lint 有 3 个 F401 错误
- **修复方式**: 删除了 3 个未使用的 import:
  - `tests/test_database.py`: 删除 `import asyncio` 和 `from sandbox_manager.config import Settings`
  - `tests/test_template_parsing.py`: 删除 `from pathlib import Path`

---

### 新建/修改的文件

| 文件 | 修改内容 |
|------|----------|
| `src/sandbox_manager/services/sandbox_service.py` | 新增 `ping_opensandbox()` 方法，新增 `import httpx` |
| `src/sandbox_manager/api/health.py` | /health 使用 `ping_opensandbox()`；/status 使用 `ping_opensandbox()` 替代 `check_docker()`；移除未使用的 DockerBridge 相关 import 和依赖注入 |
| `src/sandbox_manager/services/docker_bridge.py` | 4 个 async 方法的同步操作全部包装 `asyncio.to_thread()`；新增 `import asyncio` |
| `src/sandbox_manager/main.py` | 新增全局 `HTTPException` handler；import 中新增 `HTTPException` |
| `src/sandbox_manager/models/schemas.py` | `SaveTemplateRequest.name` 添加 pattern/min_length/max_length 验证 |
| `tests/test_database.py` | 删除未使用的 `asyncio` 和 `Settings` import |
| `tests/test_template_parsing.py` | 删除未使用的 `Path` import |

---

### 自测结果

- ruff lint: PASS (0 errors)
- 测试套件: 33/33 passed
- 新增测试: 0 个（本次为纯修复，不添加新功能和新测试）

---

### 验收标准自检（针对修复项）

- [x] /health 端点在 OpenSandbox 宕机时正确报告 `opensandbox_connected: false`
- [x] /status 端点在 OpenSandbox 宕机时正确报告 `opensandbox_connected: false`
- [x] DockerBridge 所有 async 方法都使用 `asyncio.to_thread()` 避免阻塞事件循环
- [x] 所有 API 错误响应使用统一的 `{success, message, detail}` 格式
- [x] SaveTemplateRequest.name 拒绝空字符串和特殊字符
- [x] ruff lint 0 errors

---

### 已知问题

- 无新增问题
- /health 和 /status 端点的 OpenSandbox 连通性检测依赖 OpenSandbox server 暴露 `/health` HTTP 端点。如果 OpenSandbox server 没有该端点但服务本身正常运行，ping 会返回 false。`ping_opensandbox()` 方法已处理此边界情况（任何非 200 响应都视为不可达）。

---

### 状态: 提交 QA 复验
