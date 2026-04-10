## 里程碑 M2 交付报告

### 本轮实现的功能

- **功能 #10: 沙盒创建增强** -- 创建沙盒时自动使用模板定义的 entrypoint 作为启动命令（已在 M1 的 OpenSandbox SDK create 调用中传入 entrypoint 参数实现），未构建模板创建时返回明确错误提示。
- **功能 #11: 自适应连接** -- 新增 ConnectorService 和 `GET /api/v1/sandboxes/{id}/connect-info` 端点。根据模板的 connect_type 返回：shell 类型返回 docker exec 命令，url 类型通过 OpenSandbox SDK get_endpoint 获取访问 URL（失败时回退 localhost），port 类型返回端口映射列表。连接前检查沙盒状态，暂停/停止时给出明确提示。
- **功能 #12: 沙盒列表增强** -- list 和 detail 端点现在会通过 DockerBridge.get_container_status 同步 Docker 容器实际状态，数据库中的状态与容器不一致时自动更新。支持 `?status=running|paused|stopped` 按状态筛选。
- **功能 #13: 沙盒暂停与恢复** -- 新增 SandboxService.pause_sandbox/resume_sandbox 方法封装 OpenSandbox SDK 的 pause/resume 调用。新增 `POST /api/v1/sandboxes/{id}/pause` 和 `/resume` 端点，包含完整的状态校验（已暂停不能再暂停、未暂停不能恢复等）。
- **功能 #14: 批量销毁** -- 新增 `DELETE /api/v1/sandboxes?all=true` 批量销毁端点，遍历所有活跃沙盒逐一 kill。单个沙盒销毁增强：无论沙盒处于什么状态（running/paused）都直接 kill。

### 新建/修改的文件

**新建:**
- `src/sandbox_manager/services/connector.py` -- 自适应连接器服务，根据 connect_type 生成 shell/url/port 三种连接信息
- `tests/test_m2_sandbox_management.py` -- M2 测试套件，30 个测试覆盖所有新功能和边界情况

**修改:**
- `src/sandbox_manager/services/sandbox_service.py` -- 新增 pause_sandbox、resume_sandbox、get_endpoint 三个方法
- `src/sandbox_manager/services/docker_bridge.py` -- 新增 get_container_status 方法，用于查询容器实际状态
- `src/sandbox_manager/api/sandboxes.py` -- 新增 pause、resume、connect-info、批量删除端点；增强 list 和 detail 端点的状态同步；重构为使用辅助函数减少重复代码
- `src/sandbox_manager/models/schemas.py` -- 新增 ConnectInfo、BatchDeleteResponse schema
- `src/sandbox_manager/dependencies.py` -- 新增 ConnectorService 依赖注入

### 自测结果

- ruff lint: 0 errors
- 测试套件: 63/63 passed (33 M1 + 30 M2)
- 新增测试: 30 个

### 验收标准自检

- [x] 功能 #10: 从模板创建沙盒，自动执行模板定义的启动命令（通过 entrypoint 参数传入 OpenSandbox SDK）
- [x] 功能 #10: 模板未构建时给出明确提示（返回 400 + 提示信息）
- [x] 功能 #11: shell 类型返回 docker exec 命令
- [x] 功能 #11: url 类型返回访问 URL（通过 OpenSandbox get_endpoint 获取）
- [x] 功能 #11: port 类型返回端口映射列表
- [x] 功能 #11: 连接前检查沙盒状态，暂停时提示恢复，停止时提示无法连接
- [x] 功能 #11: 不存在的沙盒返回 404
- [x] 功能 #12: 列表同步 Docker 容器实际状态
- [x] 功能 #12: 支持按状态筛选 (?status=running|paused|stopped)
- [x] 功能 #13: 暂停运行中的沙盒 -> 状态变为 paused
- [x] 功能 #13: 恢复已暂停的沙盒 -> 状态变为 running
- [x] 功能 #13: 暂停已暂停的沙盒 -> 返回 400 错误
- [x] 功能 #13: 恢复未暂停的沙盒 -> 返回 400 错误
- [x] 功能 #14: 销毁单个沙盒 -> 容器被移除 + 数据库记录删除
- [x] 功能 #14: 批量销毁 (DELETE /api/v1/sandboxes?all=true) -> 所有沙盒被移除
- [x] 功能 #14: 批量销毁需显式传入 all=true，否则返回 400

### QA-M2 验收场景对照

| # | 场景 | 状态 | 说明 |
|---|------|------|------|
| 1 | 从 claude-code 模板创建沙盒 -> 启动 <=3s -> shell 连接 | 需集成测试 | API 逻辑已实现，启动速度取决于 OpenSandbox + 本地镜像 |
| 2 | 从 vscode 模板创建 -> url 连接 | 需集成测试 | connect-info 端点会通过 get_endpoint 获取 URL |
| 3 | 从 openclaw 模板创建 -> port 信息 | 需集成测试 | connect-info 端点会返回端口映射列表 |
| 4 | 从 python-dev 创建 -> import numpy | 需集成测试 | 取决于模板构建是否成功 |
| 5 | 列出所有沙盒 -> 显示运行中 | 已测试 | list 端点同步容器状态 |
| 6 | 暂停沙盒 -> 状态变为 paused | 已测试 | pause 端点 + 状态校验 |
| 7 | 恢复沙盒 -> 状态变为 running | 已测试 | resume 端点 + 状态校验 |
| 8 | 销毁单个沙盒 -> 容器被移除 | 已测试 | delete 端点 |
| 9 | 批量销毁所有沙盒 | 已测试 | delete?all=true 端点 |
| 10 | 已暂停沙盒的 connect-info -> 提示已暂停 | 已测试 | 返回 message 提示 |
| 11 | 不存在沙盒的 connect-info -> 404 | 已测试 | 返回 404 |
| 12 | 未构建模板创建沙盒 -> 提示未构建 | 已测试 | 返回 400 + 提示 |

### 已知问题

- 启动时间 <=3s 的验收需要在真实环境（OpenSandbox server + 已构建模板镜像）中测试，单元测试无法验证实际性能。
- `get_endpoint` 方法依赖 OpenSandbox SDK 的实际行为，endpoint 对象的属性结构需要在集成测试中验证。如果 SDK 返回的 endpoint 对象没有 `.endpoint` 属性，代码已有 fallback 到 `str(endpoint)`。
- 就绪检查（ready_check）功能：当前模板 YAML 中未定义 ready_check 字段，因此创建后不会执行就绪检查。如果未来需要此功能，需要在模板配置中新增 ready_check 字段并在创建流程中实现轮询检查逻辑。

### 状态: 提交 QA
