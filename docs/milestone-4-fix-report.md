## 里程碑 M4 QA 修复报告

修复日期: 2026-04-09

### 修复的问题

#### 问题 #1 [严重]: 停止按钮实际执行删除操作
- **修复方式**: 移除停止按钮。因为后端没有 stop 端点（OpenSandbox 只有 pause 和 kill/delete），停止按钮在此系统中无语义意义。保留暂停和删除两个操作，删除已有 Popconfirm 确认。
- **决策依据**: QA 报告建议的三种方案中，移除停止按钮是最简洁且语义最正确的选择。

#### 问题 #2 [严重]: 终端无法交互（docker exec 缺少 PTY）
- **修复方式**: 将后端 `ws_terminal.py` 从 `asyncio.subprocess` 方案重写为 Docker SDK 方案。使用 `client.api.exec_create(tty=True)` + `client.api.exec_start(tty=True, socket=True)` 分配真正的 PTY，支持输入回显、PS1 提示符、行编辑等完整交互功能。
- **前端配合**: Terminal.tsx 更新为 binary 传输模式（`ws.binaryType = 'arraybuffer'`），发送和接收均使用 bytes 而非 text，与 Docker socket 的原始字节流对齐。
- **决策依据**: Docker SDK 已在项目依赖中（`docker>=7.0.0`），项目已有 `DockerBridge` 类使用 Docker SDK 的模式。

#### 问题 #3 [中等]: 缺少 404 路由处理
- **修复方式**: 在 `App.tsx` 的 Routes 末尾添加 `<Route path="*" element={<Navigate to="/" replace />} />`，将所有未匹配路由重定向到 Dashboard。
- **决策依据**: 作为 MVP 单页应用，重定向到首页比显示 404 页面更友好。

#### 问题 #4 [轻微]: Ant Design 废弃 API
- **修复方式**: Dashboard.tsx 中 4 处 `bordered={false}` 改为 `variant="borderless"`，4 处 `valueStyle={{...}}` 改为 `styles={{ value: {...} }}`。
- **决策依据**: 遵循 Ant Design 5.x 新版 API，消除控制台 deprecation 警告。

#### 问题 #5 [轻微]: 操作按钮缺少文字标签
- **修复方式**: Sandboxes 页面操作列按钮添加中文文字标签（终端、暂停/恢复、快照、删除），同时保留 Tooltip。操作列宽度从 280px 增加到 340px。
- **决策依据**: 文字标签让首次使用的用户不需要逐个 hover 就能理解按钮功能。

### 新建/修改的文件
- `web/src/pages/Sandboxes.tsx` -- 移除停止按钮、添加操作按钮文字标签
- `web/src/pages/Dashboard.tsx` -- 替换废弃 API（bordered, valueStyle）
- `web/src/pages/Terminal.tsx` -- 切换到 binary WebSocket 传输模式
- `web/src/App.tsx` -- 添加 404 catch-all 路由重定向
- `src/sandbox_manager/api/ws_terminal.py` -- 重写为 Docker SDK PTY 方案

### 自测结果
- TypeScript (`tsc --noEmit`): 零错误
- ESLint: 零错误
- ruff check (`python3 -m ruff check src/`): All checks passed
- 后端测试 (`pytest tests/`): 118/118 passed

### 验收标准自检
- [x] Sandboxes 停止操作: 已移除停止按钮，不再有误删风险
- [x] Terminal 交互: 已使用 Docker SDK tty=True 方案，支持完整 PTY
- [x] 404 路由处理: 未匹配路由自动重定向到 Dashboard
- [x] Ant Design 废弃 API: 全部替换为新版 API
- [x] 操作按钮文字标签: 4 个按钮均有中文文字标签

### 已知问题
- 无新增已知问题

### 状态: 提交 QA 复审
