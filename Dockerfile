# syntax=docker/dockerfile:1.6

# ============================================================
# Stage 1: 前端构建阶段，基于 node:20-alpine
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: 后端运行时，基于 python:3.9-slim
# ============================================================
FROM python:3.9-slim AS backend
WORKDIR /app

# 安装基础系统依赖（curl 用于探活，build-essential 用于可能需要编译的依赖）
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# 通过 pip 安装 uv，统一管理 Python 依赖
RUN pip install --no-cache-dir uv

# 拷贝依赖描述文件并安装生产依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷贝后端源码
COPY app/ ./app/

# 从前端构建阶段拷贝产物到 /app/static，便于后续按需挂载静态资源
COPY --from=frontend-builder /build/frontend/dist ./static

# 暴露 FastAPI 服务端口
EXPOSE 8000

# 默认启动命令
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
