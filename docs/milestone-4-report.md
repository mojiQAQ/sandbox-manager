## 里程碑 M4 交付报告

### 本轮实现的功能

**前端 Web 管理界面（19 个文件）**

- **配置层**: Vite proxy 配置（API + WebSocket）、Ant Design 6 暗色赛博朋克主题 token、全局 CSS（发光效果、脉冲动画、滚动条、字体）、TypeScript 类型定义（完整映射 schemas.py）、axios 实例（baseURL + 错误拦截）
- **API 层**: `api/sandboxes.ts`（12 个函数：CRUD + 暂停/恢复/连接信息/快照 + 健康检查/系统状态）、`api/templates.ts`（5 个函数：列表/详情/构建/构建状态/删除）
- **基础组件**: `StatusBadge`（7 种状态颜色映射 + building 脉冲动画）、`AppLayout`（Sider 侧边栏 + Header + Content，路由联动菜单高亮）、`usePolling` hook（可配置间隔的定时轮询，支持暂停）
- **Dashboard 仪表盘**: 4 个统计卡片（连接状态指示灯、活跃沙盒数、已构建模板数/总数、系统版本）+ 快速启动区域（2x2 模板卡片网格，hover 发光效果）+ 最近沙盒列表
- **Sandboxes 沙盒管理**: 工具栏（创建/批量删除/刷新）+ Ant Design Table（ID 截断+tooltip、状态徽标、操作列 5 个按钮）+ 行选择 + 5 秒自动轮询
- **Templates 模板管理**: 工具栏（全部构建/刷新）+ 表格（名称、描述、状态、来源、连接类型、镜像大小）+ 构建/删除操作
- **Terminal Web 终端**: 全屏 xterm.js（赛博朋克配色主题）+ 顶栏（沙盒 ID、模板名、状态、连接指示灯）+ WebSocket 双向通信
- **弹窗组件**: `CreateSandboxModal`（模板选择/自定义镜像双模式）、`SnapshotModal`（名称校验 + 描述）、`BuildLogModal`（轮询构建状态 + 成功/失败结果展示）、`TemplateCard`（快速启动卡片，按状态显示不同操作按钮）

**后端 WebSocket 终端端点（1 个新文件 + 1 个修改）**

- `ws_terminal.py`: WebSocket 端点，通过 `asyncio.create_subprocess_exec` 桥接 `docker exec -i` 到 xterm.js，支持 bash/sh 自动回退，双向异步流转发，优雅关闭清理
- `router.py`: 注册 ws_terminal 路由

### 新建/修改的文件

**前端（web/src/）**:
- `vite.config.ts` — Vite 开发服务器配置，API + WebSocket proxy
- `theme.ts` — Ant Design 6 暗色主题 token，赛博朋克配色
- `global.css` — 全局样式，发光效果、脉冲动画、滚动条、侧边栏 logo
- `main.tsx` — 应用入口，引入全局 CSS
- `App.tsx` — 路由配置 + ConfigProvider 暗色主题
- `api/types.ts` — 完整 TypeScript 类型定义
- `api/client.ts` — axios 实例 + 错误拦截器
- `api/sandboxes.ts` — 沙盒 + 系统 API 函数
- `api/templates.ts` — 模板 API 函数
- `components/AppLayout.tsx` — 主布局（侧边栏 + 页头 + 内容区）
- `components/StatusBadge.tsx` — 状态徽标组件
- `components/TemplateCard.tsx` — 模板快速启动卡片
- `components/CreateSandboxModal.tsx` — 创建沙盒弹窗
- `components/SnapshotModal.tsx` — 快照保存弹窗
- `components/BuildLogModal.tsx` — 构建日志弹窗
- `hooks/usePolling.ts` — 定时轮询 hook
- `pages/Dashboard.tsx` — 仪表盘页面
- `pages/Sandboxes.tsx` — 沙盒管理页面
- `pages/Templates.tsx` — 模板管理页面
- `pages/Terminal.tsx` — Web 终端页面
- `index.html` — 更新标题和语言设置

**后端（src/sandbox_manager/api/）**:
- `ws_terminal.py` — 新增 WebSocket 终端端点
- `router.py` — 注册 WebSocket 路由

**清理的脚手架文件**:
- 删除: `App.css`, `index.css`, `assets/react.svg`, `assets/vite.svg`, `assets/hero.png`, `public/icons.svg`

### 自测结果

- TypeScript 编译: 0 errors
- ESLint: 0 errors, 0 warnings
- Vite 生产构建: 成功（dist/ 输出正常）
- 后端 ruff lint（ws_terminal.py）: All checks passed
- 后端 pytest: 118/118 passed
- 后端 import 验证: router.py 加载 17 个路由正常

### 验收标准自检

- [x] Dashboard 页面：4 个统计卡片 + 快速启动区 + 最近沙盒列表
- [x] Dashboard 快速启动：模板卡片展示状态，ready 可启动，unbuilt 可构建
- [x] Sandboxes 页面：完整 CRUD 操作 + 暂停/恢复 + 行选择 + 5s 自动轮询
- [x] Sandboxes 创建弹窗：支持模板选择和自定义镜像双模式
- [x] Sandboxes 快照弹窗：名称格式校验 + 描述
- [x] Templates 页面：列表展示 + 构建/删除操作 + 全部构建
- [x] Templates 构建日志弹窗：轮询构建状态，展示成功/失败结果
- [x] Terminal 页面：xterm.js 全屏终端 + WebSocket 连接
- [x] 赛博朋克深色主题：主背景 #0a0e17，霓虹青 #06b6d4 强调色
- [x] StatusBadge：7 种状态正确颜色映射 + building 脉冲动画
- [x] 路由：/ /sandboxes /templates /terminal/:sandboxId
- [x] 后端 WebSocket 端点：桥接 docker exec，bash/sh 自动回退
- [x] 所有 UI 文字使用中文
- [x] 代码零 lint 错误，生产构建成功

### 已知问题

- 生产构建单 chunk 1454KB（gzip 445KB），超过 500KB 警告阈值。可通过 dynamic import 做代码分割优化，但 MVP 阶段影响有限
- Terminal 页面未使用 AppLayout 包裹（设计意图：全屏终端体验）
- WebSocket 终端使用 `docker exec -i`（无 `-t`），因为 asyncio subprocess 不支持 PTY 分配。终端交互体验可能不如原生 SSH，部分需要 TTY 的命令（如 `top`, `vim`）可能显示异常

### 状态: 提交 QA
