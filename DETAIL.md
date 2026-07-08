# FastAPI 用户管理项目 - 精细代码讲解

> 本文档从入口文件开始，逐模块、逐函数、逐关键行讲解项目实现。
> 适合 FastAPI / SQLAlchemy / Pydantic v2 初学者对照源码学习。

---

## 目录

1. [项目结构总览](#1-项目结构总览)
2. [入口文件 main.py](#2-入口文件-mainpy)
3. [配置与数据库 app/db.py](#3-配置与数据库-appdbpy)
4. [ORM 模型 app/models/user.py](#4-orm-模型-appmodelsuserpy)
5. [Pydantic Schema app/schema/user.py](#5-pydantic-schema-appschemauserpy)
6. [Repository 层 app/repository/user_repo.py](#6-repository-层-apprepositoryuser_repopy)
7. [Service 层 app/service/user_service.py](#7-service-层-appserviceuser_servicepy)
8. [API 层 app/api/users.py](#8-api-层-appapiuserspy)
9. [测试 tests/test_api.py](#9-测试-teststest_apipy)
10. [完整请求时序图](#10-完整请求时序图)
11. [常见疑问 FAQ](#11-常见疑问-faq)
12. [日志系统 app/logger.py](#12-日志系统-apploggerpy)
13. [全局异常处理 app/exception_handlers.py](#13-全局异常处理-appexception_handlerspy)
14. [Alembic 数据库迁移](#14-alembic-数据库迁移)
15. [分页查询 Page[T] 模型](#15-分页查询-paget-模型)
16. [健康检查接口](#16-健康检查接口)
17. [Docker 容器化](#17-docker-容器化)
18. [CI/CD GitHub Actions](#18-cicd-github-actions)
19. [Claude Code Hook 自动校验](#19-claude-code-hook-自动校验)
20. [CLAUDE.md 协作规范](#20-claudemd-协作规范)
21. [docs/ 文档目录](#21-docs-文档目录)

---

## 1. 项目结构总览

```
fastapi-user-demo/
├── .env                    # 真实环境变量（密码等，git 忽略）
├── .env.example            # 配置模板
├── .gitignore
├── requirements.txt        # 依赖清单
├── README.md
├── DETAIL.md               # 本文档
├── main.py                 # 应用入口
├── app/
│   ├── __init__.py
│   ├── db.py               # 数据库引擎、Session、Base
│   ├── api/                # 路由层（处理 HTTP）
│   │   ├── __init__.py
│   │   └── users.py
│   ├── schema/             # 校验层（Pydantic 模型）
│   │   ├── __init__.py
│   │   └── user.py
│   ├── models/             # ORM 模型（SQLAlchemy，对应表）
│   │   ├── __init__.py
│   │   └── user.py
│   ├── service/            # 业务层（业务规则、密码哈希）
│   │   ├── __init__.py
│   │   └── user_service.py
│   └── repository/         # 数据库层（CRUD）
│       ├── __init__.py
│       └── user_repo.py
└── tests/
    └── test_api.py
```

**四层架构关系图**：

```
HTTP 请求
   ↓
API 层 (app/api/)          ← 处理 HTTP、异常映射
   ↓
Schema 层 (app/schema/)    ← Pydantic 自动校验请求体
   ↓
Service 层 (app/service/)  ← 业务规则、密码哈希
   ↓
Repository 层 (app/repository/) ← 封装数据库操作
   ↓
ORM 模型 (app/models/)     ← SQLAlchemy 映射表结构
   ↓
MySQL (testdb.users)
```

---

## 2. 入口文件 main.py

**职责**：创建 FastAPI 应用、注册路由、启动时建表。

```python
from fastapi import FastAPI
from app.api import users_router
from app.db import engine, Base
import app.models  # noqa: F401
```

| 导入 | 用途 |
|------|------|
| `FastAPI` | 应用主类 |
| `users_router` | 用户路由器 |
| `engine` | 数据库引擎（建表用） |
| `Base` | ORM 模型基类（收集所有表元数据） |
| `import app.models` | 副作用导入：触发 ORM 模型注册到 Base.metadata |

### 创建应用

```python
app = FastAPI(
    title="用户管理 API",
    description="FastAPI 四层架构示例：路由 / 业务 / 校验 / 数据库（MySQL）",
    version="1.0.0",
)
```

这三项元信息会显示在 `/docs` Swagger 文档顶部。

### 启动时自动建表

```python
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表已就绪")
```

- `@app.on_event("startup")` 是 FastAPI 生命周期钩子，应用启动时执行一次
- `Base.metadata.create_all` 会遍历所有继承 `Base` 的 ORM 模型，生成 `CREATE TABLE IF NOT EXISTS`
- **已存在的表不会被修改**，加新字段需要手动迁移（生产用 Alembic）

### 注册路由

```python
app.include_router(users_router)
```

把 `users_router`（在 `app/api/users.py` 定义）挂到 app 上，所有 `/users` 路径由它处理。

---

## 3. 配置与数据库 app/db.py

**职责**：从环境变量读取配置、创建引擎、Session 工厂、Base 类、`get_db` 依赖。

### 加载环境变量

```python
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

load_dotenv()  # 从 .env 文件加载到 os.environ

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "testdb")
```

**关键点**：
- `load_dotenv()` **不会覆盖**已存在的系统环境变量
- 本地开发用 `.env`，生产用系统环境变量，代码完全不用改
- `os.getenv(name, default)` 第二个参数是默认值，找不到时返回

### 拼接 DATABASE_URL

```python
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)
```

URL 格式：`驱动+协议://用户:密码@主机:端口/库?参数`

- `mysql+pymysql` 表示用 PyMySQL 驱动连 MySQL
- `charset=utf8mb4` 支持完整 emoji 和中文（mb4 = multi-byte 4）

### 创建引擎

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)
```

| 参数 | 作用 |
|------|------|
| `pool_pre_ping=True` | 借出连接前先 ping，避免拿到失效连接 |
| `pool_recycle=3600` | 连接每小时回收（MySQL 默认 8h 超时，提前回收更稳） |
| `echo=False` | True 时打印所有 SQL，调试用 |

### Session 工厂

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

- `sessionmaker` 是会话工厂，调用 `SessionLocal()` 生成一个 Session
- `autocommit=False`：必须手动 `db.commit()` 才提交事务
- `autoflush=False`：不在查询前自动 flush，避免意外 SQL

### Base 类

```python
class Base(DeclarativeBase):
    pass
```

所有 ORM 模型继承 `Base`，`Base.metadata` 会自动收集所有表结构信息。

### `get_db` 依赖（FastAPI 核心模式）

```python
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**这是 FastAPI 依赖注入的标准写法**：

1. 请求进来时执行 `db = SessionLocal()` 创建 Session
2. `yield db` 把 Session 注入到路由函数
3. 路由执行完毕（无论成功失败），`finally` 自动 `db.close()`

**为什么这么写**：每个请求独立 Session，避免并发请求互相污染，连接自动归还连接池。

---

## 4. ORM 模型 app/models/user.py

**职责**：定义 `users` 表结构。

```python
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False,
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
```

### SQLAlchemy 2.0 新写法解析

```python
id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
```

- `Mapped[int]`：类型注解，告诉 SQLAlchemy 这一列是 `int`
- `mapped_column(...)`：配置列属性
  - `primary_key=True`：主键
  - `autoincrement=True`：自增

### 各字段配置

| 字段 | 类型 | 关键约束 | 说明 |
|------|------|---------|------|
| `id` | Integer | PK, autoincrement | 主键自增 |
| `username` | String(20) | unique, index, not null | 用户名唯一+建索引加速查询 |
| `hashed_password` | String(128) | not null | bcrypt 哈希约 60 字符，留余量 |
| `created_at` | DateTime | server_default | 插入时 MySQL 自动填当前时间 |
| `updated_at` | DateTime | server_default + onupdate | 插入和更新时自动刷新 |

**`server_default` vs `default`**：
- `server_default=func.current_timestamp()`：让 **MySQL** 写入默认值（DDL 里带 DEFAULT）
- `default=...`：让 **Python** 写入默认值（不会出现在 DDL）

---

## 5. Pydantic Schema app/schema/user.py

**职责**：定义 API 请求体/响应体的校验规则。

### 类继承关系

```
BaseModel
   │
   ├─ UserBase (username)
   │    ├─ UserCreate (+password)      # POST /users 请求体
   │    ├─ UserOut (+id)               # 响应体（无密码）
   │    └─ UserInDB (+hashed_password) # 内部传输
   │
   └─ UserUpdate (username?, password?) # PUT /users/{id} 请求体（全可选）
```

### UserBase — 公共基类

```python
class UserBase(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$",
        description="用户名，3-20 位字母数字下划线",
    )
```

- `Field(...)` 第一个参数 `...` 表示**必填**（不能用 None）
- `min_length` / `max_length`：长度限制
- `pattern`：正则约束，只允许字母数字下划线
- `description`：显示在 Swagger 文档里

### UserCreate — 创建用户

```python
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=64)
```

继承 `UserBase` 自动获得 `username` 字段，再加 `password`。

### UserUpdate — 更新用户（字段全可选）

```python
class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: Optional[str] = Field(default=None, min_length=6, max_length=64)
```

**为什么不继承 UserBase**：因为更新时 username 是可选的，但 UserBase 的 username 是必填。

### UserOut — 对外响应

```python
class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
```

- 继承 UserBase（有 username）+ 加 id
- **没有 password / hashed_password 字段** → FastAPI 用它作 `response_model` 时会自动过滤掉密码
- `from_attributes=True`：允许从普通对象的属性创建（`UserOut.model_validate(orm_obj)`）

### UserInDB — 内部存储模型

```python
class UserInDB(UserOut):
    hashed_password: str
```

Repository 层返回这个模型，Service 层内部使用。**永远不会直接返回给前端**。

---

## 6. Repository 层 app/repository/user_repo.py

**职责**：封装所有数据库操作，对 Service 层返回 `UserInDB`（Pydantic），不暴露 ORM `User`。

### 类定义与构造

```python
class UserRepo:
    def __init__(self, db: Session) -> None:
        self._db = db
```

**每个请求一个 `UserRepo` 实例**，传入该请求的 db session。

### ORM ↔ Schema 转换器

```python
@staticmethod
def _to_schema(user: User) -> UserInDB:
    return UserInDB(
        id=user.id,
        username=user.username,
        hashed_password=user.hashed_password,
    )
```

**为什么要转换**：ORM `User` 和 Pydantic `UserInDB` 是两个体系，不直接互通。这层转换保证上层完全不接触 ORM。

### 查询：按 id

```python
def get(self, user_id: int) -> Optional[UserInDB]:
    user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
    return self._to_schema(user) if user else None
```

**SQLAlchemy 2.0 写法**：
- `select(User).where(User.id == user_id)` 构造 SELECT 语句
- `db.scalars(stmt)` 返回 `ScalarResult`（标量结果集，直接是 User 对象）
- `.one_or_none()` 返回单条，找不到返回 None，多于一条抛异常

等价 SQL：
```sql
SELECT * FROM users WHERE id = %s LIMIT 2
```

### 查询：列表

```python
def list_all(self) -> list[UserInDB]:
    users = self._db.scalars(select(User)).all()
    return [self._to_schema(u) for u in users]
```

`.all()` 把所有结果收集成 list。

### 创建

```python
def create(self, username: str, hashed_password: str) -> UserInDB:
    user = User(username=username, hashed_password=hashed_password)
    self._db.add(user)        # 加入会话（INSERT 排队）
    self._db.commit()         # 提交事务（真正执行 SQL）
    self._db.refresh(user)    # 刷新：拿回自增 id 和默认时间戳
    return self._to_schema(user)
```

**三步走**：`add` → `commit` → `refresh`

### 更新

```python
def update(self, user_id, username=None, hashed_password=None):
    user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
    if user is None:
        return None

    if username is not None:
        user.username = username           # 直接改属性
    if hashed_password is not None:
        user.hashed_password = hashed_password

    self._db.commit()
    self._db.refresh(user)
    return self._to_schema(user)
```

**关键点**：只更新非 None 字段（实现 PATCH 语义）。

### 删除

```python
def delete(self, user_id: int) -> bool:
    user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
    if user is None:
        return False
    self._db.delete(user)   # 标记删除
    self._db.commit()       # 真正执行 DELETE
    return True
```

---

## 7. Service 层 app/service/user_service.py

**职责**：业务规则、密码哈希、业务异常定义。

### 密码哈希上下文

```python
from passlib.context import CryptContext
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

- `schemes=["bcrypt"]`：用 bcrypt 算法
- `deprecated="auto"`：旧算法自动升级
- 全局单例复用

**两个核心方法**：
```python
_pwd_context.hash(plain)         # 哈希明文密码
_pwd_context.verify(plain, hashed)  # 校验密码是否匹配
```

### 业务异常

```python
class UserAlreadyExistsError(Exception):
    """用户名已存在（应映射为 HTTP 409 Conflict）。"""

class UserNotFoundError(Exception):
    """用户不存在（应映射为 HTTP 404 Not Found）。"""
```

**设计理念**：Service 层只关心业务，抛业务异常；API 层负责把业务异常翻译成 HTTP 状态码。这样 Service 不耦合 HTTP 概念。

### 工厂方法

```python
@classmethod
def from_db(cls, db) -> "UserService":
    return cls(UserRepo(db))
```

便捷构造：从 db session 一键创建 service。等价于 `UserService(UserRepo(db))`。

### 创建用户（业务逻辑核心）

```python
def create_user(self, payload: UserCreate) -> UserOut:
    # 1. 业务规则：用户名唯一
    if self._repo.get_by_username(payload.username) is not None:
        raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

    # 2. 密码哈希（绝不存明文）
    hashed = _pwd_context.hash(payload.password)

    # 3. 调用 Repository 写入
    user = self._repo.create(
        username=payload.username,
        hashed_password=hashed,
    )

    # 4. UserInDB → UserOut 转换（屏蔽密码字段）
    return UserOut.model_validate(user)
```

**为什么这里要做 `model_validate`**：Repository 返回 `UserInDB`（含密码），但 API 层应该只拿到 `UserOut`（无密码），Service 层做这次"裁剪"。

### 更新用户

```python
def update_user(self, user_id: int, payload: UserUpdate) -> UserOut:
    existing = self._repo.get(user_id)
    if existing is None:
        raise UserNotFoundError(f"用户 id={user_id} 不存在")

    # 若改用户名，需校验新用户名不冲突
    if payload.username and payload.username != existing.username:
        if self._repo.get_by_username(payload.username) is not None:
            raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

    # 若传了密码，先哈希
    new_hashed = None
    if payload.password:
        new_hashed = _pwd_context.hash(payload.password)

    updated = self._repo.update(
        user_id=user_id,
        username=payload.username,
        hashed_password=new_hashed,
    )
    return UserOut.model_validate(updated)
```

**关键点**：
- 改用户名 → 检查冲突
- 改密码 → 重新哈希
- 不改的字段保持原值（None 不传给 repo）

### 密码校验（供登录用）

```python
def verify_password(self, username: str, plain_password: str) -> bool:
    user = self._repo.get_by_username(username)
    if user is None:
        return False
    return _pwd_context.verify(plain_password, user.hashed_password)
```

`verify` 内部会从 hashed 字符串里解析盐值和算法，做安全比对，**常量时间比较**防时序攻击。

### 依赖注入工厂

```python
def get_user_service(db=Depends(get_db)) -> UserService:
    return UserService.from_db(db)
```

**FastAPI 依赖链**：
```
请求 → get_db() 拿到 db → get_user_service(db) 拿到 service → 路由函数
```

每层都用 `Depends`，FastAPI 自动按顺序解析依赖。

---

## 8. API 层 app/api/users.py

**职责**：定义 HTTP 路由、业务异常→HTTP 映射。

### 路由器创建

```python
router = APIRouter(prefix="/users", tags=["用户管理"])
```

- `prefix="/users"`：所有路由自动加 `/users` 前缀
- `tags=["用户管理"]`：Swagger 文档里分组显示

### 业务异常映射

```python
def _map_service_error(e: Exception) -> HTTPException:
    if isinstance(e, UserNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, UserAlreadyExistsError):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
```

**设计理念**：Service 抛业务异常，API 层统一映射。新增业务异常只需在这里加一行。

### 路由定义模板

```python
@router.post(
    "",                                    # 路径（拼上 prefix = /users）
    response_model=UserOut,                # 响应模型（自动过滤密码）
    status_code=status.HTTP_201_CREATED,   # 成功状态码
    summary="创建用户",                    # Swagger 文档摘要
)
def create_user(
    payload: UserCreate,                                  # 请求体（自动校验）
    svc: UserService = Depends(get_user_service),        # 依赖注入
):
    try:
        return svc.create_user(payload)
    except Exception as e:
        raise _map_service_error(e)
```

### 各接口一览

| 方法 | 路径 | 状态码 | 说明 |
|------|------|--------|------|
| GET | /users | 200 | 列表 |
| GET | /users/{id} | 200 / 404 | 单个 |
| POST | /users | 201 / 409 / 422 | 创建 |
| PUT | /users/{id} | 200 / 404 / 409 / 422 | 更新 |
| DELETE | /users/{id} | 204 / 404 | 删除 |

### `response_model` 的妙用

```python
@router.post("", response_model=UserOut)
def create_user(...):
    return svc.create_user(payload)  # 返回 UserOut 对象
```

即使 service 返回的对象意外包含 `hashed_password`，FastAPI 也会按 `UserOut` 字段过滤掉，**双保险防泄露**。

### 路径参数自动校验

```python
@router.get("/{user_id}")
def get_user(user_id: int, ...):
```

`user_id: int` 让 FastAPI 自动校验：传非数字会返回 422。

---

## 9. 测试 tests/test_api.py

**职责**：用 TestClient 冒烟测试所有接口。

### TestClient 工作原理

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
```

- `TestClient` 内部用 `httpx` 走 ASGI 协议直接调用 app
- **不需要启动 uvicorn**，不需要监听端口
- 速度快，CI 友好

### 完整测试流程

```python
def test_full_flow():
    # 1. 创建用户
    r = client.post("/users", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 201
    user = r.json()
    assert "password" not in user  # 验证响应不含密码
    uid = user["id"]

    # 2. 用户名冲突（应 409）
    r = client.post("/users", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 409

    # 3. 查询列表
    r = client.get("/users")
    assert r.status_code == 200

    # 4. 查询单个
    r = client.get(f"/users/{uid}")
    assert r.json()["username"] == "alice"

    # 5. 更新用户名
    r = client.put(f"/users/{uid}", json={"username": "alice_new"})
    assert r.json()["username"] == "alice_new"

    # 6. 校验失败：密码过短（应 422）
    r = client.put(f"/users/{uid}", json={"password": "123"})
    assert r.status_code == 422

    # 7. 删除
    r = client.delete(f"/users/{uid}")
    assert r.status_code == 204

    # 8. 删除后查不到（应 404）
    r = client.get(f"/users/{uid}")
    assert r.status_code == 404
```

### `sys.path` 修复

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

让 `from main import app` 能找到项目根目录的 `main.py`，便于直接 `python tests/test_api.py` 运行。

---

## 10. 完整请求时序图

以 `POST /users` 为例：

```
客户端 POST /users {"username":"alice","password":"secret123"}
   │
   ▼
┌─────────────────────────────────────────────────┐
│ main.py → app 接收请求                           │
│ FastAPI 根据路由匹配到 app/api/users.py:create_user │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ Schema 层自动校验（Pydantic）                    │
│ - username 符合正则 ✅                            │
│ - password 长度 6-64 ✅                           │
│ 失败 → 自动返回 422                              │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ API 层 create_user(payload, svc=Depends(...))   │
│ FastAPI 先调 get_db() 拿到 db                    │
│ 再调 get_user_service(db) 拿到 svc               │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ Service 层 svc.create_user(payload)             │
│ 1. repo.get_by_username("alice") → None（不重复）│
│ 2. _pwd_context.hash("secret123") → "$2b$12$..." │
│ 3. repo.create("alice", "$2b$12$...")            │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ Repository 层 repo.create(...)                   │
│ 1. user = User(username=, hashed_password=)       │
│ 2. db.add(user)                                  │
│ 3. db.commit()  → INSERT INTO users ...          │
│ 4. db.refresh(user) → 拿到 id=1, created_at      │
│ 5. return UserInDB(id=1, username=, hashed=)     │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ MySQL testdb.users 表                            │
│ INSERT INTO users (username, hashed_password)    │
│ VALUES ('alice', '$2b$12$...')                   │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ Service 层 UserOut.model_validate(user_in_db)   │
│ 裁剪掉 hashed_password                          │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ API 层 return UserOut                            │
│ FastAPI 按 response_model=UserOut 序列化         │
│ 双重保险过滤密码                                 │
└─────────────────────────────────────────────────┘
   │
   ▼
HTTP 201 Created
{"username":"alice","id":1}
```

---

## 11. 常见疑问 FAQ

### Q1: 为什么 ORM 模型 User 和 Pydantic UserInDB 字段几乎一样，还要分两个？

- `User` (SQLAlchemy) 用于操作数据库，方法如 `db.add()`, `db.commit()`
- `UserInDB` (Pydantic) 用于层间数据传递，纯数据，无 ORM 方法
- **解耦**：换数据库（如 MongoDB）时只改 ORM，Schema 不变；换 API 框架时只改 Schema，ORM 不变

### Q2: 为什么每个请求都要新建 db session？

- Session 不是线程安全的，并发请求共用会导致数据混乱
- Session 持有数据库连接，长生命周期会占用连接池资源
- `get_db` 用 `yield` + `finally` 保证请求结束自动关闭

### Q3: `model_validate` 和 `from_orm` 什么关系？

- Pydantic v1 用 `from_orm(obj)`
- Pydantic v2 改名 `model_validate(obj)`，且需要 `model_config = ConfigDict(from_attributes=True)`
- 作用：从任意对象的属性创建 Pydantic 模型

### Q4: 为什么 Service 层用 `Optional[UserInDB]` 而不是 `UserInDB | None`？

- 项目要兼容 Python 3.9
- `X | None` 是 Python 3.10+ 语法
- 文件顶部加 `from __future__ import annotations` 可解决注解问题，但 Pydantic v2 在 3.9 上对 `X | None` 解析有问题，用 `Optional[X]` 最稳

### Q5: 为什么密码字段叫 `hashed_password` 而不是 `password`？

- 防止误用：看到 `hashed_password` 就知道是哈希值，不能直接比对明文
- 命名自文档：减少注释需求
- `UserCreate.password` 是明文（请求体），`UserInDB.hashed_password` 是哈希（存储），名称区分清楚

### Q6: 启动时自动建表，那加新字段怎么办？

`Base.metadata.create_all` 只建不存在的表，**不会修改已有表结构**。加字段方案：

1. **开发环境**：直接 `DROP TABLE users;` 让程序重建（数据丢失）
2. **生产环境**：用 Alembic 做 schema 迁移
   ```bash
   pip install alembic
   alembic init alembic
   alembic revision --autogenerate -m "add email column"
   alembic upgrade head
   ```

### Q7: `Depends` 嵌套依赖是怎么执行的？

```python
def get_user_service(db=Depends(get_db)) -> UserService:
    return UserService.from_db(db)

@router.post("")
def create_user(svc: UserService = Depends(get_user_service)):
    ...
```

FastAPI 解析顺序：
1. 看到 `Depends(get_user_service)` → 调用 `get_user_service`
2. `get_user_service` 又依赖 `Depends(get_db)` → 调用 `get_db`
3. `get_db` yield 一个 db
4. 把 db 传给 `get_user_service`，返回 service
5. 把 service 传给 `create_user`
6. 请求结束，`get_db` 的 finally 执行 `db.close()`

### Q8: 为什么用 PyMySQL 而不是 mysqlclient？

| 驱动 | 优点 | 缺点 |
|------|------|------|
| **PyMySQL** | 纯 Python，无需编译，兼容 MySQL 9.x `caching_sha2_password` | 性能略低 |
| mysqlclient | 性能高（C 实现） | 需编译，依赖系统 mysql 库，9.x 兼容性差 |
| mysql-connector-python | 官方驱动 | 包大，老版本不支持 caching_sha2 |

本项目选 PyMySQL：**安装零依赖、兼容性最好**。

### Q9: 为什么把异常映射写在 API 层而不是 Service 层？

- Service 层应该是"纯业务"的，不知道 HTTP 的存在
- 这样 Service 可以被 CLI 工具、定时任务、其他 Service 复用，而不被 HTTP 绑定
- 测试 Service 时不需要 mock HTTP

### Q10: 如何扩展？

| 需求 | 改哪里 |
|------|--------|
| 加 email 字段 | `models/user.py` 加列 + `schema/user.py` 加字段 + Alembic 迁移 |
| 加登录接口 | 新建 `app/api/auth.py`，复用 `UserService.verify_password` |
| 换 PostgreSQL | 改 `.env` 的 `DATABASE_URL` 为 `postgresql+psycopg://...` |
| 加 Redis 缓存 | 在 `service/` 加 `cache.py`，API 层无感 |
| 加权限校验 | 新建 `app/dependencies/auth.py`，路由函数加 `Depends(check_admin)` |

---

## 📚 延伸阅读

- [FastAPI 官方文档](https://fastapi.tiangolo.com/zh/)
- [SQLAlchemy 2.0 教程](https://docs.sqlalchemy.org/en/20/tutorial/)
- [Pydantic v2 迁移指南](https://docs.pydantic.dev/latest/migration/)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [bcrypt 官方文档](https://github.com/pyca/bcrypt/)
- [PEP 526 - 类型注解](https://peps.python.org/pep-0526/)

---

## 12. 日志系统 app/logger.py

**职责**：统一日志格式、级别、输出目标。

### 核心函数

```python
def setup_logging() -> None:
    """初始化全局日志配置。"""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,  # 容器化部署推荐 stdout
        force=True,
    )
    # 降低第三方库日志级别
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

### 日志格式

```
2026-07-07 17:21:35 | INFO    | app.service.user_service:161 | 用户创建成功 id=2 username=alice
       时间         级别              模块名:行号                    消息
```

### 使用方式

```python
from app.logger import get_logger
logger = get_logger(__name__)

logger.info("用户创建成功 id=%s username=%s", user.id, user.username)
logger.warning("用户名冲突 username=%s", username)
logger.exception("未处理异常: %s", exc)  # 自动带堆栈
```

### 为什么用 stdout 而不是文件

- **容器化友好**：docker logs / kubectl logs 自动收集
- **无需管理文件轮转**：Docker/k8s 负责日志轮转
- **可聚合**：可对接 ELK、Loki、CloudWatch 等

### 级别由环境变量控制

```bash
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload
LOG_LEVEL=ERROR python -m uvicorn main:app
```

---

## 13. 全局异常处理 app/exception_handlers.py

**职责**：把业务异常统一映射为 HTTP 响应，路由函数无需 try/except。

### 注册方式

```python
# main.py
from app.exception_handlers import register_exception_handlers

app = FastAPI(...)
register_exception_handlers(app)
```

### 处理器示例

```python
@app.exception_handler(UserNotFoundError)
async def handle_user_not_found(_: Request, exc: UserNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(IntegrityError)
async def handle_integrity_error(_: Request, exc: IntegrityError):
    logger.warning("数据库完整性约束错误: %s", exc)
    return JSONResponse(status_code=409, content={"detail": "数据冲突"})

@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception):
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
```

### 对比改造前后

**改造前**（每个路由都重复 try/except）：
```python
@router.post("")
def create_user(payload, svc=Depends(...)):
    try:
        return svc.create_user(payload)
    except UserAlreadyExistsError as e:
        raise HTTPException(409, detail=str(e))
    except UserNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        raise _map_service_error(e)
```

**改造后**（路由干净）：
```python
@router.post("")
def create_user(payload, svc=Depends(...)):
    return svc.create_user(payload)
```

### 异常映射表

| 业务异常 | HTTP 状态码 | 触发场景 |
|----------|------------|---------|
| `UserNotFoundError` | 404 | 用户不存在 |
| `UserAlreadyExistsError` | 409 | 用户名冲突 |
| `IntegrityError` | 409 | DB 兜底（如 UNIQUE 约束） |
| `Exception` | 500 | 未捕获异常 |

### 关键设计：500 不暴露内部细节

```python
@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception):
    logger.exception("未处理异常: %s", exc)  # 服务端记完整堆栈
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},  # 客户端只看到通用错误
    )
```

**安全考虑**：500 错误不返回 `str(exc)`，避免泄露 SQL、文件路径等敏感信息。

---

## 14. Alembic 数据库迁移

**职责**：管理 schema 变更版本，支持 autogenerate、回滚。

### 配置文件

- `alembic.ini`：主配置（数据库 URL 从 .env 读取）
- `alembic/env.py`：迁移环境，引入项目 Base.metadata
- `alembic/versions/`：迁移脚本

### env.py 改造点

```python
from dotenv import load_dotenv
load_dotenv()

from app.db import DATABASE_URL, Base
import app.models  # noqa: F401

config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata  # 关键：让 autogenerate 识别模型变化
```

### 加字段流程

```bash
# 1. 修改 app/models/user.py 加字段
class User(Base):
    ...
    email: Mapped[str] = mapped_column(String(100), unique=True)

# 2. 生成迁移脚本
alembic revision --autogenerate -m "add email column"
# 生成 alembic/versions/xxx_add_email_column.py

# 3. 检查迁移脚本（重要！autogenerate 不一定 100% 准确）
# - upgrade() 包含 ALTER TABLE ADD COLUMN
# - downgrade() 包含 ALTER TABLE DROP COLUMN

# 4. 执行迁移
alembic upgrade head
# 或回滚
alembic downgrade -1
```

### 迁移脚本结构

```python
"""add email column

Revision ID: abc123
"""
def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(100), unique=True))

def downgrade() -> None:
    op.drop_column('users', 'email')
```

### 常用命令

| 命令 | 作用 |
|------|------|
| `alembic current` | 查看当前版本 |
| `alembic history` | 迁移历史 |
| `alembic upgrade head` | 升级到最新 |
| `alembic downgrade -1` | 回滚一个版本 |
| `alembic revision --autogenerate -m "msg"` | 自动生成迁移 |
| `alembic upgrade head --sql` | 离线模式生成 SQL（不连库） |

### 已有数据库如何接入 Alembic

如果数据库已有表但未用 Alembic 管理：

```bash
alembic stamp head  # 标记当前数据库为最新版本，不执行 SQL
```

之后改模型生成的迁移才能正常 upgrade。

### 为什么用 Alembic 而不是 `create_all`

| 方式 | 加字段 | 改字段 | 删字段 | 数据迁移 |
|------|--------|--------|--------|---------|
| `create_all` | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 |
| Alembic | ✅ | ✅ | ✅ | ✅ |

`create_all` 只建不存在的表，**永远不会修改已有表结构**。生产环境必须用 Alembic。

---

## 15. 分页查询 Page[T] 模型

**职责**：通用分页响应模型，可装任意类型列表。

### Page 模型定义

```python
from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool = False
```

### 使用方式

```python
# Service 层
def list_users(self, skip=0, limit=20) -> Page[UserOut]:
    users = self._repo.list_all(skip=skip, limit=limit)
    total = self._repo.count()
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
        has_more=(skip + limit) < total,
    )

# API 层
@router.get("", response_model=Page[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    svc=Depends(get_user_service),
):
    return svc.list_users(skip=skip, limit=limit)
```

### 响应示例

```json
GET /users?skip=0&limit=2

{
  "items": [
    {"id": 1, "username": "alice"},
    {"id": 2, "username": "bob"}
  ],
  "total": 5,
  "skip": 0,
  "limit": 2,
  "has_more": true
}
```

### Repository 层分页实现

```python
def list_all(self, skip: int = 0, limit: int = 20):
    users = self._db.scalars(
        select(User).offset(skip).limit(limit)
    ).all()
    return [self._to_schema(u) for u in users]

def count(self) -> int:
    return self._db.scalar(select(func.count()).select_from(User)) or 0
```

等价 SQL：
```sql
SELECT * FROM users LIMIT 2 OFFSET 0;
SELECT COUNT(*) FROM users;
```

### Query 参数校验

```python
skip: int = Query(0, ge=0, description="跳过条数")
limit: int = Query(20, ge=1, le=100, description="每页数量（1-100）")
```

- `ge=0`：skip 必须 ≥ 0
- `ge=1, le=100`：limit 在 1-100 之间，防止恶意请求查全表

### 为什么用泛型 `Page[T]`

- **复用**：用户列表、订单列表、文章列表都能用 `Page[UserOut]` / `Page[OrderOut]`
- **类型安全**：IDE 自动补全 items 字段
- **文档友好**：Swagger 自动渲染正确结构

---

## 16. 健康检查接口

**职责**：探活接口，用于负载均衡、K8s liveness/readiness probe。

### 两个接口

```python
@app.get("/", summary="健康检查")
def health():
    """简单探活（不查数据库）。"""
    return {"status": "ok"}

@app.get("/health", summary="完整健康检查（含数据库连通性）")
def health_check(db: Session = Depends(get_db)):
    """检查应用和数据库连通性。"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logger.error("健康检查数据库异常: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "error", "detail": str(e)},
        )
```

### 区分 `/` 和 `/health`

| 接口 | 用途 | 查 DB | 适合场景 |
|------|------|-------|---------|
| `/` | 简单探活 | 否 | Liveness probe（进程是否活着） |
| `/health` | 完整检查 | 是 | Readiness probe（是否能服务请求） |

### K8s 配置示例

```yaml
livenessProbe:
  httpGet:
    path: /
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### 为什么 503 不是 500

- 503 Service Unavailable：服务暂时不可用，但进程还活着
- 500 Internal Server Error：服务器内部错误（程序 bug）

健康检查失败时返回 503，负载均衡器会把这个实例从池里摘掉，但不重启。

### 为什么用 `SELECT 1`

- `SELECT 1` 是最轻量的查询，不需要访问任何表
- 只验证连接是否有效 + MySQL 是否响应
- `text("SELECT 1")` 是 SQLAlchemy 2.0 推荐写法，避免 SQL 注入风险

---

## 17. Docker 容器化

**职责**：把应用打包成可移植镜像，一键部署。

### 文件清单

| 文件 | 作用 |
|------|------|
| [Dockerfile](../Dockerfile) | 多阶段构建镜像 |
| [docker-compose.yml](../docker-compose.yml) | app + mysql 一键启动 |
| [.dockerignore](../.dockerignore) | 排除无关文件 |
| [docker/mysql-init/](../docker/mysql-init/) | MySQL 初始化脚本目录 |

### Dockerfile 多阶段构建

```dockerfile
# 阶段 1：builder（装依赖）
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y build-essential libffi-dev libssl-dev
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# 阶段 2：runtime（最终镜像）
FROM python:3.11-slim
RUN apt-get update && apt-get install -y libssl3 curl
COPY --from=builder /install /usr/local
COPY . .

# 非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

**为什么多阶段**：
- builder 阶段装 gcc 等编译工具，编译 bcrypt/cffi
- runtime 阶段只复制编译好的包，不带 gcc，镜像小一半

**为什么用非 root**：
- 容器被攻破后，攻击者拿到的是 appuser 权限
- 不能写 /etc、/usr 等系统目录

### docker-compose.yml

```yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD:-123456}
      MYSQL_DATABASE: ${DB_NAME:-testdb}
    ports: ["3306:3306"]
    volumes: [mysql_data:/var/lib/mysql]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]

  app:
    build: .
    depends_on:
      mysql:
        condition: service_healthy  # 等 MySQL 健康再启动
    environment:
      DB_HOST: mysql  # 用 service name
      DB_PASSWORD: ${DB_PASSWORD:-123456}
    ports: ["8000:8000"]
    command: sh -c "alembic upgrade head && gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000"

volumes:
  mysql_data:
```

**关键设计**：
- `depends_on: condition: service_healthy`：等 MySQL 真正就绪
- 启动前自动跑 `alembic upgrade head`
- `DB_HOST: mysql` 用 service name 解析（Docker 内置 DNS）
- `mysql_data` 卷持久化数据

### 常用命令

```bash
docker compose up -d --build     # 构建并启动
docker compose logs -f app       # 看日志
docker compose exec app bash     # 进容器
docker compose exec app alembic revision --autogenerate -m "..."  # 生成迁移
docker compose down              # 停止
docker compose down -v           # 停止+删数据卷
```

---

## 18. CI/CD GitHub Actions

**职责**：push 自动跑 lint/test/build/deploy。

### 流水线设计

```
push/PR
  ↓
Job 1: lint (flake8)
  ↓
Job 2: test (MySQL service 容器 + alembic upgrade + 跑测试)
  ↓ (仅 main 分支)
Job 3: build-and-push (构建 Docker 镜像，推到 Docker Hub)
  ↓
Job 4: deploy (SSH 到服务器，docker compose up)
```

### 关键配置

```yaml
# 取消同分支旧 run
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# MySQL service 容器
services:
  mysql:
    image: mysql:8.4
    env:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: testdb
    ports: ["3306:3306"]
    options: --health-cmd="mysqladmin ping..."

# Docker 镜像构建+推送
- uses: docker/build-push-action@v6
  with:
    cache-from: type=gha    # GitHub Actions 缓存
    cache-to: type=gha,mode=max
```

### 镜像 tag 策略

用 `docker/metadata-action` 自动打 3 个 tag：

| tag | 示例 | 用途 |
|-----|------|------|
| `type=raw,value=latest` | `latest` | 最新版 |
| `type=sha,format=short` | `sha-abc1234` | 版本回滚 |
| `type=ref,event=branch` | `main` | 分支名 |

### 部署阶段（可选）

```yaml
deploy:
  if: github.ref == 'refs/heads/main'
  steps:
    - name: Deploy
      run: |
        ssh $DEPLOY_USER@$DEPLOY_HOST << 'EOF'
          cd /opt/fastapi-user-demo
          git pull
          docker compose pull
          docker compose up -d --remove-orphans
          docker compose exec -T app alembic upgrade head
        EOF
```

### 需要的 GitHub Secrets

| Secret | 用途 |
|--------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `DEPLOY_HOST` | 部署服务器 IP |
| `DEPLOY_USER` | SSH 用户 |
| `DEPLOY_KEY` | SSH 私钥 |

---

## 19. Claude Code Hook 自动校验

**职责**：编辑 Python 文件后自动跑 AST 校验 + 测试，违反规范立即报错。

### 文件清单

| 文件 | 作用 |
|------|------|
| [.claude/settings.json](../.claude/settings.json) | Hook 配置（PostEdit/PreCommit） |
| [scripts/check.py](../scripts/check.py) | AST 校验脚本 |
| [scripts/check.sh](../scripts/check.sh) | 入口脚本 |

### Hook 配置

```json
{
  "hooks": {
    "PostEdit": [
      {
        "matcher": "**/*.py",
        "hooks": [{
          "type": "command",
          "command": "scripts/check.sh",
          "timeout": 60
        }]
      }
    ],
    "PreCommit": [...]
  }
}
```

- `PostEdit`：每次编辑 `.py` 文件后触发
- `PreCommit`：git commit 前触发

### AST 校验项（精确，无误报）

```python
# scripts/check.py 用 ast 模块解析，只看真正代码不看注释

class ForbiddenCallChecker(ast.NodeVisitor):
    """检查 db.commit() 等禁止调用"""
    def visit_Call(self, node):
        # 解析 a.b.c 链式调用
        ...

class DecoratorChecker(ast.NodeVisitor):
    """检查 @app.on_event 等弃用装饰器"""
    ...
```

### 校验规则

| 规则 | 错误信息 |
|------|---------|
| Repository 调 `db.commit()` | Repository 不应调用 db.commit()（事务由 Service 控制） |
| 用 `@on_event` | 检测到 @on_event，已弃用，请用 lifespan |
| 导入 passlib | 检测到 passlib 导入，请直接用 bcrypt |
| Service 缺 bcrypt | 缺少 'import bcrypt' |
| 业务代码 `print()` | 业务代码不能直接 print()，请用 logger |
| Python 语法错误 | 语法错误 |
| 测试失败 | 测试失败 |

### 为什么用 AST 而不是 grep

- grep 会匹配注释和 docstring 里的字样（误报）
- AST 只解析真正代码，精确无误
- 例如 `# 不应调用 db.commit()` 注释不会误报

### 实测验证

故意在 repository 写 `db.commit()`：
```
❌ /app/repository/user_repo.py:127 Repository 不应调用 db.commit()
```

注释里的 `db.commit()` 字样不会误报。

---

## 20. CLAUDE.md 协作规范

**职责**：指导 Claude Code 在本项目协作的规范文件。

### 内容结构

```markdown
# CLAUDE.md

## 项目概述
框架、数据库、密码、迁移、Python 版本

## 项目结构
完整目录树

## 关键设计约定
1. 四层架构依赖方向不可逆
2. 事务边界（Repository 不 commit）
3. 密码安全（不存明文，用 UserOut）
4. 配置管理（.env，不硬编码）
5. 异常处理（业务异常继承 Exception）

## 开发规范
- 代码风格（中文注释，import 顺序）
- 命名约定（UserCreate/UserOut/UserInDB）
- 提交信息格式（feat/fix/refactor/docs/test/chore）

## 常用命令
启动、测试、迁移、Docker

## 修改代码时检查清单
新增 API / 新增字段 / 新增业务异常 各自的检查项

## 禁止事项（7 条硬规则）
❌ Service 层 import HTTPException
❌ Repository 层 db.commit()
❌ UserInDB 作 response_model
❌ 密码明文进代码或日志
❌ 用 @app.on_event
❌ 用 passlib
❌ Python 3.9 用 X | None
❌ 业务代码直接 print()
```

### 每次会话开始时

Claude Code 会自动读取 CLAUDE.md，理解：
- 项目用什么架构
- 有什么禁忌
- 修改代码后要检查什么

---

## 21. docs/ 文档目录

**职责**：项目级文档，按主题分文件。

### 文档清单

| 文档 | 内容 |
|------|------|
| [docs/README.md](README.md) | 文档索引 |
| [docs/architecture.md](architecture.md) | 四层架构、依赖方向、事务边界设计 |
| [docs/api.md](api.md) | REST API 完整文档（含 curl 示例） |
| [docs/deployment.md](deployment.md) | 3 种部署方式 + CI/CD 流程 + 回滚 |
| [docs/database.md](database.md) | 表结构、Alembic 迁移指南、FAQ |
| [docs/security.md](security.md) | 密码/配置/SQL注入/传输/依赖安全 |
| [docs/troubleshooting.md](troubleshooting.md) | 21 个常见问题排查 |

### 文档分层

```
README.md          项目概览（5 分钟看完）
├── DETAIL.md      精细代码讲解（学习用）
├── CLAUDE.md      Claude 协作规范（AI 用）
└── docs/          按主题深入（运维/前端/安全各取所需）
    ├── architecture.md
    ├── api.md
    ├── deployment.md
    ├── database.md
    ├── security.md
    └── troubleshooting.md
```

### 谁看什么文档

| 角色 | 文档 |
|------|------|
| 新人入门 | README.md → DETAIL.md |
| 前端对接 | docs/api.md |
| 运维部署 | docs/deployment.md + docs/troubleshooting.md |
| DBA | docs/database.md |
| 安全审计 | docs/security.md |
| Claude Code | CLAUDE.md |

---

**学完这个项目你应该掌握**：
- ✅ FastAPI 四层架构组织
- ✅ Pydantic v2 数据校验（含泛型分页模型）
- ✅ SQLAlchemy 2.0 ORM 操作
- ✅ Alembic 数据库迁移
- ✅ bcrypt 密码哈希
- ✅ 环境变量管理配置
- ✅ FastAPI 依赖注入模式
- ✅ 全局异常处理
- ✅ 结构化日志
- ✅ 分页查询设计
- ✅ 健康检查接口
- ✅ TestClient 接口测试
- ✅ Docker 多阶段构建
- ✅ docker-compose 多服务编排
- ✅ GitHub Actions CI/CD
- ✅ Claude Code Hook 自动校验
- ✅ AST 静态分析
- ✅ 项目文档分层组织
