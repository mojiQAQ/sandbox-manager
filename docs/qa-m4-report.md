## QA 评审报告 -- 里程碑 M4: Web 管理界面

评审日期: 2026-04-09

### 评分摘要

| 维度 | 分数 | 阈值 | 状态 |
|------|------|------|------|
| 功能完整性 | 6/10 | 7 | FAIL |
| 可靠性 | 6/10 | 6 | PASS |
| 用户体验 | 7/10 | 6 | PASS |
| 代码质量 | 7/10 | 5 | PASS |

**里程碑结果: FAIL -- 功能完整性未达阈值**

### 评分理由

**功能完整性 6/10**: "停止"按钮实际调用删除 API 是一个破坏性语义错误。终端页面虽然连接成功但无法交互（无输入回显、无命令输出、无 shell prompt），等于该功能不可用。两个核心功能存在实质问题，且没有 404 路由处理。尽管 Dashboard、模板管理、创建弹窗等多数功能工作正常，但存在的问题直接影响核心使用场景，给 6 分。

**可靠性 6/10**: API 错误拦截器有统一处理，表单验证有效，轮询中的异常被静默处理不会中断 UI。但"停止"按钮无确认就直接删除沙盒是一个数据安全风险。其他操作的错误路径处理合理。刚好达到阈值。

**用户体验 7/10**: 赛博朋克暗色主题视觉一致性高，hover 发光效果、loading 状态、状态徽标颜色映射等细节打磨到位。中文界面完整。Ant Design 的布局和表格组件使用规范。侧边栏导航、面包屑菜单高亮都正确。但操作按钮只有图标无文字标签（需 hover 看 tooltip），不存在的路由显示空白页。

**代码质量 7/10**: TypeScript 和 ESLint 零错误，后端 118 个测试全部通过。代码组织清晰，命名规范，组件拆分合理。类型定义完整映射后端 schema。usePolling hook 正确处理了 cleanup。但 Ant Design 废弃 API 使用（`bordered`, `valueStyle`）、前端无单元测试、构建产物未做代码分割（单 chunk 1.45MB）是扣分项。

### 验收标准验证

- [x] PASS Dashboard 页面：4 个统计卡片显示正确（连接状态/活跃沙盒/已构建模板 3/4/系统版本 0.1.0）
- [x] PASS Dashboard 快速启动：4 个模板卡片，3 个 ready 可启动，1 个 failed 可构建
- [x] PASS Dashboard 快速启动点击"启动"可创建沙盒并跳转到沙盒管理页
- [x] PASS Sandboxes 创建弹窗：模板选择和自定义镜像双模式，表单验证有效
- [x] PASS Sandboxes 快照弹窗：名称必填校验 + 描述，提示文字正确
- [x] PASS Sandboxes 暂停/恢复：状态正确切换，按钮图标随状态变化，disabled 状态正确
- [x] FAIL Sandboxes 停止操作：停止按钮实际执行删除操作而非停止
- [x] PASS Sandboxes 删除操作：有 Popconfirm 确认弹窗
- [x] PASS Sandboxes 表格：5 秒自动轮询、行选择、分页、ID 截断 + tooltip + 复制
- [x] PASS Templates 列表：4 个模板完整展示，状态/来源/连接类型/镜像大小正确
- [x] PASS Templates 构建按钮：对 failed 模板可用，触发构建后弹窗显示进度
- [x] PASS Templates 删除：有 Popconfirm 确认
- [x] PASS Terminal 页面渲染：xterm.js 组件正确渲染，顶栏显示沙盒 ID/模板名/状态/连接指示灯
- [x] FAIL Terminal 交互：WebSocket 连接成功但无法在终端中看到输入或输出
- [x] PASS 赛博朋克深色主题：主背景 #0a0e17，霓虹青 #06b6d4，视觉一致
- [x] PASS 所有 UI 文字使用中文
- [x] PASS 侧边栏导航：三个菜单项正确高亮，路由切换正常
- [x] FAIL 404 路由处理：访问不存在的路由显示空白页

### 问题列表

#### 问题 #1: 停止按钮实际执行删除操作
- **严重程度**: 严重
- **维度**: 功能完整性 / 可靠性
- **位置**: `web/src/pages/Sandboxes.tsx:224`
- **问题**: "停止"按钮 (`StopOutlined`) 的 `onClick` 调用的是 `handleDelete(record.id)`，与"删除"按钮使用同一个处理函数。用户认为是停止（保留沙盒数据），实际上是永久删除。
- **预期**: 停止按钮应调用独立的 stop API 或者至少应有确认对话框说明操作将删除沙盒。
- **实际**: 点击停止按钮后沙盒立即从列表消失，无任何确认提示，调用了 `DELETE /api/v1/sandboxes/{id}`。
- **证据**: 截图 `after-stop.png` -- 点击停止后表格立即变为"暂无沙盒"。代码第 224 行 `onClick={() => handleDelete(record.id)}`。
- **修复方向**: (1) 由于后端没有 stop 端点，可以移除停止按钮（停止在此系统中无意义，只有暂停和删除）；(2) 或者将停止按钮改为调用 pause 然后再 delete 的组合操作，并添加 Popconfirm 确认；(3) 最简单的方案是移除停止按钮，只保留暂停和删除。

#### 问题 #2: 终端页面无法交互 -- 无输入回显和命令输出
- **严重程度**: 严重
- **维度**: 功能完整性
- **位置**: `src/sandbox_manager/api/ws_terminal.py:36-44`
- **问题**: WebSocket 连接成功（顶栏显示"已连接"），但终端中无法看到任何键盘输入或命令执行结果。根本原因是 `docker exec -i` 没有 `-t` 选项，不分配 PTY。没有 PTY 意味着: (a) bash 进入非交互模式，不显示 PS1 提示符；(b) 终端驱动不做输入回显；(c) 部分命令行编辑功能不可用。
- **预期**: 用户输入 `echo hi` 并回车后应能看到 `echo hi` 的回显和 `hi` 的输出。
- **实际**: 终端只显示初始的三行连接信息（"--- Sandbox Terminal ---"、"正在连接到沙盒 xxx..."、"已连接"），之后任何键盘输入都看不到回显，也看不到命令输出。
- **证据**: 截图 `terminal-after-command.png` -- 输入 "echo hi" + Enter 后终端仍然只有三行初始文本。
- **修复方向**: 此问题被标记为"已知限制"（asyncio subprocess 不支持 PTY）。建议改用以下方案之一: (1) 使用 Python `pty` 模块在子进程中分配伪终端；(2) 使用 `socat` 或 `script` 命令包裹 `docker exec` 来获得 PTY；(3) 使用 Docker SDK 的 exec API 加上 `tty=True` 参数。

#### 问题 #3: 缺少 404 路由处理
- **严重程度**: 中等
- **维度**: 用户体验
- **位置**: `web/src/App.tsx:15-21`
- **问题**: 路由配置中没有 catch-all (`path="*"`) 路由。访问不存在的 URL 时，页面显示纯色空白背景，没有侧边栏，没有任何提示信息。
- **预期**: 应显示包含侧边栏的 404 提示页面，或自动重定向到 Dashboard。
- **实际**: 完全空白的深色页面，用户无法导航回任何功能页面。
- **证据**: 截图 `404-route.png` -- 纯黑背景无任何内容。
- **修复方向**: 在 Routes 中添加 `<Route path="*" element={<Navigate to="/" />} />` 或一个 NotFound 组件。

#### 问题 #4: Ant Design 废弃 API 使用
- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `web/src/pages/Dashboard.tsx`（推断，基于 console 错误消息）
- **问题**: 使用了 Ant Design 已废弃的 `bordered` 属性和 `valueStyle` 属性，控制台输出两条 deprecation 警告。
- **预期**: 使用新版 API -- `variant` 替代 `bordered`，`styles.content` 替代 `valueStyle`。
- **实际**: 控制台显示 `[antd: Card] bordered is deprecated` 和 `[antd: Statistic] valueStyle is deprecated`。
- **证据**: Playwright console 日志捕获的 2 条 error 级别消息。
- **修复方向**: 将 `bordered` 改为 `variant="borderless"`，将 `valueStyle={{...}}` 改为 `styles={{ content: {...} }}`。

#### 问题 #5: 操作按钮缺少可见文字标签
- **严重程度**: 轻微
- **维度**: 用户体验
- **位置**: `web/src/pages/Sandboxes.tsx:191-256`
- **问题**: 沙盒列表操作列的 5 个按钮全部只有图标，没有可见的文字标签。用户必须逐个 hover 查看 tooltip 才能知道按钮功能。虽然 tooltip 存在且正确（"连接终端"、"暂停"、"停止"、"快照"、"删除"），但对首次使用的用户不够直观。
- **预期**: 至少对破坏性操作（停止/删除）提供可见文字标签，或在按钮密度较低时显示文字。
- **实际**: 5 个纯图标按钮排列在一起，不 hover 无法区分功能。
- **证据**: 截图 `after-launch-claude-code.png` 中操作列只有图标。
- **修复方向**: 可接受的方案是保持图标按钮但确保 tooltip 延迟较短；更好的方案是为关键操作添加文字标签。

#### 问题 #6: 构建产物未做代码分割
- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `web/vite.config.ts`
- **问题**: 生产构建产出单个 JS chunk 1.45 MB（gzip 后 ~445 KB）。xterm.js 和 Ant Design 是两个体积较大的依赖，完全可以通过 dynamic import 做代码分割。
- **预期**: 按路由做 code splitting，Terminal 页面的 xterm.js 单独分 chunk。
- **实际**: 所有代码打包在一个文件中。
- **证据**: `web/dist/assets/index-BICGlhHN.js` 大小 1,454,133 bytes。
- **修复方向**: 对 Terminal 页面使用 `React.lazy(() => import('./pages/Terminal'))`，对 Ant Design 使用 `manualChunks` 配置。

#### 问题 #7: 前端无任何测试
- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `web/` 目录
- **问题**: 整个前端项目没有任何单元测试或集成测试文件。后端有 118 个测试，但前端零测试。
- **预期**: 至少对关键组件（StatusBadge、CreateSandboxModal 的表单验证、API 层的请求格式）有基础测试。
- **实际**: 没有 test 目录，没有 jest/vitest 配置，没有任何 `.test.tsx` 文件。
- **证据**: `ls web/src/` 和 `glob **/*.test.*` 无结果。
- **修复方向**: MVP 阶段可以接受，但建议至少添加对 API 层函数的 mock 测试和 StatusBadge 的渲染测试。

### 测试覆盖评估

**已覆盖:**
- Dashboard 页面：统计卡片、快速启动、最近沙盒列表
- Sandboxes 页面：列表、创建弹窗、暂停/恢复、快照弹窗、删除（有确认）
- Templates 页面：列表、状态显示、构建触发、构建日志弹窗
- Terminal 页面：组件渲染、WebSocket 连接建立、信息顶栏
- 路由导航：三个主路由的菜单高亮和页面切换
- API 层：与后端数据一致性验证
- 代码质量：TypeScript 编译、ESLint、后端 pytest、ruff lint

**缺失:**
- Terminal 页面的实际命令执行和交互
- 创建沙盒弹窗的"自定义镜像"模式测试
- 批量删除功能（全部删除按钮）
- 浏览器窗口 resize 时的响应式布局
- 网络断连恢复场景（后端不可达时的 UI 表现）
- 前端单元测试和集成测试

### 总结

- 共 7 个问题（严重 2, 中等 1, 轻微 4）
- 最关键的问题是: **#1 停止按钮执行删除** 和 **#2 终端无法交互**
- 建议优先修复: 问题 #1（改变一行代码即可解决）和 问题 #3（添加 404 路由），这两个修复成本极低
- 问题 #2（终端无 PTY）是架构层面的限制，修复成本较高但对功能完整性影响最大

**整体评价:** Dashboard、Templates、Sandboxes（除停止按钮外）三个页面的功能实现质量较高，赛博朋克暗色主题的视觉效果出色，代码组织清晰。但两个严重问题（停止即删除、终端不可用）使得功能完整性未达到 7 分阈值。建议修复问题 #1 和 #3 后重新提交 QA，终端 PTY 问题可以作为已知限制在 UI 上给出明确提示。

---

## QA 回归验证报告 -- M4 修复后

回归日期: 2026-04-10
验证环境: 后端 http://localhost:9000, 前端 http://localhost:5174 (Vite dev server)

### 修复验证结果

| 问题 | 严重程度 | 状态 | 验证结果 |
|------|----------|------|----------|
| #1 停止按钮执行删除操作 | 严重 | PASS 已修复 | 操作列只有终端/暂停/快照/删除四个按钮，停止按钮已完全移除 |
| #2 终端无法交互（无 PTY） | 严重 | PASS 已修复 | WebSocket 连接成功，shell 提示符 `root@container:/#` 正常显示，`echo hello-qa-test` 命令执行后输入回显和输出均正确，新提示符正常出现 |
| #3 缺少 404 路由处理 | 中等 | PASS 已修复 | 访问 `/nonexistent-page` 自动重定向到 `/` (Dashboard)，页面正常显示侧边栏和内容 |
| #4 Ant Design 废弃 API | 轻微 | PARTIAL 部分修复 | `bordered` 和 `valueStyle` 已替换为新 API（代码中已无引用）；但 `destroyOnClose` 废弃 API 仍存在于 CreateSandboxModal.tsx:67 和 SnapshotModal.tsx:50，控制台仍有 deprecation 警告 |
| #5 操作按钮缺少文字标签 | 轻微 | PASS 已修复 | 沙盒列表操作按钮均有中文文字标签："终端"、"暂停"/"恢复"、"快照"、"删除" |
| #6 构建产物未做代码分割 | 轻微 | -- 未修复（未纳入本次修复范围） | -- |
| #7 前端无任何测试 | 轻微 | -- 未修复（未纳入本次修复范围） | -- |

### 回归测试结果

| 测试场景 | 结果 | 说明 |
|----------|------|------|
| Dashboard 页面加载 | PASS | 统计卡片正确（连接状态=已连接, 活跃沙盒数正确, 已构建模板=3/4, 系统版本=0.1.0），快速启动区 4 个模板卡片，最近沙盒列表正常 |
| Dashboard 快速启动创建沙盒 | PASS | 点击 claude-code 卡片"启动"按钮成功创建沙盒，自动跳转到沙盒管理页 |
| Templates 页面列表 | PASS | 4 个模板完整展示，状态/来源/连接类型/镜像大小正确，openclaw 为"失败"状态带"构建"按钮 |
| 沙盒暂停操作 | PASS | 状态变为"已暂停"，按钮变为"恢复"，终端/快照按钮变为 disabled |
| 沙盒恢复操作 | PASS | 状态恢复为"运行中"，按钮恢复为"暂停" |
| 沙盒删除确认 | PASS | 点击删除弹出 Popconfirm 确认弹窗"确认删除？此操作将永久删除该沙盒" |
| 侧边栏导航 | PASS | 三个菜单项正确高亮，路由切换正常 |
| 后端测试套件 | PASS | 118 passed |
| TypeScript 编译 | PASS | 零错误 |
| ESLint | PASS | 零错误 |

### 新发现的问题

#### 问题 NEW-1: Modal 组件使用废弃的 destroyOnClose 属性
- **严重程度**: 轻微
- **维度**: 代码质量
- **位置**: `web/src/components/CreateSandboxModal.tsx:67`, `web/src/components/SnapshotModal.tsx:50`
- **问题**: 两个 Modal 组件使用了 Ant Design 已废弃的 `destroyOnClose` 属性，控制台输出 `[antd: Modal] destroyOnClose is deprecated. Please use destroyOnHidden instead.`
- **修复方向**: 将 `destroyOnClose` 替换为 `destroyOnHidden`

### 重新评分

| 维度 | 原始分数 | 修复后分数 | 阈值 | 状态 |
|------|----------|-----------|------|------|
| 功能完整性 | 6/10 | 8/10 | 7 | PASS |
| 可靠性 | 6/10 | 7/10 | 6 | PASS |
| 用户体验 | 7/10 | 8/10 | 6 | PASS |
| 代码质量 | 7/10 | 7/10 | 5 | PASS |

**里程碑结果: PASS**

### 重新评分理由

**功能完整性 6->8**: 停止按钮已移除消除了破坏性语义错误。终端页面现在完全可交互 -- WebSocket 连接成功、PTY 分配正常、shell 提示符显示、命令输入回显和输出均正常工作。404 路由重定向到首页。三个核心功能（沙盒管理、终端、模板）全部可用。构建产物未做代码分割和缺少前端测试属于优化项，不影响功能完整性评分。

**可靠性 6->7**: 移除停止按钮消除了"无确认删除"的数据安全风险。删除操作有 Popconfirm 确认。暂停/恢复状态切换正确，按钮 disabled 状态控制合理（已暂停时终端和快照不可用）。API 错误处理和轮询行为稳定。

**用户体验 7->8**: 操作按钮添加中文文字标签后可用性显著提升（终端/暂停/恢复/快照/删除一目了然）。404 路由重定向避免了用户看到空白页的困惑。终端页面从完全不可用变为流畅的交互式 shell 体验。

**代码质量 7->7（维持）**: 原有优点保持（TypeScript 零错误、ESLint 零错误、118 后端测试全通过、代码组织清晰）。`destroyOnClose` 废弃 API 是新发现的轻微问题，但 `bordered` 和 `valueStyle` 已修复。构建产物未分割和前端无测试仍然存在。整体代码质量没有显著变化。

### 总结

5 个需修复的问题中：
- 3 个完全修复（#1 停止按钮, #2 终端 PTY, #3 404 路由）
- 1 个完全修复 + 遗漏同类问题（#4 Ant Design API: bordered/valueStyle 已修复，destroyOnClose 遗漏）
- 1 个完全修复（#5 操作按钮文字标签）
- 2 个未纳入修复范围（#6 代码分割, #7 前端测试）

修复质量评价: 三个核心问题（#1 严重, #2 严重, #3 中等）全部彻底修复，修复效果经浏览器实际操作验证确认。遗留的 `destroyOnClose` 废弃 API 是轻微问题，不影响功能。

**M4 里程碑现在通过 QA 评审。**
