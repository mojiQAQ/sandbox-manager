# === 阶段 1：构建前端 ===
FROM docker.m.daocloud.io/library/node:22-alpine AS frontend-builder

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# === 阶段 2：安装后端依赖 ===
FROM docker.m.daocloud.io/library/python:3.11-slim AS backend-builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# === 阶段 3：最终镜像 ===
FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# 安装系统依赖（curl 用于 healthcheck）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 从 backend-builder 复制已安装的 Python 包
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# 复制后端代码
COPY src/ src/
COPY templates/ templates/

# 从 frontend-builder 复制构建产物到 static 目录
COPY --from=frontend-builder /web/dist/ static/

# 创建数据目录
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "sandbox_manager.main:app", "--host", "0.0.0.0", "--port", "8000"]
