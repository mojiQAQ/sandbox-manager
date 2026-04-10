## 里程碑 M3 交付报告

### 本轮实现的功能

- **功能 #15 一键启动命令**: `sbx start <template-name>` 实现了创建沙盒 + 等待就绪 + 自适应连接的完整流程。未构建模板时给出明确引导（提示执行 `sbx template build`）。正在构建/构建失败的模板也有对应提示。shell 类型使用 `os.execvp` 替换进程进入 docker exec，url 类型自动打开浏览器，port 类型打印端口映射表。`--json` 模式输出纯 JSON 不混入 Rich 格式文本。

- **功能 #16 沙盒管理命令组**: 实现了 `sbx list`（表格展示）、`sbx connect`（自适应连接）、`sbx stop`（停止/`--all` 批量停止）、`sbx rm`（销毁/`--all` 批量销毁）、`sbx pause`（暂停）、`sbx resume`（恢复）。所有命令支持 `--json` 输出，沙盒 ID 支持前缀匹配（多匹配时提示disambiguation）。

- **功能 #17 模板管理命令组**: 实现了 `sbx template list`（表格展示模板状态）、`sbx template build`（单个构建 + 轮询进度/`--all` 批量构建未构建模板）、`sbx template init`（生成带注释的 YAML 脚手架文件）、`sbx template show`（Rich Panel 展示详情）、`sbx template rm`（删除模板）、`sbx snapshot`（将运行中沙盒保存为模板）。

- **功能 #18 系统管理命令**: 实现了 `sbx status`（Rich Panel 展示系统状态）、`sbx config show`（显示当前配置含 config.yaml 内容）、`sbx config set`（修改并保存到 ~/.sandbox-manager/config.yaml）、`sbx version`（显示版本号）。

### 新建/修改的文件

- `src/sandbox_manager/cli.py` -- CLI 完整实现，包含所有命令（约 630 行）
- `tests/test_m3_cli.py` -- CLI 测试，48 个测试用例，覆盖所有命令和错误场景
- `pyproject.toml` -- 将 typer/rich 从 optional-dependencies 移到 dependencies，添加 `[project.scripts] sbx` 入口

### 自测结果

- ruff lint: 0 errors (全项目 src/ + tests/)
- 测试套件: 115/115 passed (67 旧 + 48 新)
- 新增测试: 48 个

### 验收标准自检

#### 核心体验
- [x] `sbx start claude-code` -> 创建沙盒 + 自适应连接（shell 类型 os.execvp）
- [x] `sbx start vscode` -> 创建沙盒 + 自动打开浏览器（url 类型 webbrowser.open）
- [x] `sbx start python-dev` -> 创建沙盒 + 进入终端
- [x] `sbx start` 支持 `--json` 输出纯 JSON

#### 管理命令
- [x] `sbx list` -> 整洁表格，列宽自适应
- [x] `sbx connect <id>` -> 前缀匹配 + 自适应连接
- [x] `sbx stop <id>` -> 停止沙盒
- [x] `sbx stop --all` -> 停止所有沙盒
- [x] `sbx rm <id>` -> 销毁沙盒
- [x] `sbx rm --all` -> 销毁所有沙盒
- [x] `sbx pause <id>` -> 暂停沙盒
- [x] `sbx resume <id>` -> 恢复沙盒
- [x] 所有命令支持 `--json` 输出格式

#### 模板管理
- [x] `sbx template list` -> 表格展示所有模板及状态
- [x] `sbx template build <name>` -> 构建 + 轮询进度（Rich spinner）
- [x] `sbx template build --all` -> 构建所有未构建模板
- [x] `sbx template init <name>` -> 生成 YAML 脚手架文件
- [x] `sbx template show <name>` -> Rich Panel 展示详情
- [x] `sbx template rm <name>` -> 删除模板
- [x] `sbx snapshot <id> --name <name>` -> 保存沙盒为模板

#### 引导体验
- [x] 模板未构建时提示用户执行 `sbx template build`
- [x] `sbx status` -> Rich Panel 展示系统状态

#### 错误体验
- [x] API 服务未启动 -> 友好 Panel 提示（含排查步骤）而非连接超时
- [x] 输入错误的模板名 -> 提示不存在（API 返回 404）
- [x] 输入错误的沙盒 ID -> "找不到以 xxx 开头的沙盒" + 列出可用沙盒

#### JSON 输出
- [x] `sbx list --json` -> 使用 print() 输出纯净合法 JSON（不经过 Rich 处理）

### 已知问题

- Rich Table 在窄终端下会截断长文本（如 "python-dev" -> "python-d..."），这是 Rich 的正常行为，不影响使用
- `sbx template build --all` 在构建多个模板时采用串行轮询方式（每个模板构建完才开始下一个），如果后续需要并行构建可以优化
- `sbx stop` 命令实际调用的是 DELETE API（与 rm 相同），因为当前 API 没有区分 stop 和 rm。如果后续需要区分"停止但保留容器"和"彻底销毁"，需要增加 stop API 端点

### 状态: 提交 QA
