# ============================================
# Kubedoctor - Multi-stage Dockerfile
# ============================================

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# 系统依赖（编译 asyncpg / sentence-transformers 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 先拷贝依赖文件，利用 Docker 缓存层
COPY requirements.txt .

# 安装到独立 prefix，便于第二阶段拷贝
RUN pip install --user --no-cache-dir -r requirements.txt

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

WORKDIR /app

# 运行时系统依赖（libpq for asyncpg, libgomp for numpy）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 拷贝已安装的 Python 包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 拷贝应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]