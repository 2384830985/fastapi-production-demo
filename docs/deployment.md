# 部署文档
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


## 部署方式

本项目支持三种部署方式，按推荐程度排序：

1. **Docker Compose**（推荐）— 一键启动 app + mysql
2. **Docker 单容器** — app 容器 + 外部 MySQL
3. **直接运行** — 本地开发或测试

---

## 方式 1：Docker Compose（推荐）

### 前置条件
- Docker 20+
- Docker Compose v2+

### 步骤

```bash
# 1. 准备环境变量
cp .env.example .env
# 编辑 .env，至少修改 DB_PASSWORD

# 2. 构建并启动
docker compose up -d --build

# 3. 查看日志
docker compose logs -f app

# 4. 执行数据库迁移
docker compose exec app alembic upgrade head

# 5. 健康检查
curl http://localhost:8000/health

# 6. 停止
docker compose down

# 7. 停止并删除数据卷（慎用，会丢数据）
docker compose down -v
```

### 服务组成

| 服务 | 端口 | 说明 |
|------|------|------|
| app | 8000 | FastAPI 应用 |
| mysql | 3306 | MySQL 数据库 |

### 数据持久化

- MySQL 数据：`mysql_data` 卷
- 容器重启数据不丢失

---

## 方式 2：Docker 单容器

适用于已有外部 MySQL 的情况。

```bash
# 1. 构建镜像
docker build -t fastapi-user-demo:latest .

# 2. 运行（连接外部 MySQL）
docker run -d \
  --name user-api \
  -p 8000:8000 \
  -e DB_HOST=192.168.1.100 \
  -e DB_PORT=3306 \
  -e DB_USER=root \
  -e DB_PASSWORD=your_password \
  -e DB_NAME=testdb \
  -e LOG_LEVEL=INFO \
  fastapi-user-demo:latest

# 3. 查看日志
docker logs -f user-api

# 4. 进入容器执行迁移
docker exec -it user-api alembic upgrade head

# 5. 停止
docker stop user-api && docker rm user-api
```

---

## 方式 3：直接运行

适用于本地开发。

```bash
# 1. 创建虚拟环境
python3 -m venv env
source env/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env

# 4. 启动
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 生产部署建议

### 1. Gunicorn + Uvicorn worker

开发用 `uvicorn`，生产用 `gunicorn` 管理 多个 uvicorn worker：

```bash
gunicorn main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

Docker 部署时直接修改 CMD：
```dockerfile
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

worker 数量建议：CPU 核心数 × 2 + 1。

### 2. Nginx 反向代理

```nginx
upstream fastapi_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. HTTPS

- 用 Let's Encrypt 免费证书：`certbot --nginx -d api.example.com`
- 或 Cloudflare 免费 SSL

### 4. 数据库连接池调优

修改 `app/db.py`：
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # 连接池大小
    max_overflow=20,       # 突发时最多额外连接
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### 5. 监控

- **Prometheus metrics**：用 `prometheus-fastapi-instrumentator`
- **日志聚合**：ELK / Loki / CloudWatch
- **APM**：Sentry / DataDog

### 6. 资源限制

Docker 部署加资源限制：
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          memory: 256M
```

---

## CI/CD 流程

### GitHub Actions

仓库根目录 `.github/workflows/ci.yml`，每次 push 自动执行：

1. **lint**：代码风格检查
2. **test**：跑测试
3. **build**：构建 Docker 镜像
4. **push**：推到镜像仓库（仅 main 分支）

### 部署流程

```
开发分支 push
    ↓
GitHub Actions 跑 lint + test
    ↓
合并到 main
    ↓
构建镜像并推到 registry
    ↓
服务器拉取新镜像
    ↓
docker compose up -d
    ↓
alembic upgrade head（在容器内）
    ↓
健康检查通过 → 流量切到新版本
```

### 配置 GitHub Secrets

仓库 Settings → Secrets and variables → Actions：

| Secret 名 | 用途 |
|-----------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `DEPLOY_HOST` | 部署服务器 IP |
| `DEPLOY_USER` | 部署服务器 SSH 用户 |
| `DEPLOY_KEY` | SSH 私钥 |

---

## 回滚

### 应用回滚

```bash
# 拉取旧版本镜像
docker pull fastapi-user-demo:v1.0.0

# 修改 docker-compose.yml 的 image tag 或用变量
docker compose up -d
```

### 数据库回滚

```bash
# 在容器内执行
docker compose exec app alembic downgrade -1
```

⚠️ **注意**：数据库回滚可能丢数据，谨慎操作，先备份！

### 数据备份

```bash
# 备份
docker compose exec mysql mysqldump -u root -p testdb > backup.sql

# 恢复
docker compose exec -T mysql mysql -u root -p testdb < backup.sql
```
