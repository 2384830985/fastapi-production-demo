# 架构设计
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


## 四层架构总览

```
┌──────────────────────────────────────────────────┐
│  API 层 (app/api/)                               │
│  职责：HTTP 路由、参数解析、异常映射             │
│  依赖：Schema、Service                           │
└──────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│  Schema 层 (app/schema/)                         │
│  职责：请求/响应数据模型、Pydantic 校验           │
│  依赖：无（纯数据模型）                           │
└──────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│  Service 层 (app/service/)                       │
│  职责：业务规则、密码哈希、事务控制               │
│  依赖：Schema、Repository                        │
└──────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│  Repository 层 (app/repository/)                 │
│  职责：ORM CRUD，不 commit                       │
│  依赖：ORM 模型、Schema (UserInDB)               │
└──────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│  ORM 模型 (app/models/) + 数据库 (app/db.py)     │
│  职责：表结构定义、连接池管理                     │
└──────────────────────────────────────────────────┘
                       ↓
                   MySQL 数据库
```

## 依赖方向（严格不可逆）

```
API → Schema
API → Service → Repository → ORM
Service → Schema
Repository → Schema (仅 UserInDB)
```

**禁止的依赖**：
- Service ❌ → FastAPI HTTP 概念（除 `Depends`）
- Repository ❌ → `db.commit()`
- Schema ❌ → 任何其他层

## 辅助模块

| 模块 | 职责 |
|------|------|
| `app/db.py` | 引擎、Session、Base、`get_db` 依赖 |
| `app/logger.py` | 日志配置，统一格式 |
| `app/exception_handlers.py` | 全局异常映射 |

## 事务边界设计

**核心原则**：Repository 只 flush，Service 控制 commit/rollback。

### 为什么这么设计

考虑转账场景：扣钱 + 加钱必须同时成功或失败。

**错误设计**（Repository 各自 commit）：
```python
# Repository
def debit(self, user_id, amount):
    ...
    db.commit()  # 提交了，无法回滚

def credit(self, user_id, amount):
    ...
    db.commit()  # 如果这里失败，上面已 commit，数据不一致
```

**正确设计**（Repository 不 commit）：
```python
# Repository
def debit(self, user_id, amount):
    ...
    db.flush()  # 触发 SQL 但不提交

def credit(self, user_id, amount):
    ...
    db.flush()

# Service
def transfer(self, from_id, to_id, amount):
    try:
        self._repo.debit(from_id, amount)
        self._repo.credit(to_id, amount)
        self._commit()  # 一起提交
    except Exception:
        self._repo._db.rollback()  # 一起回滚
        raise
```

## 异常处理设计

### 业务异常与 HTTP 解耦

业务层抛业务异常，API 层（全局处理器）翻译为 HTTP：

```python
# Service 层（不知道 HTTP）
def create_user(self, payload):
    if self._repo.get_by_username(payload.username):
        raise UserAlreadyExistsError(...)  # 业务异常
    ...

# 全局处理器（翻译为 HTTP）
@app.exception_handler(UserAlreadyExistsError)
async def handle(_, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
```

### 异常映射表

| 业务异常 | HTTP | 场景 |
|---------|------|------|
| `UserNotFoundError` | 404 | 用户不存在 |
| `UserAlreadyExistsError` | 409 | 用户名冲突 |
| `IntegrityError` | 409 | DB 唯一约束兜底 |
| `Exception` | 500 | 未捕获异常，不暴露细节 |

## 依赖注入链

```
请求 → Depends(get_db) → db
       ↓
       Depends(get_user_service) → UserService(UserRepo(db))
       ↓
       路由函数 → svc.create_user(payload)
```

`get_db` 用 `yield` + `finally` 保证请求结束自动关闭 Session。

## 扩展点

| 需求 | 改哪里 |
|------|--------|
| 加新接口 | `app/api/<resource>.py` + 注册到 `main.py` |
| 加新业务规则 | `app/service/<resource>_service.py` |
| 加新表 | `app/models/<resource>.py` + Alembic 迁移 |
| 换 PostgreSQL | 改 `.env` 的 `DATABASE_URL` |
| 加 Redis 缓存 | `app/cache/` 新模块，Service 层调用 |
| 加 JWT 鉴权 | `app/api/auth.py` + `app/dependencies/auth.py` |
