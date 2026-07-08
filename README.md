# FastAPI 用户管理示例（生产级）
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


按 **四层架构 + 完整基础设施** 组织的 FastAPI 项目，可作为生产项目脚手架。

## 🎯 项目特性

- ✅ **四层架构**：API / Schema / Service / Repository 职责分离
- ✅ **MySQL 持久化**：SQLAlchemy 2.0 ORM，连接池管理
- ✅ **bcrypt 密码哈希**：直接用官方 bcrypt，无 passlib 兼容性警告
- ✅ **Pydantic v2 校验**：请求/响应模型，类型即文档
- ✅ **环境变量配置**：`.env` 文件，敏感信息不进代码
- ✅ **Alembic 迁移**：schema 变更版本管理
- ✅ **结构化日志**：统一格式，级别可调，stdout 输出便于容器收集
- ✅ **全局异常处理**：业务异常自动映射 HTTP 状态码
- ✅ **分页查询**：通用 `Page[T]` 响应模型
- ✅ **健康检查**：`/` 简单探活，`/health` 含数据库连通性
- ✅ **事务边界清晰**：Repository 不 commit，Service 控制 commit/rollback
- ✅ **lifespan 生命周期**：替代弃用的 `on_event`，支持启动/关闭钩子
- ✅ **Docker 容器化**：多阶段构建 + docker-compose 一键部署
- ✅ **CI/CD 流水线**：GitHub Actions 自动 lint/test/build/deploy
- ✅ **Claude Code Hook**：编辑代码后 AST 自动校验 + 跑测试
- ✅ **完整文档**：CLAUDE.md + docs/ + DETAIL.md

## 📐 架构分层

```
HTTP 请求
    │
    ▼
┌─────────────────────────────────────────┐
│ API 层 (app/api/)        — 路由         │  ← 处理 HTTP
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Schema 层 (app/schema/)  — Pydantic 校验│  ← 请求/响应模型
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Service 层 (app/service/)— 业务规则     │  ← 业务逻辑 + 事务控制
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Repository 层 (app/repository/)— ORM    │  ← 数据访问（不 commit）
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ MySQL (testdb.users)                    │
└─────────────────────────────────────────┘
```

辅助模块：
- `app/db.py` — 数据库引擎、Session、Base
- `app/models/` — ORM 模型
- `app/logger.py` — 日志配置
- `app/exception_handlers.py` — 全局异常处理器
- `alembic/` — 数据库迁移

## 📂 项目结构

```
fastapi-user-demo/
├── .github/workflows/ci.yml  # CI/CD 流水线
├── .claude/settings.json     # Claude Code Hook 配置
├── .env / .env.example       # 环境变量
├── .dockerignore
├── .gitignore
├── CLAUDE.md                 # Claude 协作规范
├── Dockerfile                # 多阶段构建
├── docker-compose.yml        # app + mysql 一键部署
├── README.md / DETAIL.md     # 项目文档
├── alembic.ini + alembic/    # 数据库迁移
├── docs/                     # 详细文档
│   ├── architecture.md       # 架构设计
│   ├── api.md                # API 文档
│   ├── deployment.md         # 部署指南
│   ├── database.md           # 数据库设计
│   ├── security.md           # 安全设计
│   └── troubleshooting.md    # 故障排查
├── docker/mysql-init/        # MySQL 初始化脚本
├── scripts/                  # Claude Hook 脚本
│   ├── check.py              # AST 校验
│   └── check.sh              # 入口
├── main.py                   # 应用入口
├── app/
│   ├── api/                  # 路由层
│   ├── schema/               # 校验层
│   ├── service/              # 业务层
│   ├── repository/           # 数据库层
│   ├── models/               # ORM 模型
│   ├── db.py                 # 数据库引擎
│   ├── logger.py             # 日志配置
│   └── exception_handlers.py # 全局异常处理
└── tests/test_api.py
```

## 🚀 快速开始

### 1. 准备 MySQL

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS testdb DEFAULT CHARACTER SET utf8mb4;"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填写真实密码
```

### 3. 安装依赖

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 4. 启动服务

```bash
python -m uvicorn main:app --reload
```

### 5. 访问

```
http://127.0.0.1:8000/         # 简单探活
http://127.0.0.1:8000/health   # 完整健康检查
http://127.0.0.1:8000/docs     # Swagger 文档
http://127.0.0.1:8000/redoc    # ReDoc 文档
```

## 🔌 接口列表

| 方法   | 路径             | 说明                     |
|--------|------------------|--------------------------|
| GET    | /                | 简单健康检查             |
| GET    | /health          | 完整健康检查（含 DB）    |
| GET    | /users           | 分页获取用户列表         |
| GET    | /users/{id}      | 获取单个用户             |
| POST   | /users           | 创建用户                 |
| PUT    | /users/{id}      | 更新用户                 |
| DELETE | /users/{id}      | 删除用户                 |

### 分页参数

```
GET /users?skip=0&limit=20
```

响应：
```json
{
  "items": [{"id": 1, "username": "alice"}],
  "total": 100,
  "skip": 0,
  "limit": 20,
  "has_more": true
}
```

## 📊 数据库迁移（Alembic）

### 加新字段流程

```bash
# 1. 修改 app/models/user.py 加字段
# 2. 生成迁移脚本
alembic revision --autogenerate -m "add email column"

# 3. 检查 alembic/versions/xxx_add_email_column.py，确认 upgrade/downgrade

# 4. 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 常用命令

```bash
alembic current        # 查看当前版本
alembic history        # 查看迁移历史
alembic upgrade head   # 升级到最新
alembic downgrade -1   # 回滚一个版本
```

## 🔐 密码安全

- 使用 `bcrypt` 官方包（非 passlib），无兼容性警告
- `gensalt(rounds=12)` 推荐工作因子（约 250ms/次）
- 数据库列 `hashed_password` 仅存哈希值（`$2b$12$...` 格式）
- 响应模型 `UserOut` 不返回密码字段
- `verify_password` 用常量时间比对，防时序攻击

## 📝 日志

日志级别由环境变量 `LOG_LEVEL` 控制（默认 INFO）。

```bash
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload
```

格式：
```
2026-07-07 17:21:35 | INFO    | app.service.user_service:161 | 用户创建成功 id=2 username=alice
```

日志输出到 stdout，便于容器收集（docker logs / kubectl logs）。

## 🛡️ 全局异常处理

| 业务异常 | HTTP 状态码 |
|----------|------------|
| `UserNotFoundError` | 404 |
| `UserAlreadyExistsError` | 409 |
| `IntegrityError` (DB 兜底) | 409 |
| 未捕获异常 | 500 |

路由函数无需 try/except，业务异常直接抛出由全局处理器处理。

## 🧪 测试

```bash
python tests/test_api.py
```

测试覆盖：增删改查 + 用户名冲突 + 校验失败 + 分页 + 健康检查。

## 📦 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.128+ | Web 框架 |
| Pydantic | 2.9+ | 数据校验 |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.13+ | 数据库迁移 |
| PyMySQL | 1.1+ | MySQL 驱动 |
| bcrypt | 4.0+ | 密码哈希 |
| python-dotenv | 1.0+ | 环境变量加载 |
| uvicorn | 0.32+ | ASGI 服务器（开发） |
| gunicorn | 23.0+ | WSGI 服务器（生产，管理 uvicorn worker） |

## 🐳 Docker 部署

### 一键启动（app + mysql）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 修改 DB_PASSWORD

# 2. 构建并启动
docker compose up -d --build

# 3. 查看日志
docker compose logs -f app

# 4. 健康检查
curl http://localhost:8000/health

# 5. 停止
docker compose down

# 6. 停止并删数据卷（慎用，会丢数据）
docker compose down -v
```

启动时自动执行 `alembic upgrade head` 数据库迁移。

### Dockerfile 特性

- **多阶段构建**：builder 装依赖，runtime 镜像更小
- **非 root 用户**：`appuser` 运行（安全最佳实践）
- **HEALTHCHECK**：每 30s 调 `/health` 接口
- **gunicorn + uvicorn worker**：4 worker，生产级配置

详见 [docs/deployment.md](docs/deployment.md)。

## 🔁 CI/CD

GitHub Actions 流水线（`.github/workflows/ci.yml`）：

```
push/PR
  ↓
1. lint    (flake8 代码风格)
  ↓
2. test    (MySQL service 容器 + alembic upgrade + 跑测试)
  ↓ (仅 main 分支)
3. build   (构建 Docker 镜像，推到 Docker Hub)
  ↓
4. deploy  (SSH 到服务器，docker compose up)
```

### 配置 GitHub Secrets

仓库 Settings → Secrets and variables → Actions：

| Secret | 用途 | 必需 |
|--------|------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 | 推镜像时 |
| `DOCKER_PASSWORD` | Docker Hub access token | 推镜像时 |
| `DEPLOY_HOST` | 部署服务器 IP | 自动部署 |
| `DEPLOY_USER` | SSH 用户 | 自动部署 |
| `DEPLOY_KEY` | SSH 私钥 | 自动部署 |

## 🤖 Claude Code 集成

### CLAUDE.md

[CLAUDE.md](CLAUDE.md) 是 Claude Code 的协作规范，包含：
- 项目结构和设计约定
- 开发规范和命名约定
- 修改代码检查清单
- 7 条禁止事项（硬规则）

### 自动校验 Hook

编辑任何 `*.py` 文件后，Hook 自动跑 AST 校验：

- ✅ Python 语法检查
- ✅ Repository 层不能调 `db.commit()`
- ✅ 不能用 `@on_event`（已弃用）
- ✅ 不能用 passlib（与 bcrypt 4.x+ 不兼容）
- ✅ Service 层必须有 bcrypt 导入
- ✅ 业务代码不能直接 `print()`（用 logger）
- ✅ 修改 app/tests 时自动跑测试

配置在 [.claude/settings.json](.claude/settings.json)，脚本在 [scripts/check.py](scripts/check.py)。

## ⚠️ 生产部署清单

- [x] Gunicorn + Uvicorn worker 多进程部署
- [x] 容器化（Dockerfile + docker-compose）
- [x] CI/CD 流水线
- [x] 结构化日志
- [x] 数据库迁移工具
- [x] 健康检查接口
- [ ] HTTPS 配置（Nginx 反代 + Let's Encrypt）
- [ ] CORS 配置（如需前后端分离）
- [ ] JWT 认证 + 接口鉴权
- [ ] 限流（slowapi 或 API Gateway）
- [ ] Prometheus metrics 监控
- [ ] 依赖锁文件（pip-compile / poetry）
- [ ] 单元测试覆盖率 > 80%

## 📚 文档

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | Claude Code 协作规范 |
| [DETAIL.md](DETAIL.md) | 精细代码讲解，逐模块、逐函数注释 |
| [docs/](docs/) | 项目文档目录 |
| [docs/architecture.md](docs/architecture.md) | 四层架构设计 |
| [docs/api.md](docs/api.md) | REST API 接口文档 |
| [docs/deployment.md](docs/deployment.md) | 部署指南 |
| [docs/database.md](docs/database.md) | 数据库设计与迁移 |
| [docs/security.md](docs/security.md) | 安全设计 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 故障排查 |
