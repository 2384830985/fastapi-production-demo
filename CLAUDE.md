# CLAUDE.md

> 本文件用于指导 Claude Code 在本项目中工作。每次会话开始时请阅读本文。

## 项目概述

FastAPI 用户管理示例项目，四层架构 + 完整基础设施，作为生产级脚手架。

- **框架**：FastAPI + SQLAlchemy 2.0 + Pydantic v2
- **数据库**：MySQL 8+（通过 PyMySQL 驱动）
- **密码**：bcrypt 官方包（不用 passlib，避免兼容性警告）
- **迁移**：Alembic
- **Python 版本**：3.9+（用 `Optional[X]` 而非 `X | None`，兼容 3.9）

## 项目结构

```
fastapi-user-demo/
├── app/
│   ├── api/            # 路由层（HTTP）
│   ├── schema/         # 校验层（Pydantic）
│   ├── service/        # 业务层（业务规则 + 事务）
│   ├── repository/     # 数据库层（ORM CRUD，不 commit）
│   ├── models/         # ORM 模型（SQLAlchemy）
│   ├── db.py           # 引擎、Session、Base、get_db
│   ├── logger.py       # 日志配置
│   └── exception_handlers.py  # 全局异常处理
├── alembic/            # 数据库迁移
├── tests/
├── docs/               # 项目文档
├── .github/workflows/  # CI/CD
├── Dockerfile
├── docker-compose.yml
├── main.py             # 应用入口
├── .env                # 真实配置（git忽略）
└── .env.example        # 配置模板
```

## 关键设计约定

### 1. 四层架构，依赖方向不可逆
```
API → Service → Repository → ORM
```
- Service 层**不允许** import `fastapi.Depends` 之外的 FastAPI 概念（业务异常应继承 Exception，不是 HTTPException）
- Repository 层**不允许**调 `db.commit()`，事务由 Service 控制
- Schema 层不依赖任何其他层

### 2. 事务边界
- Repository 只 `add/flush/delete`
- Service 的写操作显式调 `self._commit()`
- 异常时 Service 主动 `rollback`

### 3. 密码安全
- 永远不存明文，用 `app.service.user_service.hash_password`
- 响应模型必须用 `UserOut`，绝不用 `UserInDB` 作 `response_model`
- `UserInDB` 仅在 Repository ↔ Service 之间流转

### 4. 配置管理
- 敏感信息（密码、key）走 `.env`，不硬编码
- 代码用 `os.getenv(name, default)` 读取
- `.env` 已在 `.gitignore` 排除

### 5. 异常处理
- 业务异常继承 `Exception`，定义在 `app/service/user_service.py`
- 路由**不需要** try/except，全局处理器自动映射
- 新增业务异常时，在 `app/exception_handlers.py` 注册处理器

## 开发规范

### 代码风格
- 所有 docstring 和注释用中文
- import 顺序：标准库 → 第三方 → 本项目
- 每个模块顶部必须有 docstring 说明职责
- 关键 import 必须有行内注释说明用途

### 命名
- Schema 模型：`UserCreate` / `UserUpdate` / `UserOut` / `UserInDB`
- ORM 模型：单数 `User`，`__tablename__` 用复数 `users`
- Service 方法：`create_user` / `get_user` / `list_users` / `update_user` / `delete_user`

### 提交信息
- 用中文，格式：`<类型>: <描述>`
- 类型：`feat` / `fix` / `refactor` / `docs` / `test` / `chore`
- 示例：`feat: 添加邮箱字段并生成 Alembic 迁移`

## 常用命令

```bash
# 推荐：用 Makefile
make help          # 看所有命令
make install       # 装依赖
make dev           # 启动开发服务
make check         # 一键检查（lint + typecheck + test）
make test          # 跑测试
make test-cov      # 测试 + 覆盖率
make migrate       # 数据库迁移
make migrate-new MSG="add email"  # 生成迁移
make docker-up     # Docker 部署
make clean         # 清理缓存

# 或手动
source env/bin/activate
python -m uvicorn main:app --reload
pytest tests/ -v --cov=app
alembic upgrade head
```

## 修改代码时检查清单

新增/修改 API 接口时：
- [ ] 路由函数无 try/except（用全局异常处理器）
- [ ] 响应模型用 `UserOut`，不含密码字段
- [ ] 路径参数有类型注解（如 `user_id: int`）
- [ ] 查询参数有 `Query` 约束（如 `ge=0`, `le=100`）

新增字段时：
- [ ] 改 `app/models/user.py` 加列
- [ ] 改 `app/schema/user.py` 加 Schema 字段
- [ ] 生成 Alembic 迁移：`alembic revision --autogenerate -m "..."`
- [ ] 检查迁移脚本（autogenerate 不一定 100% 准确）
- [ ] 执行迁移：`alembic upgrade head`

新增业务异常时：
- [ ] 异常类继承 `Exception`，定义在相关 Service 文件
- [ ] 在 `app/exception_handlers.py` 注册 `@app.exception_handler`
- [ ] 异常映射到合适的 HTTP 状态码（4xx 表示客户端错误，5xx 表示服务端错误）

## 禁止事项

- ❌ 不要在 Service 层 import `HTTPException`
- ❌ 不要在 Repository 层调 `db.commit()`
- ❌ 不要用 `UserInDB` 作 `response_model`
- ❌ 不要把密码明文写进代码或日志
- ❌ 不要用 `@app.on_event("startup")`（已弃用，用 `lifespan`）
- ❌ 不要用 passlib（与 bcrypt 4.x+ 不兼容）
- ❌ 不要在 Python 3.9 项目用 `X | None` 语法（用 `Optional[X]`）
- ❌ 不要直接 `print()` 业务日志（用 `logger.info` 等）
- ❌ 不要在 `.env` 里用弱默认值（SECRET_KEY、DB_PASSWORD 启动时校验）
- ❌ 不要用 `CORS_ORIGINS=*`（生产必须具体域名）
- ❌ 不要用 `>=` 装生产依赖（用 `requirements.lock` 锁定版本）

## 工程化工具

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| Makefile | 统一命令 | `Makefile` |
| .editorconfig | 编辑器统一 | `.editorconfig` |
| mypy | 类型检查 | `mypy.ini` |
| flake8 | 代码风格 | 命令行参数 |
| pre-commit | git hook | `.pre-commit-config.yaml` |
| pytest | 测试框架 | `pytest.ini` |
| pytest-cov | 覆盖率 | `pytest.ini` |
| pip-compile | 依赖锁文件 | `requirements.lock` |
| Claude Hook | 编辑后校验 | `.claude/settings.json` + `scripts/check.py` |
| slowapi | 限流 | `app/ratelimit.py` |
| CORS | 跨域 | `main.py` + `CORS_ORIGINS` 环境变量 |
| 配置校验 | fail-fast | `app/config.py` |

## 相关文档

- [README.md](README.md) — 项目概览
- [DETAIL.md](DETAIL.md) — 精细代码讲解
- [docs/](docs/) — 架构、部署、API 文档
