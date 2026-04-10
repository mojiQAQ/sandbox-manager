# Sandbox Manager

一条命令，秒级进入预装好开发工具的隔离环境。

## 功能特性

- **即开即用** — 内置 Claude Code / VS Code / OpenClaw / Python 等模板，创建即可用
- **Web 管理面板** — React + Ant Design 赛博朋克暗色主题，可视化管理所有沙盒
- **Web Terminal** — 浏览器内直接连接沙盒终端，无需 SSH
- **运行时快照** — 保存当前沙盒状态为新模板，随时复用
- **自定义模板** — YAML 定义模板，自动构建 Docker 镜像
- **CLI 工具** — `sbx` 命令行，适合脚本集成和快速操作

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| 前端 | React 18, Ant Design 5, xterm.js, Vite |
| CLI | Typer + Rich |
| 运行时 | OpenSandbox (Docker runtime) |
| 部署 | Docker Compose, 多阶段构建 |

## 快速开始

### Docker Compose 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/mojiQAQ/sandbox-manager.git
cd sandbox-manager

# 复制环境变量
cp .env.prod.example .env

# 构建并启动
docker compose -f docker-compose.prod.yaml up -d --build
```

服务启动后访问 `http://localhost:8000`。

### CentOS 一键部署

```bash
bash deploy.sh
```

脚本会自动安装 Docker、构建镜像、启动所有服务。详见 [部署指南](docs/deploy-guide.md)。

### 本地开发

```bash
# 后端
pip install -e ".[dev]"
uvicorn sandbox_manager.main:app --reload --port 19000

# 前端
cd web
npm install
npm run dev
```

### CLI 使用

```bash
# 安装后可用 sbx 命令
pip install .

# 查看所有沙盒
sbx list

# 从模板创建沙盒
sbx start claude-code

# 停止沙盒
sbx stop <sandbox-id>
```

## 项目结构

```
├── src/sandbox_manager/     # 后端 FastAPI 应用
│   ├── api/                 # REST API + WebSocket 路由
│   ├── models/              # 数据模型 (SQLAlchemy + Pydantic)
│   ├── services/            # 业务逻辑层
│   ├── db/                  # 数据库引擎
│   ├── main.py              # 应用入口
│   ├── cli.py               # CLI 入口
│   └── config.py            # 配置管理
├── web/                     # React 前端
│   └── src/
│       ├── pages/           # 页面组件
│       ├── components/      # 通用组件
│       └── api/             # API 客户端
├── templates/               # 内置沙盒模板 (YAML)
├── tests/                   # 测试用例
├── Dockerfile               # Sandbox Manager 多阶段构建
├── Dockerfile.opensandbox   # OpenSandbox Server 镜像
├── docker-compose.prod.yaml # 生产部署配置
├── deploy.sh                # CentOS 一键部署脚本
└── docs/                    # 文档
```

## 服务架构

```
Nginx Proxy Manager (域名 + HTTPS + WSS)
        │
        ▼ :8000
  Sandbox Manager (FastAPI + Web UI)
        │ 内部网络
        ▼ :8080
  OpenSandbox Server (沙盒运行时)
        │
        ▼
  Docker Engine (沙盒容器)
```

## 内置模板

| 模板 | 说明 |
|------|------|
| `base` | 基础 Ubuntu 环境 |
| `python-dev` | Python 开发环境 |
| `vscode` | VS Code (code-server) |
| `claude-code` | Claude Code 开发环境 |
| `openclaw` | OpenClaw AI 工具 |

## 环境变量

所有配置项通过 `SBXMGR_` 前缀的环境变量设置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SBXMGR_OPENSANDBOX_HOST` | `localhost` | OpenSandbox 地址 |
| `SBXMGR_OPENSANDBOX_PORT` | `8080` | OpenSandbox 端口 |
| `SBXMGR_DATABASE_PATH` | `data/sandbox_manager.db` | 数据库路径 |
| `SBXMGR_PORT` | `8000` | 服务端口 |
| `SBXMGR_DEBUG` | `false` | 调试模式 |

## License

MIT
