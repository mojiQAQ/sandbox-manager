# Sandbox Manager 远端部署指南

## 前置条件

- CentOS 7/8/9 或 RHEL 系统
- root 或 sudo 权限
- 服务器能访问外网（拉取 Docker 镜像）
- 已安装 Nginx Proxy Manager（用于反向代理）

## 一键部署

```bash
# 1. 将项目上传到服务器
scp -r ./sandbox user@your-server:/opt/sandbox

# 2. SSH 到服务器
ssh user@your-server

# 3. 进入项目目录
cd /opt/sandbox

# 4. 运行部署脚本
bash deploy.sh
```

脚本会自动完成：
- 检测并安装 Docker + Docker Compose
- 生成 `.env` 配置文件
- 构建 Docker 镜像
- 启动所有服务
- 验证服务就绪

## 手动部署

如果你更喜欢手动操作：

```bash
# 复制环境变量
cp .env.prod.example .env

# 构建并启动
docker compose -f docker-compose.prod.yaml up -d --build

# 查看日志
docker compose -f docker-compose.prod.yaml logs -f
```

## 服务架构

```
                  ┌─────────────────────────┐
                  │   Nginx Proxy Manager   │
                  │  (域名 + HTTPS + WSS)   │
                  └───────────┬─────────────┘
                              │
                              ▼ :8000
                  ┌─────────────────────────┐
                  │    Sandbox Manager      │
                  │  (FastAPI + Web UI)     │
                  └───────────┬─────────────┘
                              │ 内部网络
                              ▼ :8080
                  ┌─────────────────────────┐
                  │   OpenSandbox Server    │
                  │   (沙盒运行时管理)       │
                  └───────────┬─────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │     Docker Engine       │
                  │   (沙盒容器运行环境)     │
                  └─────────────────────────┘
```

**安全设计**：
- OpenSandbox Server (8080) **不暴露到外网**，仅通过内部 Docker 网络通信
- 只有 Sandbox Manager (8000) 对外，由 Nginx Proxy Manager 反代

## Nginx Proxy Manager 配置

### 添加 Proxy Host

1. 登录 Nginx Proxy Manager Web 界面
2. 点击 **Proxy Hosts** → **Add Proxy Host**

### Details 选项卡

| 字段 | 值 |
|------|-----|
| Domain Names | `sandbox.yourdomain.com`（改成你的域名） |
| Scheme | `http` |
| Forward Hostname / IP | `127.0.0.1`（如果 NPM 和应用在同一台机器） |
| Forward Port | `8000` |
| Cache Assets | 可选开启 |
| Block Common Exploits | 建议开启 |
| **Websockets Support** | **必须开启** |

> **重要**：WebSocket Support 必须开启，否则 Web Terminal 无法工作！

### SSL 选项卡

| 字段 | 值 |
|------|-----|
| SSL Certificate | Request a new SSL Certificate |
| Force SSL | 开启 |
| HTTP/2 Support | 开启 |
| HSTS Enabled | 可选 |

点击 **Save** 即可。Let's Encrypt 证书会自动申请。

### Custom Nginx Configuration（可选优化）

在 **Advanced** 选项卡中添加：

```nginx
# WebSocket 超时设置（Web Terminal 长连接）
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;

# 上传文件大小限制
client_max_body_size 100m;
```

## 常用运维命令

```bash
# 查看服务状态
docker compose -f docker-compose.prod.yaml ps

# 查看实时日志
docker compose -f docker-compose.prod.yaml logs -f

# 仅看某个服务日志
docker compose -f docker-compose.prod.yaml logs -f sandbox-manager

# 重启所有服务
docker compose -f docker-compose.prod.yaml restart

# 停止所有服务
docker compose -f docker-compose.prod.yaml down

# 重新构建并启动（代码更新后）
docker compose -f docker-compose.prod.yaml up -d --build

# 清理未使用的镜像
docker image prune -f
```

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker compose -f docker-compose.prod.yaml up -d --build
```

## 故障排查

### 服务无法启动
```bash
# 检查 Docker 是否运行
systemctl status docker

# 查看容器日志
docker compose -f docker-compose.prod.yaml logs opensandbox-server
docker compose -f docker-compose.prod.yaml logs sandbox-manager
```

### WebSocket 连接失败（终端无法使用）
- 确认 Nginx Proxy Manager 中 **Websockets Support** 已开启
- 检查是否有防火墙阻止 WebSocket 连接
- 检查 Advanced 配置中 `proxy_read_timeout` 是否设置

### 沙盒创建失败
```bash
# 检查 Docker socket 权限
ls -la /var/run/docker.sock

# 检查 OpenSandbox 日志
docker compose -f docker-compose.prod.yaml logs opensandbox-server
```
