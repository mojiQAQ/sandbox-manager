#!/usr/bin/env bash
# ============================================================
# Sandbox Manager 一键部署脚本
# 适用于 CentOS/RHEL 全新环境
# 用法: bash deploy.sh
# ============================================================
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }
info()  { echo -e "${CYAN}[i]${NC} $*"; }

# ============================================================
# 1. 检测操作系统
# ============================================================
info "检测操作系统..."
if [ -f /etc/redhat-release ]; then
    OS="centos"
    log "检测到 CentOS/RHEL 系统"
elif [ -f /etc/debian_version ]; then
    OS="debian"
    log "检测到 Debian/Ubuntu 系统"
else
    OS="unknown"
    warn "未识别的操作系统，将尝试通用安装方式"
fi

# ============================================================
# 2. 安装 Docker
# ============================================================
install_docker() {
    if command -v docker &>/dev/null; then
        log "Docker 已安装: $(docker --version)"
        return 0
    fi

    info "正在安装 Docker..."
    if [ "$OS" = "centos" ]; then
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    elif [ "$OS" = "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    else
        curl -fsSL https://get.docker.com | sudo sh
    fi

    sudo systemctl enable docker
    sudo systemctl start docker

    # 将当前用户加入 docker 组
    if [ "$(id -u)" -ne 0 ]; then
        sudo usermod -aG docker "$USER"
        warn "已将 $USER 加入 docker 组，若后续命令报权限错误请重新登录或运行: newgrp docker"
    fi

    log "Docker 安装完成: $(docker --version)"
}

# ============================================================
# 3. 检测 Docker Compose
# ============================================================
check_compose() {
    if docker compose version &>/dev/null; then
        log "Docker Compose (plugin) 已就绪: $(docker compose version --short)"
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        log "docker-compose 已就绪: $(docker-compose --version)"
        COMPOSE_CMD="docker-compose"
    else
        err "Docker Compose 未找到，请安装 docker-compose-plugin"
    fi
}

# ============================================================
# 4. 生成环境变量文件
# ============================================================
generate_env() {
    if [ -f .env ]; then
        warn ".env 文件已存在，跳过生成"
        return 0
    fi

    info "生成 .env 配置文件..."
    cp .env.prod.example .env
    log ".env 文件已生成，请根据需要修改配置"
}

# ============================================================
# 5. 构建并启动服务
# ============================================================
deploy() {
    info "构建 Docker 镜像（首次构建可能需要几分钟）..."
    $COMPOSE_CMD -f docker-compose.prod.yaml build

    info "启动服务..."
    $COMPOSE_CMD -f docker-compose.prod.yaml up -d

    info "等待服务就绪..."
    local retries=30
    local count=0
    while [ $count -lt $retries ]; do
        if curl -sf http://localhost:${SBXMGR_PORT:-8000}/api/v1/health > /dev/null 2>&1; then
            log "服务已就绪！"
            return 0
        fi
        count=$((count + 1))
        sleep 2
    done

    warn "服务可能尚未完全启动，请检查日志: $COMPOSE_CMD -f docker-compose.prod.yaml logs -f"
}

# ============================================================
# 主流程
# ============================================================
echo ""
echo "======================================================"
echo "       Sandbox Manager 一键部署"
echo "======================================================"
echo ""

install_docker
check_compose
generate_env
deploy

# 获取服务器 IP
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")
PORT=${SBXMGR_PORT:-8000}

echo ""
echo "======================================================"
echo -e "  ${GREEN}部署完成！${NC}"
echo "======================================================"
echo ""
echo "  访问地址:"
echo -e "    ${CYAN}http://${SERVER_IP}:${PORT}${NC}"
echo ""
echo "  管理命令:"
echo "    查看日志:  $COMPOSE_CMD -f docker-compose.prod.yaml logs -f"
echo "    停止服务:  $COMPOSE_CMD -f docker-compose.prod.yaml down"
echo "    重启服务:  $COMPOSE_CMD -f docker-compose.prod.yaml restart"
echo ""
echo "  Nginx Proxy Manager 配置:"
echo "    Forward Hostname: ${SERVER_IP}"
echo "    Forward Port: ${PORT}"
echo "    WebSocket Support: 开启"
echo ""
