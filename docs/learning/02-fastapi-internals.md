# 02 - FastAPI 框架入门与原理

> 系列文章第 2 篇。本篇讲清楚 FastAPI 是什么、为什么快、依赖注入怎么工作、路由怎么匹配、生命周期怎么管理。

## 你将学到

- ASGI vs WSGI 的本质区别
- FastAPI / Starlette / Pydantic 三者关系
- 依赖注入（`Depends`）的执行机制
- 路由匹配与 `APIRouter` 组织
- `lifespan` 生命周期钩子（替代弃用的 `on_event`）
- FastAPI 为什么比 Flask 快

---

## 1. FastAPI 是什么

FastAPI 是一个现代 Python Web 框架，由 Sebastián Ramírez 于 2018 年创建。它有三个核心特点：

1. **快**：基于 ASGI 异步，性能接近 Node.js / Go
2. **简单**：类型注解驱动，少写代码
3. **自动文档**：Swagger / ReDoc 自动生成

### 1.1 三层依赖关系

```
FastAPI
   │
   ├── Starlette（底层 ASGI 框架，提供路由、中间件、HTTP）
   │
   └── Pydantic（数据校验，把类型注解变成校验规则）
```

- **Starlette**：FastAPI 的 Web 内核，纯异步 ASGI 框架
- **Pydantic**：数据校验库，FastAPI 用它校验请求体、序列化响应
- **FastAPI**：在两者之上加了一层语法糖，让开发更爽

### 1.2 一个最简单的 FastAPI 应用

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def hello():
    return {"msg": "hello"}
```

启动：

```bash
uvicorn main:app --reload
```

`main:app` 表示 `main.py` 文件里的 `app` 变量。

---

## 2. ASGI vs WSGI：为什么 FastAPI 快

### 2.1 WSGI（同步）

老一代 Python Web 框架（Flask、Django）用 WSGI 协议：

```
请求 → WSGI Server (gunicorn) → Flask → 处理 → 响应
```

**问题**：一个请求占一个 worker，等数据库时 worker 空闲，浪费资源。

### 2.2 ASGI（异步）

```
请求 → ASGI Server (uvicorn) → FastAPI (async) → 处理（可让出 CPU）→ 响应
```

**优势**：异步 I/O，一个 worker 能处理多个请求。等数据库时让出 CPU 给其他请求。

### 2.3 同步 vs 异步代码对比

```python
# Flask（同步）
@app.route("/users")
def get_users():
    users = db.query_all()  # 阻塞等数据库，worker 空闲
    return jsonify(users)

# FastAPI（异步）
@app.get("/users")
async def get_users():
    users = await db.query_all()  # 等数据库时让出 CPU
    return users
```

### 2.4 本项目为什么用同步

你看项目代码：

```python
@router.get("")
def list_users(svc: UserService = Depends(get_user_service)):  # def 不是 async def
    return svc.list_users()
```

**用 `def` 而非 `async def`**，因为 SQLAlchemy 2.0 的同步 API 是阻塞的。FastAPI 会自动把同步路由放到线程池执行，不阻塞事件循环。

| 写法 | 适合场景 |
|------|---------|
| `async def` | I/O 异步库（asyncpg、httpx 异步、Redis 异步） |
| `def` | 同步库（SQLAlchemy 同步、requests） |

本项目用 SQLAlchemy 同步 API，所以路由用 `def`。

---

## 3. 依赖注入：`Depends` 的原理

依赖注入是 FastAPI 最强大的特性。先看用法：

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
```

`Depends(get_db)` 告诉 FastAPI："调用 `list_users` 前，先调 `get_db`，把结果作为 `db` 参数传入"。

### 3.1 `yield` 依赖的执行流程

```python
def get_db():
    db = SessionLocal()    # 1. 创建 Session
    try:
        yield db           # 2. 把 db 注入路由
    finally:
        db.close()         # 3. 路由执行完，关闭 Session
```

执行顺序：

```
请求进来
  ↓
FastAPI 调 get_db()
  ↓
get_db 执行到 yield，把 db 给路由
  ↓
路由执行（用 db 查数据库）
  ↓
路由返回
  ↓
FastAPI 继续 get_db 的 finally，关闭 db
  ↓
返回响应给客户端
```

**关键**：无论路由成功还是抛异常，`finally` 都会执行，保证连接释放。

### 3.2 嵌套依赖

依赖可以嵌套：

```python
def get_db():
    db = SessionLocal()
    yield db

def get_user_service(db: Session = Depends(get_db)):
    return UserService(UserRepo(db))

@router.get("/users")
def list_users(svc: UserService = Depends(get_user_service)):
    return svc.list_users()
```

FastAPI 自动按依赖顺序解析：

```
get_db → 拿到 db
   ↓
get_user_service(db) → 拿到 svc
   ↓
list_users(svc)
```

### 3.3 依赖缓存（同请求内）

同一个请求里，`Depends(get_db)` 只调用一次：

```python
@router.get("/")
def index(
    db1: Session = Depends(get_db),
    db2: Session = Depends(get_db),  # 同一个 db 实例
):
    assert db1 is db2  # True
```

**好处**：一个请求共享一个 db session，避免重复创建。

### 3.4 依赖的作用

| 场景 | 依赖做什么 |
|------|----------|
| 数据库 Session | 每请求独立 session |
| 当前用户 | 从 JWT 解析当前用户 |
| 权限校验 | 检查是否有权限 |
| 分页参数 | 解析 skip/limit |
| 限流 | 检查调用频率 |

### 3.5 `Depends` vs 普通函数调用

为什么不直接调函数？

```python
# ❌ 直接调用
@router.get("/users")
def list_users():
    db = SessionLocal()  # 没法自动关闭
    try:
        return db.query(User).all()
    finally:
        db.close()
```

问题：
1. 每个路由重复代码
2. 异常时 session 关闭逻辑复杂
3. 测试时无法 mock

用 `Depends`：
1. 一个依赖复用所有路由
2. 异常自动处理（finally）
3. 测试时替换依赖：

```python
app.dependency_overrides[get_db] = get_test_db
```

---

## 4. 路由匹配与 `APIRouter`

### 4.1 路由装饰器

```python
@app.get("/")           # GET 请求
@app.post("/users")     # POST 请求
@app.put("/users/{id}") # PUT 请求
@app.delete("/users/{id}")  # DELETE 请求
```

每个装饰器对应一个 HTTP 方法。

### 4.2 路径参数

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):  # 类型注解自动校验
    return {"id": user_id}
```

`user_id: int` 让 FastAPI 自动：
1. 从 URL 解析 `user_id`
2. 转成 int（转不了返回 422）
3. 传给函数

### 4.3 查询参数

```python
@app.get("/users")
def list_users(skip: int = 0, limit: int = 20):
    return {"skip": skip, "limit": limit}
```

URL 里没的参数（`skip`、`limit`）自动当查询参数：`/users?skip=0&limit=20`。

### 4.4 用 `Query` 加约束

```python
from fastapi import Query

@router.get("")
def list_users(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
):
    ...
```

- `ge=0`：必须 ≥ 0
- `le=100`：必须 ≤ 100
- `description`：Swagger 文档里显示

### 4.5 `APIRouter`：模块化路由

大项目不会把所有路由堆在一个文件。用 `APIRouter` 拆分：

```python
# app/api/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["用户管理"])

@router.get("")
def list_users(): ...

@router.get("/{user_id}")
def get_user(user_id: int): ...
```

```python
# main.py
from fastapi import FastAPI
from app.api import users_router

app = FastAPI()
app.include_router(users_router)
# 所有 /users 路径都由 users_router 处理
```

**好处**：
- 不同资源拆文件（users / orders / products）
- `prefix` 自动加前缀，避免重复
- `tags` 在 Swagger 里分组显示

### 4.6 路由匹配顺序（重要坑）

```python
@router.get("/users/me")      # ① 先注册
@router.get("/users/{user_id}")  # ② 后注册
```

**FastAPI 按注册顺序匹配**。如果反过来：

```python
@router.get("/users/{user_id}")  # 先注册
@router.get("/users/me")          # 后注册
```

访问 `/users/me` 会匹配第一个，把 `me` 当 `user_id`，转 int 失败返回 422。

**规则**：**静态路径在前，动态路径在后**。

---

## 5. 生命周期：`lifespan` vs `on_event`

### 5.1 弃用的 `on_event`

老写法：

```python
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.on_event("shutdown")
def on_shutdown():
    engine.dispose()
```

FastAPI 0.93+ 弃用，未来会移除。

### 5.2 新写法：`lifespan`

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup 阶段 ──
    Base.metadata.create_all(bind=engine)
    yield  # 应用运行期间挂起
    # ── shutdown 阶段 ──
    engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### 5.3 `asynccontextmanager` 原理

`asynccontextmanager` 把生成器函数转成异步上下文管理器。

```python
@asynccontextmanager
async def lifespan(app):
    print("startup")  # yield 之前 = __aenter__
    yield
    print("shutdown")  # yield 之后 = __aexit__
```

执行流程：

```
应用启动
  ↓
调用 lifespan(app)
  ↓
执行到 yield 之前的代码（startup）
  ↓
yield 让出控制权，应用开始接收请求
  ↓
（应用运行，处理无数请求）
  ↓
应用收到关闭信号（Ctrl+C / SIGTERM）
  ↓
继续执行 yield 之后的代码（shutdown）
  ↓
应用退出
```

### 5.4 为什么用 `lifespan` 而不是 `on_event`

| 维度 | `on_event` | `lifespan` |
|------|-----------|-----------|
| 状态 | 已弃用 | 推荐 |
| 共享状态 | 麻烦（用全局变量） | 简单（yield 之前的变量可传递） |
| 资源管理 | 分散（startup 和 shutdown 是两个函数） | 集中（一个函数里） |
| 异步支持 | 一般 | 原生 |

### 5.5 本项目的 `lifespan`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")
    yield
    engine.dispose()
    logger.info("应用已关闭，连接池释放")

app = FastAPI(lifespan=lifespan)
```

---

## 6. 请求处理流程

完整流程：

```
1. 客户端发起 HTTP 请求
   ↓
2. ASGI Server (uvicorn) 接收
   ↓
3. Starlette 中间件链（CORS、认证等）
   ↓
4. FastAPI 路由匹配
   ↓
5. 依赖注入解析（Depends 链）
   ↓
6. Pydantic 校验请求（body / query / path 参数）
   ↓
7. 调用路由函数
   ↓
8. 业务逻辑执行（Service → Repository → DB）
   ↓
9. Pydantic 序列化响应（response_model）
   ↓
10. 中间件链（响应方向）
   ↓
11. ASGI Server 返回响应
```

### 6.1 Pydantic 校验失败 → 422

如果请求体不符合 Schema，FastAPI 自动返回 422：

```json
POST /users
{"username": "ab"}  ← 长度不够 3

响应 422:
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "username"],
      "msg": "String should have at least 3 characters"
    }
  ]
}
```

### 6.2 `response_model` 过滤字段

```python
@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, ...):
    return svc.create_user(payload)  # 返回 UserOut
```

即使 service 返回 `UserInDB`（含 `hashed_password`），FastAPI 按 `UserOut` 字段过滤，**双保险防泄露**。

---

## 7. 异常处理

### 7.1 `HTTPException`

```python
from fastapi import HTTPException, status

@router.get("/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user
```

FastAPI 自动把 `HTTPException` 转成对应 HTTP 响应。

### 7.2 全局异常处理器（本项目用法）

```python
@app.exception_handler(UserNotFoundError)
async def handle_user_not_found(_, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def handle_unexpected_error(_, exc):
    logger.exception(...)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
```

**好处**：路由函数不用 try/except，业务异常直接抛。

### 7.3 `status` 常量

```python
from fastapi import status

status.HTTP_200_OK          # 200
status.HTTP_201_CREATED     # 201
status.HTTP_204_NO_CONTENT  # 204
status.HTTP_400_BAD_REQUEST # 400
status.HTTP_404_NOT_FOUND   # 404
status.HTTP_409_CONFLICT    # 409
status.HTTP_422_UNPROCESSABLE_ENTITY  # 422
status.HTTP_500_INTERNAL_SERVER_ERROR # 500
```

用常量比直接写数字可读性好。

---

## 8. FastAPI vs Flask 全面对比

| 维度 | Flask | FastAPI |
|------|-------|---------|
| 协议 | WSGI（同步） | ASGI（异步） |
| 性能 | 较慢 | 快（接近 Node.js） |
| 类型注解 | 可选 | 核心 |
| 数据校验 | 需插件 | 内置（Pydantic） |
| 自动文档 | 需 flask-restx | 内置 Swagger + ReDoc |
| 异步支持 | 需 async-flask | 原生 |
| 学习曲线 | 简单 | 简单（类型注解驱动） |
| 生态 | 极其丰富 | 快速增长 |

### 8.1 同接口代码对比

**Flask**：

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    if not data.get("username") or len(data["username"]) < 3:
        return jsonify({"error": "用户名至少 3 位"}), 400
    if not data.get("password") or len(data["password"]) < 6:
        return jsonify({"error": "密码至少 6 位"}), 400
    # ... 手动校验
    user = create_in_db(data)
    return jsonify({"id": user.id, "username": user.username}), 201
```

**FastAPI**：

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)

@app.post("/users", status_code=201)
def create_user(payload: UserCreate):
    user = create_in_db(payload)
    return {"id": user.id, "username": user.username}
```

FastAPI 用类型注解 + Pydantic 自动校验，代码量少一半。

---

## 9. 自动文档

启动服务后访问：

- http://127.0.0.1:8000/docs - Swagger UI（可在线测试）
- http://127.0.0.1:8000/redoc - ReDoc（只读文档）

### 9.1 文档元信息

```python
@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
    description="创建新用户，用户名唯一。冲突返回 409。",
    tags=["用户管理"],
)
def create_user(...): ...
```

这些元信息都会显示在 Swagger 文档里。

### 9.2 为什么用文档

- **前端联调**：直接给前端 Swagger URL，自动生成 API client
- **测试**：Swagger UI 能直接发请求
- **新人入门**：看文档比看代码快

---

## 10. 常见坑

### 10.1 同步路由阻塞事件循环

```python
# ❌ 同步阻塞操作放在 async def 里
@app.get("/slow")
async def slow():
    time.sleep(5)  # 阻塞整个事件循环 5 秒
    return {"ok": True}
```

**修复**：用 `def` 让 FastAPI 放到线程池，或用 `asyncio.sleep`：

```python
# ✅ 方案 1：用 def
@app.get("/slow")
def slow():
    time.sleep(5)
    return {"ok": True}

# ✅ 方案 2：用异步 sleep
@app.get("/slow")
async def slow():
    await asyncio.sleep(5)
    return {"ok": True}
```

### 10.2 忘记 `await`

```python
# ❌ 忘记 await
@app.get("/")
async def index():
    result = some_async_func()  # 返回 coroutine，没执行
    return result

# ✅ 正确
@app.get("/")
async def index():
    result = await some_async_func()
    return result
```

### 10.3 路由顺序

```python
# ❌ 动态路由在前
@router.get("/{user_id}")
@router.get("/me")  # 永远匹配不到

# ✅ 静态路由在前
@router.get("/me")
@router.get("/{user_id}")
```

### 10.4 `response_model` 漏字段

```python
class UserOut(BaseModel):
    id: int
    username: str

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    return {"id": 1, "username": "alice", "password": "xxx"}  # 多余字段

# 实际响应：{"id": 1, "username": "alice"}  ← password 被过滤
```

**这是好事**，但要记得定义好 `response_model`。

---

## 11. 自测题

### Q1：下面代码有什么问题？

```python
@app.get("/users/{user_id}")
async def get_user(user_id):
    return {"id": user_id}
```

<details>
<summary>查看答案</summary>

`user_id` 没有类型注解，FastAPI 不知道怎么解析。应该写 `user_id: int`。
</details>

### Q2：`Depends(get_db)` 用了 `yield`，什么时候执行 `finally`？

<details>
<summary>查看答案</summary>

路由函数执行完毕（无论成功还是异常）后，FastAPI 会继续执行 `yield` 之后的代码，包括 `finally` 块。
</details>

### Q3：下面两个路由，访问 `/users/me` 会匹配哪个？

```python
@router.get("/users/{user_id}")
def get_user(user_id: int): ...

@router.get("/users/me")
def get_me(): ...
```

<details>
<summary>查看答案</summary>

匹配第一个 `/{user_id}`，把 `me` 当 user_id，转 int 失败返回 422。应该把 `/users/me` 放在前面。
</details>

---

## 12. 小结

| 概念 | 关键点 |
|------|--------|
| ASGI | 异步协议，I/O 等待时让出 CPU |
| FastAPI 架构 | Starlette（Web）+ Pydantic（校验） |
| `Depends` | 依赖注入，自动调用、自动关闭、可嵌套 |
| `APIRouter` | 模块化路由，`prefix` 加前缀 |
| `lifespan` | 替代弃用的 `on_event`，集中管理生命周期 |
| `response_model` | 自动序列化 + 字段过滤 |
| 全局异常处理 | `@app.exception_handler` 注册 |

## 13. 下篇预告

下一篇讲 **Pydantic v2 数据校验深入**：`BaseModel` 原理、`Field` 约束、`model_validate` vs `model_dump`、`ConfigDict`、自定义校验器、泛型模型。

---

**延伸阅读**：
- [FastAPI 官方文档](https://fastapi.tiangolo.com/zh/)
- [Starlette 官方文档](https://www.starlette.io/)
- [ASGI 规范](https://asgi.readthedocs.io/)
- [PEP 3333 - WSGI](https://peps.python.org/pep-3333/)
