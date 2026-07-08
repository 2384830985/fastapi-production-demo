# 学习路线总索引
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 本系列文章带你从零掌握这个 FastAPI 用户管理项目涉及的所有技能。

## 📚 系列文章（共 10 篇，已全部完成）

### 阶段 1：基础（先打地基）

| # | 标题 | 状态 | 学完你能 |
|---|------|------|---------|
| 01 | [Python 现代特性与类型注解](01-python-modern-typing.md) | ✅ | 看懂项目里所有"奇怪"语法 |
| 02 | [FastAPI 框架入门与原理](02-fastapi-internals.md) | ✅ | 理解 ASGI、依赖注入、路由匹配 |
| 03 | [Pydantic v2 数据校验深入](03-pydantic-v2.md) | ✅ | 设计 Schema、写自定义校验器 |

### 阶段 2：数据存储（落地到数据库）

| # | 标题 | 状态 | 学完你能 |
|---|------|------|---------|
| 04 | [SQLAlchemy 2.0 ORM 完全指南](04-sqlalchemy-2.md) | ✅ | 写 ORM 模型、用 Session 查询 |
| 05 | [Alembic 数据库迁移原理与实践](05-alembic-migration.md) | ✅ | 加字段、回滚、autogenerate |

### 阶段 3：架构与工程（生产级关键）

| # | 标题 | 状态 | 学完你能 |
|---|------|------|---------|
| 06 | [四层架构设计原理](06-layered-architecture.md) | ✅ | 设计解耦的层次结构 |
| 07 | [密码安全与事务边界](07-security-and-transactions.md) | ✅ | 用 bcrypt、JWT 鉴权、控制事务 |
| 08 | [异常处理与日志系统](08-exceptions-and-logging.md) | ✅ | 全局异常处理、结构化日志 |

### 阶段 4：部署与协作（上线 + AI 协作）

| # | 标题 | 状态 | 学完你能 |
|---|------|------|---------|
| 09 | [Docker 容器化与 CI/CD](09-docker-and-cicd.md) | ✅ | 多阶段构建、GitHub Actions |
| 10 | [Claude Code Hook 与 AST 静态分析](10-claude-hooks-and-ast.md) | ✅ | 写自定义校验 Hook |

### 附录（实战 + 面试 + 调试 + 工程化 + 上线审计）

| # | 标题 | 状态 | 学完你能 |
|---|------|------|---------|
| 11 | [项目代码导览](11-code-walkthrough.md) | ✅ | 按文件清单通读项目 |
| 12 | [动手实战（5 个扩展任务）](12-hands-on-projects.md) | ✅ | 加字段、加模块、加 RBAC、加缓存 |
| 13 | [面试题集（30 题）](13-interview-questions.md) | ✅ | 应对 FastAPI 相关面试 |
| 14 | [常见错误与调试技巧](14-debugging-guide.md) | ✅ | 25 个常见错误排查 |
| 15 | [项目工程化指南](15-project-engineering.md) | ✅ | Makefile/mypy/pre-commit/锁文件/限流/CORS |
| 16 | [上线审计与修复实战](16-audit-and-fix.md) | ✅ | 上线前审计方法论 + P0 修复实战 |

---

## 🎯 学习方式

### 推荐节奏

每篇文章 4000-6000 字，建议：

1. **先通读一遍**：理解整体概念，不求甚解
2. **对照源码看**：找到项目里对应代码，理解每个概念怎么用
3. **做自测题**：每篇末尾有 3-4 道题，验证理解
4. **动手改代码**：试着改项目代码，看效果

### 每篇结构

- **你将学到**：明确目标
- **正文**：概念 + 代码 + 原理
- **常见坑**：踩过的坑
- **自测题**：附答案（折叠）
- **小结**：关键点速查
- **下篇预告**：串联下一篇

### 配套资源

- 项目代码：[/](../..)
- 项目文档：[../](../)
- 精细代码讲解：[../../DETAIL.md](../../DETAIL.md)

---

## 📋 学习清单

学完后你应该能做到：

- [ ] 看懂项目里所有 Python 语法（类型注解、泛型、`__future__`）
- [ ] 解释 FastAPI 为什么比 Flask 快
- [ ] 手写一个 `Depends` 依赖链
- [ ] 设计 Pydantic Schema 继承体系
- [ ] 用 SQLAlchemy 2.0 写 ORM 模型
- [ ] 用 `Mapped[X]` 推断列类型
- [ ] 解释 flush 和 commit 的区别
- [ ] 用 Alembic 生成迁移脚本
- [ ] 解释为什么 Repository 不 commit
- [ ] 设计全局异常处理器
- [ ] 配置结构化日志
- [ ] 写 Dockerfile 多阶段构建
- [ ] 配置 GitHub Actions 流水线
- [ ] 用 `ast` 模块写静态校验器
- [ ] 解释 bcrypt 工作因子的选择
- [ ] 设计 JWT 鉴权流程（含 SECRET_KEY 兜底）
- [ ] 处理并发场景下的唯一约束冲突
- [ ] 用 `${VAR:?}` 强制要求敏感环境变量
- [ ] 用 `APP_ENV` 控制生产环境的文档暴露
- [ ] 解释为什么生产只走 Alembic 而不用 `create_all`
- [ ] 写错误响应时不暴露 `str(exc)` 内部细节

---

## 🗺️ 全系列知识点速览

### 阶段 1：基础

**01 Python 现代特性与类型注解**
- 类型注解是 hint，不强制
- `from __future__ import annotations` 让注解延迟求值
- `Optional[X]` 等价 `X | None`，3.9 用 Optional 更兼容
- `TypeVar + Generic` 实现泛型（`Page[T]`）
- `Mapped[X]` 是 SQLAlchemy 自定义注解

**02 FastAPI 框架入门与原理**
- FastAPI = Starlette + Pydantic
- ASGI 异步，I/O 等待时让出 CPU
- `Depends` 依赖注入，`yield` 依赖自动清理
- `APIRouter` 模块化路由
- `lifespan` 替代弃用的 `on_event`
- 路由按注册顺序匹配，静态路径在前

**03 Pydantic v2 数据校验深入**
- v2 用 Rust 重写，比 v1 快 5-50 倍
- 方法名变更：`.dict()` → `.model_dump()`，`.parse_obj()` → `.model_validate()`
- `Field(...)` 必填，`Field(default=None)` 可选
- `@field_validator` 字段级校验，`@model_validator` 跨字段校验
- `from_attributes=True` 替代 v1 的 `orm_mode`
- `Generic[T]` 实现泛型模型

### 阶段 2：数据存储

**04 SQLAlchemy 2.0 ORM 完全指南**
- `DeclarativeBase` 替代 `declarative_base()`
- `Mapped[X] = mapped_column(...)` 类型注解写法
- `select(stmt).where(...)` 替代 `query().filter()`
- `db.scalars(stmt).one_or_none()` 查询单条
- `flush` 发 SQL 不提交，`commit` 提交事务
- `pool_pre_ping=True` 防失效连接
- `pool_recycle=3600` 每小时回收

**05 Alembic 数据库迁移原理与实践**
- `alembic_version` 表记录当前版本
- `revision` / `down_revision` 构成版本链
- `target_metadata = Base.metadata` 让 autogenerate 识别模型
- `stamp head` 标记当前为最新，不执行 SQL
- autogenerate 后必检查脚本
- 改列名用 `alter_column`，不删列加列
- 生产迁移前备份，大表用 `ALGORITHM=INPLACE`

### 阶段 3：架构与工程

**06 四层架构设计原理**
- 依赖方向不可逆：API → Service → Repository → ORM
- Service 不依赖 HTTP 概念（业务异常继承 Exception）
- Repository 不 commit（Service 控制事务）
- Repository 对外暴露 Schema，不暴露 ORM
- ORM 模型 vs Schema 模型：用途不同，分开

**07 密码安全与事务边界**
- bcrypt 是慢哈希，自带盐，可调工作因子
- rounds=12 推荐（约 250ms）
- `checkpw` 常量时间比对，防时序攻击
- JWT 无状态 token，payload 不加密
- SECRET_KEY 未配置时拒绝签发（RuntimeError 兜底）
- 鉴权失败统一抛 HTTPException(401)，带 `WWW-Authenticate` 头
- 登录失败不区分"用户不存在"和"密码错误"，防爆破
- ACID：原子/一致/隔离/持久
- 事务边界：Service 控制，Repository 不 commit
- 并发兜底：DB UNIQUE 约束 + 捕获 IntegrityError

**08 异常处理与日志系统**
- 业务异常继承 Exception，不绑 HTTP
- 全局处理器 `@app.exception_handler` 注册
- 500 错误、健康检查失败不返回 `str(exc)`（脱敏）
- `IntegrityError` 映射 409 有过粗陷阱，严谨做法按错误码分流
- logging 组件：Logger → Handler → Formatter
- `%` 占位符延迟格式化，性能好
- 容器化日志输出 stdout
- 不记敏感信息（密码、token、PII）

### 阶段 4：部署与协作

**09 Docker 容器化与 CI/CD**
- 多阶段构建：builder 编译，runtime 只复制产物
- `python:slim` 比 alpine 兼容性好
- 非 root 用户运行（安全）
- HEALTHCHECK 容器健康检查
- `.dockerignore` 排除 `.env`
- `depends_on: condition: service_healthy` 等依赖健康
- `${VAR:?msg}` 强制要求敏感环境变量（DB_PASSWORD / SECRET_KEY）
- `${VAR:-default}` 给非敏感配置默认值
- `APP_ENV=production` 关闭 `/docs` `/redoc` `/openapi.json`
- 生产只走 Alembic 迁移，不用 `create_all`（防 schema 漂移）
- GitHub Actions services 启动数据库容器
- 镜像缓存：先 COPY requirements，再 COPY 代码

**10 Claude Code Hook 与 AST 静态分析**
- Hook 编辑后自动执行校验
- PostEdit 编辑后触发，PreCommit 提交前触发
- `ast.parse` 把源码解析成 AST
- `NodeVisitor` 访问者模式遍历 AST
- `visit_XXX` 处理特定类型节点
- `generic_visit` 继续遍历子节点
- AST 比 grep 精确（零误报，能跨节点分析）

---

## 🎉 学完后

现在你已经具备：

| 维度 | 能力 |
|------|------|
| 基础 | 看懂任何 FastAPI 项目 |
| 数据 | 设计数据库、写迁移 |
| 架构 | 设计解耦的生产级架构 |
| 安全 | bcrypt、JWT、防攻击 |
| 部署 | Docker、CI/CD |
| 协作 | Claude Hook、AST 校验 |

**下一步建议**：
1. 对照源码通读项目，验证理解
2. 自己动手扩展功能（加字段、加模块）
3. 写单元测试，提升覆盖率
4. 部署到云服务器，实战验证

祝你写出更好的生产级项目！🚀
