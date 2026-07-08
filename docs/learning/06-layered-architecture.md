# 06 - 四层架构设计原理
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 6 篇。本篇讲清楚为什么要分层、依赖方向、Repository 模式、DTO 转换、本项目的架构决策。

## 你将学到

- 为什么要分层架构
- 四层架构各层职责
- 依赖方向为什么不可逆
- Repository 模式
- DTO（数据传输对象）转换
- 解耦的代价与收益

---

## 1. 为什么要分层

### 1.1 不分层的代码长什么样

```python
# 所有逻辑堆在路由里
@app.post("/users")
def create_user(payload: dict):
    # 校验
    if not payload.get("username") or len(payload["username"]) < 3:
        return {"error": "用户名至少 3 位"}, 400

    # 数据库连接
    conn = pymysql.connect(host="localhost", user="root", password="xxx")
    cursor = conn.cursor()

    # 查重
    cursor.execute("SELECT * FROM users WHERE username = %s", payload["username"])
    if cursor.fetchone():
        return {"error": "用户名已存在"}, 409

    # 密码哈希
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(payload["password"].encode(), salt)

    # 插入
    cursor.execute(
        "INSERT INTO users (username, hashed_password) VALUES (%s, %s)",
        (payload["username"], hashed)
    )
    conn.commit()

    # 返回
    return {"id": cursor.lastrowid, "username": payload["username"]}
```

### 1.2 问题

1. **路由函数太长**：校验、DB、哈希、返回全混在一起
2. **无法复用**：登录也要查用户，得重复写 DB 代码
3. **无法测试**：想测密码哈希逻辑，必须连数据库
4. **改一处影响多处**：换数据库要改所有路由
5. **SQL 注入风险**：手动拼 SQL 容易出问题

### 1.3 分层的目的

**单一职责**：每层只做一件事
**依赖方向**：上层依赖下层，下层不知道上层
**可替换**：换实现只改一层

---

## 2. 四层架构总览

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
│ Service 层 (app/service/)— 业务规则     │  ← 业务逻辑 + 事务
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Repository 层 (app/repository/)— ORM    │  ← 数据访问
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ ORM 模型 (app/models/)                  │  ← 表结构
└─────────────────────────────────────────┘
```

### 2.1 各层职责

| 层 | 职责 | 不做的事 |
|----|------|---------|
| API | HTTP 路由、参数解析、异常映射 | 业务逻辑、数据库操作 |
| Schema | 数据校验、序列化 | 业务逻辑、数据库操作 |
| Service | 业务规则、事务控制、密码哈希 | HTTP 概念、SQL |
| Repository | ORM CRUD | 业务规则、commit |
| Models | 表结构定义 | 业务逻辑 |

### 2.2 依赖方向（严格不可逆）

```
API → Schema
API → Service → Repository → ORM
Service → Schema
Repository → Schema (仅 UserInDB)
```

**禁止的依赖**：
- Service ❌ → FastAPI HTTP 概念（除 Depends）
- Repository ❌ → `db.commit()`
- Schema ❌ → 任何其他层

---

## 3. API 层详解

### 3.1 职责

- 接收 HTTP 请求
- 用 Pydantic 校验请求体
- 调用 Service
- 把业务异常映射为 HTTP 响应
- 用 `response_model` 序列化响应

### 3.2 本项目示例

```python
# app/api/users.py
@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,  # Pydantic 自动校验
    svc: UserService = Depends(get_user_service),  # 依赖注入
):
    return svc.create_user(payload)  # 业务异常由全局处理器处理
```

### 3.3 API 层不该做什么

```python
# ❌ 业务逻辑写在 API 层
@router.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, "用户名已存在")
    hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt())
    user = User(username=payload.username, hashed_password=hashed)
    db.add(user)
    db.commit()
    return user

# ✅ 业务逻辑放 Service
@router.post("/users")
def create_user(payload: UserCreate, svc=Depends(get_user_service)):
    return svc.create_user(payload)
```

### 3.4 异常映射

API 层负责把业务异常翻译成 HTTP：

```python
# 全局处理器（app/exception_handlers.py）
@app.exception_handler(UserNotFoundError)
async def handle(_, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

**好处**：路由函数不用 try/except，业务异常直接抛。

---

## 4. Schema 层详解

### 4.1 职责

- 定义请求体模型（用户传什么）
- 定义响应体模型（返回什么）
- 自动校验数据
- 自动生成 Swagger 文档

### 4.2 本项目的 Schema 继承体系

```python
# app/schema/user.py
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")

class UserCreate(UserBase):  # 请求体
    password: str = Field(..., min_length=6, max_length=64)

class UserUpdate(BaseModel):  # 请求体（字段全可选）
    username: Optional[str] = None
    password: Optional[str] = None

class UserOut(UserBase):  # 响应体（不含密码）
    id: int

class UserInDB(UserOut):  # 内部传输（含哈希密码）
    hashed_password: str
```

### 4.3 为什么有这么多模型

考虑创建用户：
- 用户传 `password`（明文）
- 数据库存 `hashed_password`（哈希）
- 返回给前端只有 `id` + `username`

如果只用一个模型：

```python
class User(BaseModel):
    id: int
    username: str
    password: str  # 创建时需要
    hashed_password: str  # 数据库存这个
```

问题：
- 创建时 `id` 哪来？
- 返回前端时怎么隐藏 `password` / `hashed_password`？

拆成多个模型，每个场景一个，**单一职责**。

### 4.4 Schema 不依赖任何层

Schema 层不 import Service / Repository / Models，纯数据定义。这样 Schema 可以被任何层引用，不引入额外依赖。

---

## 5. Service 层详解

### 5.1 职责

- 业务规则校验（用户名唯一等）
- 密码哈希
- 事务控制（commit / rollback）
- DTO 转换（`UserInDB` → `UserOut`）

### 5.2 本项目示例

```python
# app/service/user_service.py
class UserService:
    def __init__(self, repo: UserRepo):
        self._repo = repo

    def create_user(self, payload: UserCreate) -> UserOut:
        # 1. 业务规则：用户名唯一
        if self._repo.get_by_username(payload.username):
            raise UserAlreadyExistsError(...)

        # 2. 密码哈希
        hashed = hash_password(payload.password)

        # 3. 调用 Repository
        try:
            user = self._repo.add(payload.username, hashed)
            self._commit()  # 4. 事务控制
        except IntegrityError:
            self._repo._db.rollback()
            raise UserAlreadyExistsError(...)

        return UserOut.model_validate(user)  # 5. DTO 转换
```

### 5.3 Service 不依赖 HTTP

**关键原则**：Service 层不知道 HTTP 的存在。

```python
# ❌ 错误：Service 抛 HTTPException
from fastapi import HTTPException
class UserService:
    def create_user(self, payload):
        if self._repo.get_by_username(payload.username):
            raise HTTPException(409, "用户名已存在")  # 业务层不该知道 HTTP
```

```python
# ✅ 正确：Service 抛业务异常
class UserAlreadyExistsError(Exception): ...

class UserService:
    def create_user(self, payload):
        if self._repo.get_by_username(payload.username):
            raise UserAlreadyExistsError(...)  # 业务异常
```

**为什么**：Service 可能被 CLI 工具、定时任务、其他 Service 调用，不应该绑定 HTTP。

### 5.4 事务控制

Service 控制 commit/rollback：

```python
def _commit(self):
    try:
        self._repo._db.commit()
    except Exception:
        self._repo._db.rollback()
        raise
```

为什么不在 Repository 控制？因为多个 Repository 操作可能要组合为一个事务（如转账场景）。

---

## 6. Repository 层详解

### 6.1 职责

- ORM CRUD 操作
- ORM 对象 ↔ Schema 模型转换
- **不 commit**（由 Service 控制）

### 6.2 本项目示例

```python
# app/repository/user_repo.py
class UserRepo:
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _to_schema(user: User) -> UserInDB:
        """ORM → Schema 转换，隔离 ORM 与上层"""
        return UserInDB(
            id=user.id,
            username=user.username,
            hashed_password=user.hashed_password,
        )

    def add(self, username: str, hashed_password: str) -> UserInDB:
        user = User(username=username, hashed_password=hashed_password)
        self._db.add(user)
        self._db.flush()  # 触发 SQL 但不提交
        return self._to_schema(user)
```

### 6.3 Repository 模式

**Repository 模式**：把数据访问抽象成"集合"。

```python
# 不用 Repository
users = db.query(User).filter(User.username == "alice").first()

# 用 Repository
user = user_repo.get_by_username("alice")
```

**好处**：
- 上层不接触 ORM，换 ORM 只改 Repository
- 易于测试（mock Repository）
- 业务逻辑与数据访问解耦

### 6.4 为什么不 commit

```python
# ❌ Repository 自己 commit
def add(self, ...):
    user = User(...)
    self._db.add(user)
    self._db.commit()  # 提交了，无法组合事务
```

考虑转账：

```python
def transfer(self, from_id, to_id, amount):
    self._repo.debit(from_id, amount)   # commit 了
    self._repo.credit(to_id, amount)    # 失败
    # 第一个已提交，第二个失败 → 钱丢了！
```

正确做法：

```python
# Repository 不 commit，只 flush
def add(self, ...):
    user = User(...)
    self._db.add(user)
    self._db.flush()  # 发 SQL 但不提交

# Service 控制事务
def transfer(self, from_id, to_id, amount):
    try:
        self._repo.debit(from_id, amount)
        self._repo.credit(to_id, amount)
        self._commit()  # 一起提交
    except Exception:
        self._repo._db.rollback()  # 一起回滚
        raise
```

### 6.5 ORM ↔ Schema 转换

Repository 对外只暴露 Schema（`UserInDB`），不暴露 ORM（`User`）：

```python
# Repository 内部
def get(self, user_id):
    user = self._db.scalars(select(User).where(...)).one_or_none()
    return self._to_schema(user) if user else None
    #              ↑ ORM User → Schema UserInDB
```

**为什么**：
- 上层不需要知道 ORM 长什么样
- 换 ORM（如 MongoDB）只改 Repository
- ORM 的副作用（懒加载、session 状态）不会泄漏到上层

---

## 7. ORM 模型层详解

### 7.1 职责

- 定义表结构
- 用 `Mapped` / `mapped_column` 描述列
- 不含业务逻辑

### 7.2 本项目示例

```python
# app/models/user.py
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.current_timestamp())
```

### 7.3 ORM 模型 vs Schema 模型

| 维度 | ORM 模型 (User) | Schema 模型 (UserInDB) |
|------|----------------|----------------------|
| 库 | SQLAlchemy | Pydantic |
| 用途 | 映射数据库表 | 层间数据传输 |
| 方法 | db.add(), db.commit() | model_validate(), model_dump() |
| 字段 | 含数据库列属性 | 纯数据 |

两者字段几乎一样，但**用途不同**，所以要分开。

---

## 8. DTO 转换详解

### 8.1 DTO 是什么

DTO = Data Transfer Object，层间传输的数据对象。

本项目的 DTO 流转：

```
请求体 (UserCreate)
    ↓ API 层
Service 接收 (UserCreate)
    ↓ Service 哈希密码
Repository 接收 (username, hashed_password)
    ↓ Repository 创建
ORM User
    ↓ Repository 转换
UserInDB (含哈希密码)
    ↓ Service 转换
UserOut (不含哈希密码)
    ↓ API 层
响应 JSON
```

### 8.2 为什么这么多转换

**安全**：`UserOut` 不含 `hashed_password`，即使 Service 误返回 `UserInDB`，API 层用 `response_model=UserOut` 自动过滤。

**解耦**：每层用自己最舒服的数据格式，互不干扰。

**类型安全**：每层都有明确类型，IDE 自动补全。

### 8.3 转换代码

```python
# ORM → UserInDB（Repository 层）
@staticmethod
def _to_schema(user: User) -> UserInDB:
    return UserInDB(
        id=user.id,
        username=user.username,
        hashed_password=user.hashed_password,
    )

# UserInDB → UserOut（Service 层）
return UserOut.model_validate(user_in_db)
```

`model_validate` 自动取同名字段，丢弃多余字段（如 `hashed_password`）。

---

## 9. 依赖注入

### 9.1 依赖链

```
请求 → get_db() → db
       ↓
       get_user_service(db) → UserService(UserRepo(db))
       ↓
       路由函数 → svc.create_user(payload)
```

### 9.2 本项目实现

```python
# app/db.py
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# app/service/user_service.py
def get_user_service(db=Depends(get_db)) -> UserService:
    return UserService.from_db(db)

# app/api/users.py
@router.post("")
def create_user(
    payload: UserCreate,
    svc: UserService = Depends(get_user_service),
):
    return svc.create_user(payload)
```

### 9.3 好处

- **每请求独立**：db session、Service 实例都是请求级
- **自动清理**：请求结束 `get_db` 的 finally 自动关闭 session
- **可测试**：测试时替换依赖：

```python
app.dependency_overrides[get_db] = get_test_db
```

---

## 10. 解耦的代价

### 10.1 代价

**代码量增加**：每个模型要定义多次（ORM、Schema、Repository 转换）

**层次多了**：简单功能要改多个文件

**学习成本**：新人需要理解架构

### 10.2 收益

| 维度 | 不分层 | 分层 |
|------|--------|------|
| 代码量 | 少 | 多（样板代码） |
| 可读性 | 简单功能好，复杂功能差 | 一致 |
| 可测试 | 难 | 易（mock） |
| 可复用 | 差 | 好 |
| 可维护 | 差（牵一发动全身） | 好（改一层不影响其他） |
| 可扩展 | 差 | 好（加缓存、加日志不侵入业务） |

### 10.3 什么时候该分层

| 场景 | 建议 |
|------|------|
| Demo / 脚本 | 不分层，简单优先 |
| 小项目（<10 接口） | 简单分层（API + Service + DB） |
| 中大项目（10+ 接口） | 完整分层（本项目架构） |
| 微服务 | 完整分层 + 领域驱动设计 |

**本项目架构适合中大型项目**，Demo 项目可以简化。

---

## 11. 扩展：六边形架构 / DDD

四层架构的进阶是**六边形架构（端口适配器）**和**领域驱动设计（DDD）**：

```
领域核心（业务逻辑，不依赖任何外部）
    ↓
端口（接口定义）
    ↓
适配器（实现端口，连数据库/HTTP/消息队列）
```

- 领域核心完全不知道数据库存在
- 换数据库只换适配器

本项目简化版：Service 层近似领域核心，Repository 是适配器。生产级 DDD 项目会进一步拆分：

```
app/
├── domain/         # 领域模型 + 业务规则
├── application/    # 用例（类似 Service）
├── infrastructure/ # 适配器（Repository 实现、外部 API）
└── interfaces/     # 接口（API、CLI）
```

---

## 12. 自测题

### Q1：Service 层为什么不能 import `HTTPException`？

<details>
<summary>查看答案</summary>

Service 层应该与 HTTP 解耦，可以被 CLI、定时任务、其他 Service 复用。如果绑定了 HTTP 概念，复用性下降。Service 抛业务异常，API 层负责翻译为 HTTP。
</details>

### Q2：Repository 层为什么不调 `db.commit()`？

<details>
<summary>查看答案</summary>

让 Service 层控制事务边界，多个 Repository 操作可组合为一个事务（如转账场景）。
</details>

### Q3：为什么 ORM `User` 和 Schema `UserInDB` 字段几乎一样，还要分两个类？

<details>
<summary>查看答案</summary>

用途不同：
- ORM `User`：映射数据库表，有 `db.add()` 等方法
- Schema `UserInDB`：层间数据传输，纯数据

分开后换 ORM（如 MongoDB）只改 ORM 模型，Schema 不变；换 API 框架只改 Schema，ORM 不变。
</details>

---

## 13. 小结

| 层 | 职责 | 关键约束 |
|----|------|---------|
| API | HTTP 路由、异常映射 | 不写业务逻辑 |
| Schema | 数据校验、序列化 | 不依赖其他层 |
| Service | 业务规则、事务控制 | 不依赖 HTTP 概念 |
| Repository | ORM CRUD | 不 commit |
| Models | 表结构定义 | 不含业务逻辑 |

**核心原则**：
- ✅ 依赖方向不可逆（API → Service → Repository → ORM）
- ✅ Service 抛业务异常，API 翻译为 HTTP
- ✅ Repository 不 commit，Service 控制事务
- ✅ Repository 对外暴露 Schema，不暴露 ORM
- ✅ 每层单一职责

## 14. 下篇预告

下一篇讲 **密码安全与事务边界**：bcrypt 原理、salt、工作因子、ACID、事务传播、本项目的安全设计。

---

**延伸阅读**：
- [Layered Architecture](https://www.oreilly.com/library/view/software-architecture-patterns/9781491971437/ch01.html)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Domain-Driven Design](https://www.domainlanguage.com/ddd/)
