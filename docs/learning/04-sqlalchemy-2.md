# 04 - SQLAlchemy 2.0 ORM 完全指南
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 4 篇。本篇讲清楚 SQLAlchemy 2.0 的新写法、Session 机制、查询、flush vs commit、连接池。

## 你将学到

- SQLAlchemy 1.x vs 2.0 的关键差异
- `Mapped` / `mapped_column` 类型注解写法
- `Session` 的工作机制与生命周期
- `select` 语句 vs 老式 `Query`
- `flush` vs `commit` 的本质区别
- 连接池配置与调优
- 本项目 Repository 层的设计原理

---

## 1. SQLAlchemy 是什么

SQLAlchemy 是 Python 最流行的 ORM（对象关系映射）库，把数据库表映射成 Python 类。

### 1.1 核心组成

```
SQLAlchemy
   │
   ├── Core（底层）   SQL 表达式、连接池、类型系统
   │
   └── ORM（高层）    对象映射、关系、Session
```

### 1.2 ORM 的本质

```python
# 不用 ORM
cursor.execute("SELECT * FROM users WHERE id = %s", (1,))
row = cursor.fetchone()
user = User(id=row[0], name=row[1])

# 用 ORM
user = session.scalars(select(User).where(User.id == 1)).one()
```

ORM 让你用 Python 对象操作数据库，不用写 SQL。

### 1.3 为什么用 ORM

| 优势 | 说明 |
|------|------|
| 防 SQL 注入 | 自动参数化 |
| 跨数据库 | 改 URL 就能切 MySQL/PostgreSQL |
| 类型安全 | 字段类型注解 |
| 关系映射 | 一对多/多对多用 Python 表达 |
| 迁移工具 | 配合 Alembic |

---

## 2. SQLAlchemy 1.x vs 2.0

### 2.1 写法对比

**1.x 老写法**：

```python
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(20))

# 查询
user = session.query(User).filter(User.id == 1).first()
```

**2.0 新写法**：

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20))

# 查询
user = session.scalars(select(User).where(User.id == 1)).first()
```

### 2.2 关键变化

| 维度 | 1.x | 2.0 |
|------|-----|------|
| Base 类 | `declarative_base()` 函数 | `DeclarativeBase` 类继承 |
| 列定义 | `Column(...)` | `Mapped[X] = mapped_column(...)` |
| 查询 | `session.query(...).filter(...)` | `session.scalars(select(...).where(...))` |
| 类型推断 | 无 | 从 `Mapped[X]` 推断列类型 |
| 删除 | `Column(...)` | `mapped_column(...)`（别名） |

### 2.3 2.0 的优势

1. **类型注解驱动**：IDE 自动补全、mypy 检查
2. **更明确的 API**：`select` 函数式，可读性好
3. **统一同步/异步 API**：异步写法与同步几乎一致
4. **性能优化**：内部重写

---

## 3. `Mapped` 与 `mapped_column` 详解

### 3.1 `Mapped[X]` 是什么

```python
from sqlalchemy.orm import Mapped

class User(Base):
    id: Mapped[int]
```

`Mapped[X]` 是 SQLAlchemy 2.0 的**类型注解容器**，告诉 SQLAlchemy"这一列的类型是 X"。

### 3.2 `mapped_column(...)` 配置列

```python
from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer, String

class User(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
```

`mapped_column` 的参数：

| 参数 | 说明 |
|------|------|
| 第一个位置参数 | 列类型（Integer/String/...），可省略让 SQLAlchemy 从 `Mapped[X]` 推断 |
| `primary_key=True` | 主键 |
| `autoincrement=True` | 自增 |
| `unique=True` | 唯一索引 |
| `index=True` | 普通索引 |
| `nullable=False` | 不允许 NULL |
| `default=...` | Python 端默认值 |
| `server_default=...` | 数据库端默认值 |

### 3.3 类型推断

如果列类型能从 `Mapped[X]` 推断，可以省略 `mapped_column` 第一个参数：

```python
class User(Base):
    # 推断：Mapped[int] → Integer
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 推断：Mapped[str] → String（但长度默认 255，需要显式指定）
    username: Mapped[str] = mapped_column(String(20), unique=True)
```

### 3.4 `Optional` 与 `nullable`

```python
class User(Base):
    # NOT NULL
    username: Mapped[str] = mapped_column(nullable=False)

    # 可空（NULL allowed）
    email: Mapped[Optional[str]] = mapped_column(nullable=True)
    # 或
    email: Mapped[str | None] = mapped_column(nullable=True)
```

`Mapped[Optional[str]]` 在 SQLAlchemy 里等价于 `nullable=True`。

### 3.5 默认值

```python
from sqlalchemy import func

class User(Base):
    # Python 端默认值（INSERT 时 Python 填充）
    is_active: Mapped[bool] = mapped_column(default=True)

    # 数据库端默认值（DDL 带 DEFAULT）
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp()
    )

    # 更新时自动刷新
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
```

**`default` vs `server_default`**：

| 写法 | 谁填默认值 | DDL 带 DEFAULT | 优势 |
|------|-----------|---------------|------|
| `default=True` | Python | 不带 | 跨数据库一致 |
| `server_default=...` | 数据库 | 带 | 不依赖 Python |

本项目用 `server_default` 让 MySQL 填时间戳，DDL 自带 `DEFAULT CURRENT_TIMESTAMP`。

---

## 4. `DeclarativeBase` 与元数据

### 4.1 定义 Base

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

所有 ORM 模型继承这个 `Base`。`Base.metadata` 自动收集所有表结构。

### 4.2 `metadata` 的作用

```python
# 所有继承 Base 的模型都注册到 metadata
class User(Base): ...
class Order(Base): ...

print(Base.metadata.tables)
# {'users': Table(...), 'orders': Table(...)}

# 用 metadata 建表（一次性建所有表）
Base.metadata.create_all(bind=engine)
```

### 4.3 本项目的 Base

```python
# app/db.py
class Base(DeclarativeBase):
    pass
```

```python
# main.py 启动时
Base.metadata.create_all(bind=engine)
```

启动时自动建表（只建不存在的表，不修改已有表）。

---

## 5. `Session` 详解

### 5.1 Session 是什么

Session 是 ORM 与数据库之间的**会话**，所有操作都通过它执行。

```
Python 对象 ←→ Session ←→ Connection ←→ 数据库
                ↑
              缓存改动，提交时才真正写库
```

### 5.2 创建 Session

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 用法
db = SessionLocal()
try:
    db.add(some_user)
    db.commit()
finally:
    db.close()
```

`sessionmaker` 是 Session 工厂，调用它生成 Session。

### 5.3 `autocommit` 与 `autoflush`

| 参数 | 默认 | 说明 |
|------|------|------|
| `autocommit=False` | 推荐 | 不自动提交，手动 `db.commit()` |
| `autoflush=False` | 推荐 | 不自动 flush，避免意外 SQL |

**`autoflush=True` 的坑**：每次查询前自动 flush，可能在你不知情时执行 INSERT/UPDATE。

### 5.4 Session 生命周期

```python
def get_db():
    db = SessionLocal()  # 1. 创建 Session
    try:
        yield db         # 2. 注入路由
    finally:
        db.close()       # 3. 关闭（归还连接池）
```

**关键原则**：每个请求独立 Session，请求结束关闭。

### 5.5 本项目的 `get_db`

```python
# app/db.py
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

FastAPI 依赖注入，每个请求自动创建/关闭 Session。

---

## 6. 查询：`select` 语句

### 6.1 基础查询

```python
from sqlalchemy import select

# 查询所有
users = db.scalars(select(User)).all()

# 按 id 查询
user = db.scalars(select(User).where(User.id == 1)).one_or_none()

# 按条件查询
users = db.scalars(
    select(User).where(User.username == "alice")
).all()
```

### 6.2 `scalars` vs `execute`

```python
# execute 返回 Row 对象（即使只查一列）
result = db.execute(select(User))
for row in result:
    print(row)  # Row(User(id=1, ...))

# scalars 返回标量（直接是 User 对象）
users = db.scalars(select(User)).all()
for user in users:
    print(user)  # User(id=1, ...)
```

**`scalars` 提取第一列**，适合查整个模型。如果查多列还是用 `execute`。

### 6.3 `one` / `one_or_none` / `all` / `first`

| 方法 | 找到 0 条 | 找到 1 条 | 找到多条 |
|------|----------|----------|---------|
| `.one()` | 抛异常 | 返回 | 抛异常 |
| `.one_or_none()` | None | 返回 | 抛异常 |
| `.first()` | None | 返回 | 返回第一条 |
| `.all()` | `[]` | `[obj]` | 全部 list |

**最佳实践**：
- 按主键查：`.one_or_none()`
- 按唯一字段查：`.one_or_none()`
- 列表查询：`.all()`
- 不确定是否多条：`.first()`

### 6.4 排序、分页

```python
# 排序
users = db.scalars(
    select(User).order_by(User.created_at.desc())
).all()

# 分页
users = db.scalars(
    select(User).offset(0).limit(20)
).all()
```

### 6.5 聚合查询

```python
from sqlalchemy import func

# 计数
total = db.scalar(select(func.count()).select_from(User))
# 或
total = db.scalar(select(func.count(User.id)))

# 最大值
max_id = db.scalar(select(func.max(User.id)))

# 求和
total_age = db.scalar(select(func.sum(User.age)))
```

`db.scalar` 返回单个值（不是对象）。

### 6.6 本项目的查询

```python
# repository/user_repo.py
def get(self, user_id: int) -> Optional[UserInDB]:
    user = self._db.scalars(
        select(User).where(User.id == user_id)
    ).one_or_none()
    return self._to_schema(user) if user else None

def list_all(self, skip: int = 0, limit: int = 20):
    users = self._db.scalars(
        select(User).offset(skip).limit(limit)
    ).all()
    return [self._to_schema(u) for u in users]

def count(self) -> int:
    return self._db.scalar(select(func.count()).select_from(User)) or 0
```

---

## 7. `flush` vs `commit`：本项目的核心设计

### 7.1 两者区别

| 操作 | flush | commit |
|------|-------|--------|
| 触发 SQL | ✅ INSERT/UPDATE/DELETE 发到数据库 | ✅ 同 flush |
| 提交事务 | ❌ 不提交，可回滚 | ✅ 提交事务，持久化 |
| 释放锁 | ❌ 不释放 | ✅ 释放 |
| 自动生成 id | ✅ 立即可用 | ✅ |
| 失败可回滚 | ✅ 可 rollback | ❌ 已提交无法回滚 |

### 7.2 工作流程对比

```
add(obj) → flush() → commit()
              ↓          ↓
          发 SQL      提交事务
          分配 id     持久化
          可回滚      不可逆
```

### 7.3 本项目的事务设计

**Repository 层（不 commit）**：

```python
def add(self, username: str, hashed_password: str) -> UserInDB:
    user = User(username=username, hashed_password=hashed_password)
    self._db.add(user)
    self._db.flush()  # 触发 INSERT，分配 id，但不提交
    return self._to_schema(user)
```

**Service 层（控制事务）**：

```python
def create_user(self, payload: UserCreate) -> UserOut:
    try:
        user = self._repo.add(...)
        self._commit()  # 提交事务
    except IntegrityError:
        self._repo._db.rollback()  # 回滚
        raise UserAlreadyExistsError(...)
```

### 7.4 为什么这么设计

考虑转账场景：

```python
def transfer(self, from_id, to_id, amount):
    try:
        self._repo.debit(from_id, amount)   # flush
        self._repo.credit(to_id, amount)    # flush
        self._commit()  # 一起提交
    except Exception:
        self._repo._db.rollback()  # 一起回滚
        raise
```

如果 Repository 各自 `commit`：
- 第一个 commit 成功
- 第二个失败
- **钱丢了**（已提交无法回滚）

Repository 不 commit，Service 控制事务边界，多个操作才能组合为原子事务。

### 7.5 `_commit` 辅助方法

```python
def _commit(self) -> None:
    try:
        self._repo._db.commit()
    except Exception:
        self._repo._db.rollback()
        raise
```

集中处理 commit，统一加日志或监控。

---

## 8. 写操作：增删改

### 8.1 新增（add）

```python
def add(self, username, hashed_password):
    user = User(username=username, hashed_password=hashed_password)
    self._db.add(user)    # 加入 Session
    self._db.flush()      # 触发 INSERT，分配 id
    return self._to_schema(user)
```

执行流程：
1. `User(...)` 创建 Python 对象
2. `db.add(user)` 把对象加入 Session（不发 SQL）
3. `db.flush()` 发 INSERT，MySQL 返回自增 id
4. `user.id` 现在有值了

### 8.2 更新

```python
def update(self, user_id, username=None, hashed_password=None):
    user = self._db.scalars(
        select(User).where(User.id == user_id)
    ).one_or_none()
    if user is None:
        return None

    if username is not None:
        user.username = username  # 直接改属性
    if hashed_password is not None:
        user.hashed_password = hashed_password

    self._db.flush()  # 触发 UPDATE
    return self._to_schema(user)
```

**ORM 更新方式**：先查出对象，改属性，flush 自动生成 UPDATE。

### 8.3 删除

```python
def delete(self, user_id: int) -> bool:
    user = self._db.scalars(
        select(User).where(User.id == user_id)
    ).one_or_none()
    if user is None:
        return False
    self._db.delete(user)  # 标记删除
    self._db.flush()       # 触发 DELETE
    return True
```

`db.delete(obj)` 标记对象为待删除，flush 时发 DELETE SQL。

---

## 9. 连接池

### 9.1 引擎配置

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,    # 借出前 ping
    pool_recycle=3600,     # 每小时回收
    pool_size=5,           # 连接池大小
    max_overflow=10,       # 突发额外连接
    echo=False,            # 打印 SQL（调试用）
)
```

### 9.2 参数详解

| 参数 | 默认 | 推荐生产 | 说明 |
|------|------|---------|------|
| `pool_size` | 5 | 10-20 | 连接池常驻连接数 |
| `max_overflow` | 10 | 20 | 突发时额外连接 |
| `pool_pre_ping` | False | True | 借出前 ping，避免失效连接 |
| `pool_recycle` | -1 | 3600 | 连接最大存活秒数 |
| `pool_timeout` | 30 | 30 | 等连接的超时秒数 |
| `echo` | False | False | 打印所有 SQL |

### 9.3 为什么 `pool_pre_ping=True`

MySQL 默认 `wait_timeout=28800`（8 小时），空闲连接 8 小时被 MySQL 关闭。如果连接池里这个失效连接被借出，会报 `MySQL server has gone away`。

`pool_pre_ping=True` 让 SQLAlchemy 借出前发 `SELECT 1` 检查连接，失效的丢弃，拿新的。

### 9.4 为什么 `pool_recycle=3600`

即使 `pool_pre_ping=True`，也建议每小时回收连接：
- 防止长期持有连接导致资源泄漏
- MySQL 端连接不会无限增长内存
- 网络中间件（如 RDS 代理）的连接超时

`pool_recycle` 设置小于 MySQL 的 `wait_timeout` 即可。

### 9.5 连接池工作流程

```
db = SessionLocal()
  ↓
Session 从 engine 借连接
  ↓
[pool_pre_ping] SELECT 1 检查
  ↓
失效？丢弃，拿新连接
  ↓
执行业务 SQL
  ↓
db.close() → 归还连接到池
  ↓
（不真正关闭，留给下次请求复用）
```

---

## 10. 关系映射（扩展知识）

本项目只有单表，但 SQLAlchemy 支持复杂关系：

### 10.1 一对多

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    posts: Mapped[List["Post"]] = relationship(back_populates="user")

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="posts")
```

### 10.2 查询关系

```python
user = db.scalars(select(User).where(User.id == 1)).one()
print(user.posts)  # 自动查 posts 表

# 预加载避免 N+1
from sqlalchemy.orm import selectinload
user = db.scalars(
    select(User).options(selectinload(User.posts)).where(User.id == 1)
).one()
```

---

## 11. 异常处理

### 11.1 常见异常

```python
from sqlalchemy.exc import IntegrityError, NoResultFound, MultipleResultsFound

# 唯一约束冲突
try:
    db.add(User(username="existing"))
    db.flush()
except IntegrityError as e:
    db.rollback()
    # 处理冲突

# .one() 找不到
try:
    user = db.scalars(select(User).where(User.id == 999)).one()
except NoResultFound:
    pass

# .one() 找到多条
try:
    user = db.scalars(select(User).where(User.username == "alice")).one()
except MultipleResultsFound:
    pass
```

### 11.2 本项目的用法

```python
# service/user_service.py
try:
    user = self._repo.add(username=payload.username, hashed_password=hashed)
    self._commit()
except IntegrityError:
    # 并发场景：两个请求同时通过前置检查，DB unique 约束兜底
    self._repo._db.rollback()
    raise UserAlreadyExistsError(...)
```

`IntegrityError` 是 SQLAlchemy 的数据库完整性错误，UNIQUE 约束冲突会抛这个。

---

## 12. 同步 vs 异步

### 12.1 同步引擎

```python
from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://...")
```

用 PyMySQL / mysqlclient 驱动，阻塞 I/O。

### 12.2 异步引擎

```python
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("mysql+aiomysql://...")
```

用 `aiomysql` / `asyncpg` 驱动，异步 I/O。

### 12.3 本项目为什么用同步

- SQLAlchemy 同步 API 更简单
- FastAPI 自动把同步路由放线程池，不阻塞事件循环
- PyMySQL 兼容 MySQL 9.x 的 `caching_sha2_password`，异步驱动兼容性差

性能要求高时可以换异步，但要注意：异步代码会"传染"（一旦 async，全链路都得 async）。

---

## 13. 自测题

### Q1：`db.flush()` 和 `db.commit()` 的区别？

<details>
<summary>查看答案</summary>

- `flush`：发 SQL 但不提交事务，可回滚
- `commit`：发 SQL 并提交事务，不可逆

`flush` 后 `rollback` 能撤销，`commit` 后不行。
</details>

### Q2：为什么本项目 Repository 不调 `commit`？

<details>
<summary>查看答案</summary>

让 Service 层控制事务边界，多个 Repository 操作可组合为一个事务（如转账场景：扣钱 + 加钱必须同时成功或失败）。
</details>

### Q3：`scalars(stmt).one_or_none()` 和 `execute(stmt).first()` 区别？

<details>
<summary>查看答案</summary>

- `scalars` 返回标量（直接是 User 对象）
- `execute` 返回 Row 对象（需要 `row[0]` 取）
- `.one_or_none()` 找到多条抛异常，`.first()` 返回第一条
</details>

### Q4：`pool_pre_ping=True` 解决什么问题？

<details>
<summary>查看答案</summary>

解决连接池里的失效连接问题。MySQL 空闲连接超时被关闭，借出前 ping 一下能避免 `MySQL server has gone away` 错误。
</details>

---

## 14. 小结

| 概念 | 关键点 |
|------|--------|
| `DeclarativeBase` | 2.0 Base 类 |
| `Mapped[X]` | 类型注解容器 |
| `mapped_column(...)` | 列配置 |
| `select(stmt).where(...)` | 2.0 查询写法 |
| `db.scalars(stmt).one_or_none()` | 查询单条 |
| `db.flush()` | 发 SQL 不提交 |
| `db.commit()` | 提交事务 |
| `pool_pre_ping=True` | 借出前 ping |
| `pool_recycle=3600` | 每小时回收连接 |
| `IntegrityError` | 唯一约束冲突 |

## 15. 下篇预告

下一篇讲 **Alembic 数据库迁移原理与实践**：autogenerate 原理、版本图、stamp、downgrade、生产迁移策略。

---

**延伸阅读**：
- [SQLAlchemy 2.0 官方文档](https://docs.sqlalchemy.org/en/20/)
- [SQLAlchemy 2.0 教程](https://docs.sqlalchemy.org/en/20/tutorial/)
- [SQLAlchemy 1.x → 2.0 迁移指南](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
