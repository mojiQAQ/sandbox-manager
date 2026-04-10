## 里程碑 M3 QA 修复报告

### 修复的问题

按 QA 评审报告 (`docs/qa-m3-report.md`) 优先级排序:

- **问题 #2 [严重]** -- 超时异常未捕获: 在 `_api_get`/`_api_post`/`_api_delete` 三个 HTTP helper 中增加 `httpx.TimeoutException` 捕获，显示友好的超时提示 Panel，而非暴露 Python 堆栈跟踪。新增 `_print_timeout_error()` 函数。

- **问题 #6 [中等]** -- 批量操作未使用长超时: `stop --all` 和 `rm --all` 的 `_api_delete` 调用传入 `timeout=API_LONG_TIMEOUT`（300s），避免批量删除容器时触发 10s 默认超时。

- **问题 #1 [中等]** -- `sbx stop` 与 `sbx rm` 语义区分: `stop` 命令输出 "已停止"，`rm` 输出 "已销毁"。帮助文本明确说明 stop = 停止并释放资源（等价于 rm），建议使用 `sbx pause` 保留沙盒状态。两个命令的消息不再依赖 API 返回的 message 字段，CLI 层使用固定措辞。

- **问题 #5 [中等]** -- vscode URL 缺少 http:// 前缀: 在 `connector.py` 的 `_build_url_info` 和 `_build_port_info` 中，对 OpenSandbox SDK 返回的 endpoint URL 检查是否缺少协议前缀，缺少则补全 `http://`。

- **问题 #3 [轻微]** -- `template build --all` 的 results 列表重复: 删除触发构建成功后的第一次 `results.append`，每个模板只在构建完成（或失败）后追加一条记录。

- **问题 #4 [轻微]** -- 连接暂停沙盒暴露 API 路径: 在 `_handle_api_error` 中对 HTTP 409 响应做特殊处理，当消息包含 "暂停" 时替换为 CLI 友好提示 "沙盒已暂停，请先执行: sbx resume <id>"。

- **问题 #7 [轻微]** -- `nullcontext` 重复导入: 将 `from contextlib import nullcontext` 移到文件顶部 import 区域，删除 `start` 函数内两处重复的局部导入。

### 未修复

- **问题 #8 [轻微]** -- 缺少集成测试: 按任务要求暂不添加，后续单独处理。

### 新建/修改的文件

- `src/sandbox_manager/cli.py` -- 7 个问题的修复主文件
- `src/sandbox_manager/services/connector.py` -- 问题 #5 URL 前缀补全
- `tests/test_m3_cli.py` -- 更新已有测试 + 新增 3 个测试用例

### 自测结果

- ruff lint: 0 errors
- 测试套件: 118/118 passed（原 115 + 新增 3）
- 新增测试:
  - `test_timeout_error_friendly_message` -- 验证 GET 请求超时显示友好消息
  - `test_timeout_on_delete` -- 验证 DELETE 请求超时显示友好消息
  - `test_connect_paused_sandbox_friendly_message` -- 验证 409 暂停沙盒显示 CLI 命令而非 API 路径

### 验收标准自检

- [x] 问题 #2: httpx.TimeoutException 被捕获，显示友好提示
- [x] 问题 #6: 批量操作使用 API_LONG_TIMEOUT (300s)
- [x] 问题 #1: stop 输出 "已停止"，rm 输出 "已销毁"，帮助文本区分语义
- [x] 问题 #5: URL 缺少协议前缀时自动补全 http://
- [x] 问题 #3: template build --all 的 JSON 输出中每个模板只出现一次
- [x] 问题 #4: 连接暂停沙盒时显示 "sbx resume <id>" 而非 API 路径
- [x] 问题 #7: nullcontext 在文件顶部导入一次，无重复

### 已知问题

- 无新增已知问题

### 状态: 提交 QA 复审
