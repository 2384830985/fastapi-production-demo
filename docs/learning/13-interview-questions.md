# 13 - 面试题集（30 题）
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 13 篇（附录 C）。本篇收录 30 道覆盖项目所有知识点的面试题，按主题分组，每题附详细答案。

## 你将学到

- 项目所有知识点的面试常考形式
- 标准答案 + 加分回答
- 易踩的坑

---

## 📋 题目分布

| 主题 | 题数 |
|------|------|
| Python 基础 | 5 |
| FastAPI | 6 |
| Pydantic | 3 |
| SQLAlchemy | 4 |
| Alembic | 2 |
| 架构设计 | 4 |
| 安全 | 3 |
| 部署 | 3 |

---

## 一、Python 基础

### Q1：`from __future__ import annotations` 是干什么的？

**答**：启用 PEP 563 延迟注解求值。所有类型注解在定义时不求值，存成字符串，需要时用 `typing.get_type_hints()` 解析。

**好处**：
- 解决前向引用问题（类方法返回自身类型）
- 避免循环 import
- 在 Python 3.9 上能用部分 3.10+ 语法

**示例**：
```python
from __future__ import annotations

class Node:
    def next(self) -> Node:  # 不报错，Node 已定义
        ...
```

**加分**：注解存字符串后，Pydantic / SQLAlchemy 用 `get_type_hints()` 解析。

---

### Q2：`Optional[X]` 和 `X | None` 区别？

**答**：完全等价，都表示"X 或 None"。

- `Optional[X]`：Python 3.5+，`typing` 模块
- `X | None`：Python 3.10+ 原生语法（PEP 604）

**选哪个**：
- Python 3.10+：用 `X | None`（更简洁）
- Python 3.9 + Pydantic v2：用 `Optional[X]`（兼容性好，Pydantic 在 3.9 上解析 `X | None` 有 bug）

**加分**：`Optional[X]` 本质是 `Union[X, None]` 的别名。

---

### Q3：`TypeVar` 和 `Generic` 是干什么的？

**答**：实现泛型类，让一个类能装不同类型的数据。

```python
from typing import TypeVar, Generic, List

T = TypeVar("T")

class Page(Generic[T]):
    items: List[T]
```

`Page[UserOut]` 表示"装 UserOut 的分页"，`Page[OrderOut]` 表示"装 OrderOut 的分页"，复用同一份代码。

**加分**：FastAPI 的 `response_model=Page[UserOut]` 让 Swagger 自动生成正确结构。

---

### Q4：Python 类型注解在运行时强制校验吗？

**答**：**不强制**。类型注解只是 hint，运行时不校验。

```python
x: int = "hello"  # 运行时不报错
```

需要校验要用：
- `mypy` / `pyright`：静态检查
- `Pydantic`：运行时校验（把注解变成校验规则）
- `dataclasses`：不校验，但能用 `__post_init__` 自定义

---

### Q5：`yield` 生成器 vs `return` 的区别？

**答**：
- `return`：返回值，函数结束
- `yield`：返回值，函数暂停，下次调用从 yield 后继续

```python
def gen():
    yield 1
    yield 2
    yield 3

g = gen()
next(g)  # 1
next(g)  # 2
```

**FastAPI 依赖用 yield**：
```python
def get_db():
    db = SessionLocal()
    try:
        yield db  # 注入路由
    finally:
        db.close()  # 路由结束后执行
```

---

## 二、FastAPI

### Q6：FastAPI 为什么比 Flask 快？

**答**：
1. **ASGI 异步**：I/O 等待时让出 CPU，一个 worker 处理多请求
2. **Pydantic v2 Rust 核心**：校验快 5-50 倍
3. **Starlette 优化**：高性能 ASGI 框架

**对比**：
- Flask (WSGI)：一个请求占一个 worker，等数据库时 worker 空闲
- FastAPI (ASGI)：等数据库时让出 CPU 给其他请求

---

### Q7：`Depends` 依赖注入怎么工作？

**答**：FastAPI 在调用路由前，先调用 `Depends` 包装的函数，把返回值作为参数传入。

```python
@router.get("")
def list_users(db: Session = Depends(get_db)):
    ...
```

执行流程：
1. 请求进来
2. FastAPI 调 `get_db()` 拿到 db
3. 把 db 作为参数传给 `list_users`
4. 路由执行
5. 如果 `get_db` 用 `yield`，执行 `yield` 之后的清理代码

**嵌套依赖**：`get_user_service` 依赖 `get_db`，FastAPI 按顺序解析。

---

### Q8：`lifespan` vs `on_event` 区别？

**答**：
- `@app.on_event("startup")`：**已弃用**，FastAPI 0.93+ 不推荐
- `lifespan`：**推荐写法**，用 `asynccontextmanager`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    Base.metadata.create_all(engine)
    yield
    # shutdown
    engine.dispose()

app = FastAPI(lifespan=lifespan)
```

**优势**：
- 集中管理 startup/shutdown
- 共享状态方便
- 原生异步支持

---

### Q9：路由匹配顺序有什么坑？

**答**：FastAPI 按注册顺序匹配，**静态路径在前，动态路径在后**。

```python
# ❌ 错误顺序
@router.get("/{user_id}")
@router.get("/me")  # 永远匹配不到，"me" 会被当 user_id

# ✅ 正确顺序
@router.get("/me")
@router.get("/{user_id}")
```

---

### Q10：`response_model` 的作用？

**答**：
1. **自动序列化**：把返回对象按模型序列化
2. **字段过滤**：未声明字段自动丢弃（防泄露）
3. **生成文档**：Swagger 显示正确响应结构

```python
@router.post("", response_model=UserOut)
def create_user(...) -> UserInDB:
    return user_in_db  # 即使返回 UserInDB，按 UserOut 过滤掉 hashed_password
```

**安全价值**：双保险防密码泄露。

---

### Q11：FastAPI 同步路由 vs 异步路由怎么选？

**答**：
- `def`：同步路由，FastAPI 放线程池执行，不阻塞事件循环
- `async def`：异步路由，在事件循环执行

**选择**：
- 用同步库（SQLAlchemy 同步、requests）→ `def`
- 用异步库（aiomysql、httpx 异步）→ `async def`

**坑**：`async def` 里写同步阻塞代码（如 `time.sleep`）会阻塞整个事件循环。

---

## 三、Pydantic

### Q12：Pydantic v2 vs v1 主要区别？

**答**：
| 维度 | v1 | v2 |
|------|-----|-----|
| 性能 | 慢 | Rust 核心，快 5-50 倍 |
| 转字典 | `.dict()` | `.model_dump()` |
| 从 dict 创建 | `.parse_obj()` | `.model_validate()` |
| ORM 模式 | `class Config: orm_mode=True` | `model_config = ConfigDict(from_attributes=True)` |
| 字段校验器 | `@validator` | `@field_validator` |
| 模型校验器 | `@root_validator` | `@model_validator` |

---

### Q13：`Field(...)` 第一个参数 `...` 表示什么？

**答**：`...`（Ellipsis）表示**必填字段**。

```python
class User(BaseModel):
    id: int = Field(...)              # 必填
    email: str = Field(default=None)  # 可选，默认 None
    age: int = Field(default=18)      # 可选，默认 18
```

---

### Q14：`@field_validator` vs `@model_validator` 区别？

**答**：
- `@field_validator`：字段级，校验单个字段
- `@model_validator`：模型级，校验跨字段

```python
class PasswordChange(BaseModel):
    new: str
    confirm: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new != self.confirm:
            raise ValueError("两次密码不一致")
        return self
```

`mode="after"` 在所有字段校验完后执行，能访问 `self`。

---

## 四、SQLAlchemy

### Q15：`flush` vs `commit` 区别？

**答**：
| 操作 | flush | commit |
|------|-------|--------|
| 发 SQL | ✅ | ✅ |
| 提交事务 | ❌ | ✅ |
| 可回滚 | ✅ | ❌ |
| 释放锁 | ❌ | ✅ |
| 分配自增 id | ✅ | ✅ |

**关键**：`flush` 后 `rollback` 能撤销，`commit` 后不行。

---

### Q16：为什么 Repository 不 commit？

**答**：让 Service 层控制事务边界，多个 Repository 操作可组合为一个事务。

**举例**（转账）：
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

如果 Repository 各自 commit，第一个成功第二个失败时钱会丢。

---

### Q17：`pool_pre_ping=True` 解决什么问题？

**答**：解决连接池失效连接问题。

MySQL 默认 `wait_timeout=28800`（8 小时），空闲连接被 MySQL 关闭。如果连接池里这个失效连接被借出，会报 `MySQL server has gone away`。

`pool_pre_ping=True` 让 SQLAlchemy 借出前发 `SELECT 1` 检查，失效的丢弃，拿新的。

---

### Q18：SQLAlchemy 2.0 的 `Mapped` 是什么？

**答**：SQLAlchemy 2.0 的类型注解容器，描述列类型。

```python
class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
```

`Base` 的元类扫描 `Mapped[X]` 注解，推断列类型（`int` → `Integer`），生成列定义。

**vs 1.x**：
```python
# 1.x
class User(Base):
    id = Column(Integer, primary_key=True)

# 2.0
class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
```

---

## 五、Alembic

### Q19：Alembic autogenerate 的局限？

**答**：autogenerate 能识别：
- ✅ 新增/删除表
- ✅ 新增/删除列
- ✅ 改列类型（需 `compare_type=True`）
- ✅ 新增/删除索引

**不能识别**：
- ❌ 改表名（误识别为删表+建表）
- ❌ 改列名（误识别为删列+加列，**丢数据**）
- ❌ 数据迁移

**最佳实践**：autogenerate 后必检查脚本，改列名用 `op.alter_column(new_column_name=...)`。

---

### Q20：`alembic stamp head` 什么时候用？

**答**：数据库已有表但没用 Alembic 时，标记当前为最新版本，**不执行 SQL**。

```bash
# 数据库已有 users 表，现在接入 Alembic
alembic stamp head
# alembic_version 表写入 head 版本
# 之后改模型生成的迁移才能正常 upgrade
```

**对比**：
- `upgrade head`：执行迁移 SQL
- `stamp head`：只标记版本，不执行

---

## 六、架构设计

### Q21：为什么 Service 层不抛 HTTPException？

**答**：Service 层应该与 HTTP 解耦，可以被 CLI、定时任务、其他 Service 复用。绑定 HTTP 概念后复用性下降。

**正确做法**：
- Service 抛业务异常（继承 Exception）
- API 层用全局处理器翻译为 HTTP

```python
# Service
class UserNotFoundError(Exception): ...

# 全局处理器
@app.exception_handler(UserNotFoundError)
async def handle(_, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

---

### Q22：ORM 模型和 Schema 模型为什么要分开？

**答**：用途不同。

| 维度 | ORM 模型 | Schema 模型 |
|------|---------|------------|
| 库 | SQLAlchemy | Pydantic |
| 用途 | 映射数据库表 | 层间数据传输 |
| 方法 | db.add(), commit() | model_validate(), model_dump() |

**分开的好处**：
- 换 ORM（如 MongoDB）只改 ORM 模型，Schema 不变
- 换 API 框架只改 Schema，ORM 不变
- 安全：Schema 可以隐藏敏感字段（如 `hashed_password`）

---

### Q23：DTO 转换在哪些层做？

**答**：
- **Repository 层**：ORM ↔ Schema（UserInDB）转换
- **Service 层**：UserInDB → UserOut 转换（屏蔽密码字段）

```python
# Repository: ORM → UserInDB
@staticmethod
def _to_schema(user: User) -> UserInDB:
    return UserInDB(id=user.id, ...)

# Service: UserInDB → UserOut
return UserOut.model_validate(user_in_db)
```

**关键**：API 层永远拿不到 `UserInDB`，双保险防泄露。

---

### Q24：四层架构的依赖方向？

**答**：
```
API → Schema
API → Service → Repository → ORM
Service → Schema
Repository → Schema (仅 UserInDB)
```

**禁止**：
- Service → HTTP 概念（除 Depends）
- Repository → db.commit()
- Schema → 任何其他层

---

## 七、安全

### Q25：为什么用 bcrypt 而不是 MD5/SHA？

**答**：
- **慢**：bcrypt 设计为慢，每次 250ms，暴力破解不可行
- **自带盐**：相同密码哈希不同，防彩虹表
- **可调工作因子**：算力提升时增加 rounds
- **抗 GPU/ASIC**：内存访问模式不友好

MD5/SHA 太快，GPU 每秒算几十亿次，暴力破解容易。

---

### Q26：bcrypt 工作因子 12 vs 14 怎么选？

**答**：
- rounds=12：~250ms，**推荐**，平衡安全与体验
- rounds=14：~1s，高安全，但用户登录等 1s 可能影响体验

**每增加 1，耗时翻倍**。

**选择原则**：用户可接受的等待时间 × 安全性需求。一般 12 足够。

---

### Q27：JWT payload 能放密码吗？

**答**：**不能**。JWT payload 只签名防篡改，**不加密**。任何人能 base64 解码看到内容。

只放 user_id 等非敏感信息。

---

## 八、部署

### Q28：Docker 多阶段构建的好处？

**答**：
1. **镜像更小**：runtime 阶段不带编译工具（gcc 等）
2. **攻击面小**：没有编译工具，黑客可利用的工具少
3. **构建快**：缓存复用

```dockerfile
# builder 阶段：装 gcc，编译依赖
FROM python:3.11-slim AS builder
RUN apt-get install -y build-essential
RUN pip install --prefix=/install -r requirements.txt

# runtime 阶段：只复制产物
FROM python:3.11-slim
COPY --from=builder /install /usr/local
```

---

### Q29：为什么 `.env` 必须在 `.dockerignore`？

**答**：`COPY . .` 会把 `.env` 打进镜像，密码泄露。任何人 `docker history` 或 `docker export` 都能看到。

**正确做法**：
- `.dockerignore` 排除 `.env`
- 运行时通过环境变量传入（`docker compose` 的 `environment`）

---

### Q30：CI/CD 流水线为什么要 services？

**答**：GitHub Actions 的 `services` 在 CI 机器上启动容器（如 MySQL），测试代码连 `127.0.0.1:3306`。

```yaml
services:
  mysql:
    image: mysql:8.4
    env:
      MYSQL_ROOT_PASSWORD: 123456
    ports: ["3306:3306"]
```

**好处**：
- 测试环境隔离（每个 CI run 独立数据库）
- 不依赖外部数据库
- 测试完自动清理

---

## 📊 面试题速查表

| 主题 | 高频题 |
|------|--------|
| Python | 类型注解、yield、Optional vs `X\|None` |
| FastAPI | 为什么快、Depends、lifespan、路由顺序 |
| Pydantic | v1 vs v2、Field、校验器 |
| SQLAlchemy | flush vs commit、Mapped、连接池 |
| Alembic | autogenerate 局限、stamp |
| 架构 | Repository 模式、四层依赖、DTO 转换 |
| 安全 | bcrypt、工作因子、JWT |
| 部署 | 多阶段构建、.dockerignore、CI services |

---

## 🎯 面试加分技巧

1. **举项目实例**："在我做的用户管理项目里，Repository 不 commit 是为了..."
2. **对比讲**："Flask 用 WSGI，FastAPI 用 ASGI，区别是..."
3. **讲原理**："bcrypt 慢是因为 2^12 轮迭代..."
4. **讲权衡**："rounds=12 是安全和体验的平衡..."
5. **讲坑**："autogenerate 改列名会丢数据，要手动改..."

---

**下一篇**：[14 常见错误与调试技巧](14-debugging-guide.md) — 21 个常见错误及排查方法。
