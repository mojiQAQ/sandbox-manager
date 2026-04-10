# Sandbox Manager 远端部署方案

> 用于新对话上下文，包含完整的项目状态和部署需求。

## 项目位置

`/Users/moji/ground/sandbox/`

## 当前项目状态

已完成 M1-M4 全部里程碑，QA 全部通过：
- **后端**: Python FastAPI，19 个模块，118 个测试通过
- **CLI**: `sbx` 命令，Typer 实现
- **Web UI**: React 18 + Ant Design 5 + xterm.js，赛博朋克暗色主题
- **底层**: OpenSandbox (Docker runtime)，通过 Docker socket 管理沙盒容器

## 部署目标

- **服务器**: CentOS/RHEL
- **部署方式**: Docker Compose（自包含镜像，非运行时 pip install）
- **反向代理**: Nginx Proxy Manager（用户已有）
- **访问方式**: 域名 + HTTPS

## 需要做的事情

### 1. 优化 Docker 镜像

当前 `docker-compose.yaml` 中 OpenSandbox server 用 `python:3.11-slim` + 启动时 pip install，太慢。需要：
- 构建自包含的 OpenSandbox server 镜像
- 构建自包含的 Sandbox Manager 镜像（含前端构建产物）
- 多阶段构建减小镜像体积

### 2. 一键部署脚本 (`deploy.sh`)

在全新 CentOS 环境上运行，自动完成：
- 检测并安装 Docker + Docker Compose（如果没有）
- 拉取/构建镜像
- 生成配置文件
- 启动所有服务
- 输出访问地址

### 3. Nginx Proxy Manager 配置说明

用户使用 Nginx Proxy Manager（Web UI 管理反代），需要：
- 配置域名指向 Sandbox Manager
- WebSocket 支持（Web Terminal 需要）
- SSL 证书（Let's Encrypt）

### 4. 生产配置

- OpenSandbox server 端口不暴露到外网（只走内部网络）
- Sandbox Manager API + Web UI 一个端口对外
- 环境变量配置（API key 等）

## 关键文件

| 文件 | 说明 |
|------|------|
| `docker-compose.yaml` | 当前版本，需要优化 |
| `Dockerfile` | Sandbox Manager 的 Dockerfile |
| `sandbox.toml` | OpenSandbox server 配置 |
| `web/` | React 前端项目 |
| `src/sandbox_manager/` | 后端代码 |
| `templates/` | 4 个内置模板 YAML |

## 当前 docker-compose.yaml

```yaml
services:
  opensandbox-server:
    image: python:3.11-slim
    container_name: opensandbox-server
    command: >
      bash -c "
        pip install opensandbox-server &&
        opensandbox-server init-config /etc/opensandbox/sandbox.toml --runtime docker 2>/dev/null;
        opensandbox-server --config /etc/opensandbox/sandbox.toml
      "
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./sandbox.toml:/etc/opensandbox/sandbox.toml:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  sandbox-manager:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sandbox-manager
    ports:
      - "8000:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - sandbox-data:/app/data
      - ./templates:/app/templates:ro
    environment:
      - SBXMGR_OPENSANDBOX_HOST=opensandbox-server
      - SBXMGR_OPENSANDBOX_PORT=8080
      - SBXMGR_DATABASE_PATH=/app/data/sandbox_manager.db
    depends_on:
      opensandbox-server:
        condition: service_healthy
    restart: unless-stopped

volumes:
  sandbox-data:
    driver: local
```

## 当前 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
COPY src/ src/
COPY templates/ templates/
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "sandbox_manager.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Nginx Proxy Manager 需要的配置

### Sandbox Manager Web + API
- 域名: `sandbox.yourdomain.com`（用户自定）
- Forward to: `http://<docker-host-ip>:8000`
- WebSocket 支持: **必须开启**（Web Terminal 依赖 WebSocket）
- SSL: Let's Encrypt

### 注意
- OpenSandbox server (8080) **不需要**暴露到外网
- OpenSandbox 创建的沙盒容器端口（如 vscode 的 code-server）是动态分配的，通过 OpenSandbox 的 proxy 模式访问，经由 Sandbox Manager 的 API 转发

## 目标产物

1. `Dockerfile.opensandbox` — OpenSandbox server 自包含镜像
2. `Dockerfile` — Sandbox Manager 自包含镜像（含前端构建产物）
3. `docker-compose.prod.yaml` — 生产 compose 配置
4. `deploy.sh` — CentOS 一键部署脚本
5. `.env.prod.example` — 生产环境变量模板
6. `docs/deploy-guide.md` — 部署指南（含 Nginx Proxy Manager 配置截图说明）
