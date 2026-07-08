# 09 - Docker 容器化与 CI/CD
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 9 篇。本篇讲清楚 Docker 多阶段构建、Compose 编排、GitHub Actions 流水线、镜像优化。

## 你将学到

- Docker 基础与镜像原理
- 多阶段构建为什么镜像更小
- docker-compose 多服务编排
- 健康检查与依赖顺序
- `${VAR:?}` 强制要求环境变量（拒绝弱默认值上生产）
- `APP_ENV` 环境分层与文档暴露控制
- 为什么生产环境只走 Alembic，不用 `create_all`
- GitHub Actions CI/CD 流水线
- 镜像缓存优化
- 生产部署最佳实践

---

## 1. Docker 基础

### 1.1 Docker 是什么

Docker 是容器化平台，把应用+依赖打包成**镜像**，运行成**容器**。

```
镜像 (Image)        静态模板，类似面向对象的类
   ↓ 运行
容器 (Container)    运行实例，类似对象
```

### 1.2 容器 vs 虚拟机

| 维度 | 虚拟机 | 容器 |
|------|--------|------|
| 隔离级别 | 硬件级（独立内核） | 进程级（共享内核） |
| 启动 | 分钟级 | 秒级 |
| 资源占用 | GB 级 | MB 级 |
| 密度 | 一台几个 | 一台几十个 |

### 1.3 镜像分层

Docker 镜像是**分层**的，每条 `Dockerfile` 指令一层：

```dockerfile
FROM python:3.11-slim       # 基础层
RUN apt-get install ...     # 系统依赖层
COPY requirements.txt .     # 依赖清单层
RUN pip install ...         # Python 依赖层
COPY . .                    # 代码层
```

**分层的好处**：
- 未变的层缓存复用，构建快
- 多个镜像共享基础层，存储省

---

## 2. Dockerfile 多阶段构建

### 2.1 本项目的 Dockerfile

```dockerfile
# ── 阶段 1：builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 阶段 2：runtime ───────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY . .

RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### 2.2 为什么多阶段

**不用多阶段**：

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y build-essential gcc ...  # 编译工具进镜像
RUN pip install -r requirements.txt              # 装依赖
COPY . .
# 镜像里有 gcc、build-essential 等垃圾，500MB+
```

**多阶段**：

```dockerfile
# 阶段 1：builder 装编译工具，编译依赖
FROM python:3.11-slim AS builder
RUN apt-get install -y build-essential
RUN pip install --prefix=/install -r requirements.txt

# 阶段 2：runtime 只复制编译好的依赖
FROM python:3.11-slim
COPY --from=builder /install /usr/local  # 只复制产物
# 镜像里没有 gcc，200MB
```

**收益**：镜像从 500MB 缩到 200MB，攻击面也小（没有编译工具）。

### 2.3 关键指令详解

| 指令 | 作用 |
|------|------|
| `FROM ... AS builder` | 命名阶段 |
| `COPY --from=builder /install /usr/local` | 从 builder 阶段复制产物 |
| `RUN ... && rm -rf /var/lib/apt/lists/*` | 装完清理，减小镜像 |
| `USER appuser` | 非 root 运行 |
| `HEALTHCHECK` | 容器健康检查 |
| `CMD [...]` | 启动命令（JSON 数组形式） |

### 2.4 为什么用 `python:3.11-slim` 而非 `alpine`

| 基础镜像 | 大小 | 优势 | 劣势 |
|---------|------|------|------|
| `python:3.11` | 350MB+ | 完整 Debian | 大 |
| `python:3.11-slim` | 150MB | 精简 Debian | **推荐** |
| `python:3.11-alpine` | 50MB | 最小 | 编译 Python 包麻烦（musl libc） |

alpine 用 musl libc，很多 Python 包（如 bcrypt、cryptography）需要重新编译，反而更慢更麻烦。slim 是最佳平衡。

### 2.5 非 root 用户

```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser
```

**为什么**：容器被攻破后，攻击者拿到的是 `appuser` 权限，不能写 `/etc`、`/usr` 等系统目录，限制攻击面。

### 2.6 HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

| 参数 | 作用 |
|------|------|
| `--interval=30s` | 每 30s 检查一次 |
| `--timeout=3s` | 检查超时 3s |
| `--start-period=10s` | 启动后 10s 内失败不算 unhealthy |
| `--retries=3` | 连续 3 次失败才标记 unhealthy |

Docker / k8s 根据健康状态决定是否重启或摘流量。

---

## 3. .dockerignore

### 3.1 作用

避免把无关文件打进镜像，减小镜像大小、加速构建。

```
# .dockerignore
env/
__pycache__/
*.pyc
.git/
docs/
*.md
.env
*.log
```

### 3.2 为什么必须排除 `.env`

```dockerfile
COPY . .
```

如果不排除 `.env`，**密码会被打进镜像**！任何人 `docker history` 或 `docker export` 都能看到。

`.env` 必须在 `.dockerignore` 排除，运行时通过环境变量传入。

---

## 4. docker-compose 编排

### 4.1 本项目的 compose

```yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set}
      MYSQL_DATABASE: ${DB_NAME:-testdb}
    ports: ["3306:3306"]
    volumes: [mysql_data:/var/lib/mysql]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      retries: 5

  app:
    build: .
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      DB_HOST: mysql
      DB_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set}
      SECRET_KEY: ${SECRET_KEY:?SECRET_KEY must be set}
    ports: ["8000:8000"]
    command: sh -c "alembic upgrade head && gunicorn main:app -w 4 ..."

volumes:
  mysql_data:
```

### 4.2 关键设计

#### `depends_on: condition: service_healthy`

```yaml
app:
  depends_on:
    mysql:
      condition: service_healthy
```

等 MySQL 真正健康（healthcheck 通过）再启动 app，避免 app 启动时 MySQL 还没就绪。

#### `DB_HOST: mysql`

```yaml
environment:
  DB_HOST: mysql  # 用 service name
```

Docker Compose 内置 DNS，`mysql` 解析为 MySQL 容器 IP。不用写死 IP。

#### `${VAR:?must be set}`：强制要求环境变量

```yaml
MYSQL_ROOT_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set in .env}
DB_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set in .env}
SECRET_KEY: ${SECRET_KEY:?SECRET_KEY must be set in .env}
```

`:?` 语法：环境变量未设置时 **compose 直接报错退出**，不允许弱默认值（如 `123456`）混上生产。

本项目所有敏感配置都用 `:?`：
- `DB_PASSWORD`：数据库密码
- `SECRET_KEY`：JWT 签名密钥

非敏感配置用 `:-` 给默认值：
- `DB_NAME:-testdb`：数据库名
- `APP_ENV:-development`：应用环境
- `ACCESS_TOKEN_EXPIRE_MINUTES:-60`：token 过期时间

#### `APP_ENV` 环境分层与文档暴露

```yaml
environment:
  APP_ENV: ${APP_ENV:-development}
```

应用读取 `APP_ENV` 决定行为：

```python
# main.py
APP_ENV = os.getenv("APP_ENV", "development").lower()
DOCS_ENABLED = APP_ENV not in ("production", "prod")

app = FastAPI(
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)
```

生产环境（`APP_ENV=production`）下 `/docs`、`/redoc`、`/openapi.json` 全部不注册，避免接口结构泄露给攻击者。开发环境正常暴露方便调试。

#### `volumes: mysql_data`

```yaml
volumes:
  mysql_data:
```

命名卷，数据持久化。容器重启数据不丢，`docker compose down -v` 才删除。

### 4.3 启动顺序

```
docker compose up
   ↓
启动 mysql 容器
   ↓
mysql healthcheck 失败（还在初始化）
   ↓
app 等待（depends_on: condition: service_healthy）
   ↓
mysql healthcheck 通过
   ↓
app 启动
   ↓
执行 alembic upgrade head
   ↓
启动 gunicorn
```

### 4.4 常用命令

```bash
docker compose up -d --build     # 构建并后台启动
docker compose logs -f app       # 看 app 日志
docker compose ps                # 查看容器状态
docker compose exec app bash     # 进 app 容器
docker compose restart app       # 重启 app
docker compose down              # 停止删除容器
docker compose down -v           # 停止删除容器+数据卷（慎用）
```

---

## 5. 镜像缓存优化

### 5.1 Docker 缓存规则

每条 Dockerfile 指令产生一层，**未变的层缓存复用**。一旦某层变化，后续所有层重新构建。

### 5.2 利用缓存

```dockerfile
# ❌ 错误：代码改动导致依赖重装
COPY . .
RUN pip install -r requirements.txt
# 代码一改，COPY 层变，pip install 层也变，每次都重装依赖

# ✅ 正确：先复制 requirements，再复制代码
COPY requirements.txt .
RUN pip install -r requirements.txt  # 依赖不变就缓存
COPY . .  # 代码改动只影响这层
```

### 5.3 本项目的优化

```dockerfile
# 先复制 requirements（变化少）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 后复制代码（变化多）
COPY . .
```

依赖装一次后缓存，改代码不用重装依赖，构建快几十倍。

### 5.4 GitHub Actions 缓存

```yaml
# .github/workflows/ci.yml
- uses: docker/build-push-action@v6
  with:
    cache-from: type=gha       # 从 GitHub Actions 缓存读
    cache-to: type=gha,mode=max  # 写缓存（所有层）
```

`type=gha` 用 GitHub Actions 缓存，跨 CI run 复用镜像层。

---

## 6. GitHub Actions CI/CD

### 6.1 本项目的流水线

```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:        # 1. 代码检查
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install flake8
      - run: flake8 app/ tests/ main.py

  test:        # 2. 测试
    runs-on: ubuntu-latest
    needs: lint
    services:
      mysql:
        image: mysql:8.4
        env:
          MYSQL_ROOT_PASSWORD: 123456
          MYSQL_DATABASE: testdb
        ports: ["3306:3306"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: alembic upgrade head
      - run: python tests/test_api.py

  build-and-push:  # 3. 构建推送镜像
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/fastapi-user-demo:latest

  deploy:      # 4. 部署
    runs-on: ubuntu-latest
    needs: build-and-push
    steps:
      - run: ssh $DEPLOY_USER@$DEPLOY_HOST "cd /opt/app && docker compose up -d"
```

### 6.2 关键概念

#### Job 串联

```yaml
jobs:
  lint:
    ...
  test:
    needs: lint  # 等 lint 通过
  build-and-push:
    needs: test  # 等测试通过
  deploy:
    needs: build-and-push
```

`needs` 定义依赖关系，前一个失败后续不跑。

#### 并发取消

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

同分支新 push 取消旧 run，省 CI 资源。

#### 条件执行

```yaml
if: github.ref == 'refs/heads/main' && github.event_name == 'push'
```

只在 main 分支 push 时才推镜像/部署，PR 只跑 lint/test。

### 6.3 services：CI 里的数据库

```yaml
services:
  mysql:
    image: mysql:8.4
    env:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: testdb
    ports: ["3306:3306"]
    options: >-
      --health-cmd="mysqladmin ping -h localhost"
      --health-interval=10s
      --health-retries=5
```

GitHub Actions 在 CI 机器上启动 MySQL 容器，测试代码连 `127.0.0.1:3306`。

### 6.4 镜像 tag 策略

```yaml
- uses: docker/metadata-action@v5
  with:
    images: ${{ secrets.DOCKER_USERNAME }}/fastapi-user-demo
    tags: |
      type=raw,value=latest       # latest
      type=sha,format=short       # sha-abc1234
      type=ref,event=branch       # main
```

打 3 个 tag：
- `latest`：最新版
- `sha-abc1234`：commit hash，便于回滚
- `main`：分支名

---

## 7. 部署策略

### 7.1 滚动部署

```bash
# 服务器上
git pull
docker compose pull
docker compose up -d --remove-orphans  # 滚动重启
```

新容器启动，旧容器停止，期间短暂中断。

### 7.2 蓝绿部署

```
blue（旧版）→ 流量 → 用户
green（新版）→ 预热
   ↓ 切流量
blue（旧版）→ 待命
green（新版）→ 流量 → 用户
```

零停机，但需要双倍资源。

### 7.3 金丝雀部署

```
1 个实例跑新版（5% 流量）→ 观察 → 没问题 → 10% → 50% → 100%
```

风险最小，但需要负载均衡器支持权重。

### 7.4 本项目的部署

```yaml
# .github/workflows/ci.yml
deploy:
  steps:
    - run: |
        ssh $DEPLOY_USER@$DEPLOY_HOST << 'EOF'
          cd /opt/fastapi-user-demo
          git pull
          docker compose pull
          docker compose up -d --remove-orphans
          docker compose exec -T app alembic upgrade head
          docker image prune -f
        EOF
```

简单的滚动部署：拉新镜像 → 重启 → 迁移 → 清理旧镜像。

---

## 8. 数据库迁移在容器里

### 8.1 启动时迁移

```yaml
# docker-compose.yml
app:
  command: >
    sh -c "
      alembic upgrade head &&
      gunicorn main:app -w 4 ...
    "
```

启动前自动跑 `alembic upgrade head`。

**关键**：生产环境 schema 迁移**只走 Alembic**，不要在 `main.py` 里调 `Base.metadata.create_all`。

```python
# ❌ 生产环境不要这样做
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # 与 alembic 并存会 schema 漂移
    yield

# ✅ 生产环境 lifespan 只负责日志和资源清理
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动完成，环境=%s", APP_ENV)
    yield
    engine.dispose()
```

为什么：
1. `create_all` 只看模型定义，不会感知 alembic 历史里的字段重命名、列删除等变更
2. `create_all` 不会创建索引、约束的变更脚本
3. 两套机制并存会导致生产 schema 与代码模型逐渐不一致，难以排查

本项目 lifespan 不再调 `create_all`，全部依赖 `alembic upgrade head`（在 docker-compose 启动命令里执行）。

### 8.2 多实例迁移冲突

**问题**：多实例同时启动，同时跑迁移会冲突。

**解决**：只让一个实例跑迁移：

```yaml
# 用 leader election 或单独的 migration job
migration:
  command: alembic upgrade head
  restart: "no"  # 跑完就退出

app:
  depends_on:
    migration:
      condition: service_completed_successfully
```

### 8.3 k8s 里的迁移

```yaml
# 用 init container 跑迁移
spec:
  initContainers:
    - name: migrate
      image: app:latest
      command: ["alembic", "upgrade", "head"]
  containers:
    - name: app
      image: app:latest
```

---

## 9. 生产部署清单

### 9.1 安全

- [ ] 非 root 用户运行
- [ ] `.env` 不进镜像（`.dockerignore`）
- [ ] 密码用环境变量传入（`DB_PASSWORD:?must be set`）
- [ ] HTTPS（Nginx 反代 + Let's Encrypt）
- [ ] 镜像扫描（Trivy / Snyk）

### 9.2 可靠性

- [ ] 健康检查（HEALTHCHECK）
- [ ] 依赖顺序（depends_on: condition: service_healthy）
- [ ] 数据持久化（volumes）
- [ ] 自动重启（restart: unless-stopped）
- [ ] 数据库备份

### 9.3 可观测性

- [ ] 日志到 stdout
- [ ] 监控（Prometheus + Grafana）
- [ ] 告警（AlertManager）
- [ ] APM（Sentry / DataDog）

### 9.4 CI/CD

- [ ] 自动 lint
- [ ] 自动测试
- [ ] 自动构建镜像
- [ ] 自动部署
- [ ] 回滚机制

---

## 10. 自测题

### Q1：为什么用多阶段构建？

<details>
<summary>查看答案</summary>

1. 镜像更小：runtime 阶段不带编译工具
2. 攻击面小：没有 gcc 等工具
3. 构建快：缓存复用
</details>

### Q2：为什么 `.env` 必须在 `.dockerignore`？

<details>
<summary>查看答案</summary>

`COPY . .` 会把 `.env` 打进镜像，密码泄露。任何人 `docker history` 或 `docker export` 都能看到。密码必须运行时通过环境变量传入。
</details>

### Q3：`depends_on: condition: service_healthy` 解决什么问题？

<details>
<summary>查看答案</summary>

等 MySQL 真正健康（healthcheck 通过）再启动 app。如果只用 `depends_on: mysql`，MySQL 容器启动但还没就绪，app 连不上数据库。
</details>

### Q4：CI 里为什么要 `cache-from: type=gha`？

<details>
<summary>查看答案</summary>

跨 CI run 复用镜像层，加速构建。没缓存时每次从零构建，几分钟；有缓存时几十秒。
</details>

---

## 11. 小结

| 概念 | 关键点 |
|------|--------|
| 多阶段构建 | builder 编译，runtime 只复制产物，镜像小 |
| `python:slim` | 比 alpine 兼容性好，比完整版小 |
| 非 root 用户 | 安全最佳实践 |
| HEALTHCHECK | 容器健康检查 |
| `.dockerignore` | 排除 `.env`、`__pycache__` 等 |
| `depends_on: condition` | 等依赖健康再启动 |
| `${VAR:?msg}` | 强制要求环境变量 |
| GitHub Actions services | CI 里启动数据库容器 |
| 镜像缓存 | 先 COPY requirements，再 COPY 代码 |

## 12. 下篇预告

下一篇讲 **Claude Code Hook 与 AST 静态分析**：`ast` 模块、NodeVisitor、自定义校验、Hook 配置。

---

**延伸阅读**：
- [Docker 官方文档](https://docs.docker.com/)
- [Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)
- [docker-compose 参考](https://docs.docker.com/compose/compose-file/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
