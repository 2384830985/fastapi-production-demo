# ============================================================
# 多阶段构建：builder 装依赖，runtime 只复制产物，镜像更小
# ============================================================

# ── 阶段 1：builder ────────────────────────────────────────
# 用 python:3.11-slim 而非 alpine（alpine 编译 Python 包麻烦）
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 装系统依赖（编译 bcrypt/cryptography 等 C 扩展用）
# build-essential: gcc/make
# libffi-dev: cffi 需要
# libssl-dev: cryptography 需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip

# 先只复制 requirements.txt（利用 Docker 缓存层）
# 只要 requirements.txt 不变，依赖安装层就缓存
COPY requirements.txt .

# 安装依赖到 /install 目录（便于后续复制）
# --prefix=/install 让所有包安装到 /install 而非全局
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# 阶段 2：runtime（最终镜像）
# ============================================================
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# runtime 阶段不需要编译工具，镜像更小
# 只装运行时需要的系统库（MySQL 客户端、SSL 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制已安装的 Python 依赖
COPY --from=builder /install /usr/local

# 复制项目代码
COPY . .

# 创建非 root 用户运行应用（安全最佳实践）
# - 创建 appuser 用户和组
# - 把 /app 目录所有权给 appuser
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查（每 30s 一次，3 次失败标记 unhealthy）
# 用 curl 调用 /health 接口
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令：gunicorn + uvicorn worker
# -w 4: 4 个 worker 进程
# -k uvicorn.workers.UvicornWorker: 用 uvicorn worker（支持 ASGI）
# -b 0.0.0.0:8000: 监听所有网卡的 8000 端口
# --access-logfile -: 访问日志输出到 stdout
# --error-logfile -: 错误日志输出到 stdout
# 生产用 gunicorn 比 uvicorn 更稳，支持 worker 重启、信号处理等
CMD ["gunicorn", "main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
