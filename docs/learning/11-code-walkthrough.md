# 11 - 项目代码导览（按文件清单学）

> 系列文章第 11 篇（附录 A）。本篇按文件清单带你逐文件通读项目，每个文件做什么、关键代码、对应哪篇正文。

## 你将学到

- 项目所有文件的职责
- 推荐阅读顺序
- 每个文件对应系列哪篇正文
- 哪些文件是核心，哪些是辅助

---

## 📂 推荐阅读顺序

按依赖关系从底层往上读：

```
配置 → ORM → Schema → Repository → Service → API → 入口 → 测试 → 部署
```

### 阶段 1：基础设施（5 个文件）

| 序号 | 文件 | 篇正文 |
|------|------|--------|
| 1 | `.env.example` | 02 FastAPI |
| 2 | `app/db.py` | 04 SQLAlchemy |
| 3 | `app/logger.py` | 08 异常日志 |
| 4 | `app/models/user.py` | 04 SQLAlchemy |
| 5 | `app/schema/user.py` | 03 Pydantic |

### 阶段 2：业务层（3 个文件）

| 序号 | 文件 | 篇正文 |
|------|------|--------|
| 6 | `app/repository/user_repo.py` | 04 SQLAlchemy、06 架构 |
| 7 | `app/service/user_service.py` | 07 安全、06 架构 |
| 8 | `app/service/auth_service.py` | 07 安全 |

### 阶段 3：API 层（3 个文件）

| 序号 | 文件 | 篇正文 |
|------|------|--------|
| 9 | `app/api/users.py` | 02 FastAPI |
| 10 | `app/api/auth.py` | 02 FastAPI、07 安全 |
| 11 | `app/exception_handlers.py` | 08 异常日志 |

### 阶段 4：入口与测试

| 序号 | 文件 | 篇正文 |
|------|------|--------|
| 12 | `main.py` | 02 FastAPI |
| 13 | `tests/test_api.py` | 02 FastAPI |

### 阶段 5：部署与协作

| 序号 | 文件 | 篇正文 |
|------|------|--------|
| 14 | `Dockerfile` | 09 Docker |
| 15 | `docker-compose.yml` | 09 Docker |
| 16 | `.github/workflows/ci.yml` | 09 CI/CD |
| 17 | `scripts/check.py` | 10 AST |
| 18 | `.claude/settings.json` | 10 Hook |
| 19 | `alembic/env.py` | 05 Alembic |

---

## 阶段 1：基础设施详解

### 1. `.env.example` — 配置模板

```bash
DB_USER=root
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testdb
APP_ENV=development
SECRET_KEY=please_change_me
ACCESS_TOKEN_EXPIRE_MINUTES=60
LOG_LEVEL=INFO
```

**学习点**：
- 敏感信息走环境变量，不硬编码
- 复制为 `.env` 后填真实值
- `.env` 在 `.gitignore` 排除

**对应正文**：[02 FastAPI - 配置管理](02-fastapi-internals.md)

### 2. `app/db.py` — 数据库引擎

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from dotenv import load_dotenv

load_dotenv()
DB_USER = os.getenv("DB_USER", "root")
...
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@..."

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**学习点**：
- `create_engine` 创建连接池
- `pool_pre_ping=True` 防失效连接
- `SessionLocal` 是 Session 工厂
- `get_db` 用 `yield` + `finally` 保证关闭

**对应正文**：[04 SQLAlchemy - 连接池](04-sqlalchemy-2.md)

### 3. `app/logger.py` — 日志配置

```python
import logging, sys

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"

def setup_logging():
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )

def get_logger(name):
    return logging.getLogger(name)
```

**学习点**：
- 日志输出到 stdout（容器化友好）
- 格式统一：时间 | 级别 | 模块:行号 | 消息
- 级别由环境变量控制

**对应正文**：[08 异常处理与日志](08-exceptions-and-logging.md)

### 4. `app/models/user.py` — ORM 模型

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, func
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[str] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
```

**学习点**：
- `Mapped[X]` 类型注解驱动
- `mapped_column(...)` 配置列
- `server_default` 让数据库填默认值
- `onupdate` 更新时自动刷新

**对应正文**：[04 SQLAlchemy - Mapped/mapped_column](04-sqlalchemy-2.md)

### 5. `app/schema/user.py` — Pydantic Schema

```python
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=64)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3)
    password: Optional[str] = Field(default=None, min_length=6)

class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class UserInDB(UserOut):
    hashed_password: str

T = TypeVar("T")
class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool = False
```

**学习点**：
- 继承复用字段
- `UserOut` 不含密码字段（安全）
- `UserInDB` 内部传输用
- `Page[T]` 泛型分页模型

**对应正文**：[03 Pydantic v2](03-pydantic-v2.md)

---

## 阶段 2：业务层详解

### 6. `app/repository/user_repo.py` — 数据访问

```python
class UserRepo:
    def __init__(self, db: Session):
        self._db = db

    def add(self, username, hashed_password):
        user = User(username=username, hashed_password=hashed_password)
        self._db.add(user)
        self._db.flush()  # 不 commit！
        return self._to_schema(user)
```

**学习点**：
- Repository 模式：把数据访问抽象成集合
- ORM ↔ Schema 转换（`_to_schema`）
- **不 commit**，事务由 Service 控制

**对应正文**：[04 SQLAlchemy - flush vs commit](04-sqlalchemy-2.md)、[06 架构](06-layered-architecture.md)

### 7. `app/service/user_service.py` — 业务逻辑

```python
class UserService:
    def __init__(self, repo: UserRepo):
        self._repo = repo

    def create_user(self, payload: UserCreate) -> UserOut:
        if self._repo.get_by_username(payload.username):
            raise UserAlreadyExistsError(...)
        hashed = hash_password(payload.password)
        try:
            user = self._repo.add(payload.username, hashed)
            self._commit()
        except IntegrityError:
            self._repo._db.rollback()
            raise UserAlreadyExistsError(...)
        return UserOut.model_validate(user)
```

**学习点**：
- 业务规则校验（用户名唯一）
- 密码哈希（bcrypt）
- 事务控制（commit/rollback）
- DTO 转换（UserInDB → UserOut）
- 并发兜底（捕获 IntegrityError）

**对应正文**：[07 密码安全与事务边界](07-security-and-transactions.md)、[06 架构](06-layered-architecture.md)

### 8. `app/service/auth_service.py` — JWT 鉴权

```python
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(401, "无效凭证", headers={"WWW-Authenticate": "Bearer"})
    return user_id
```

**学习点**：
- JWT 签发与验证
- `OAuth2PasswordBearer` 自动从 `Authorization: Bearer` 提取 token
- 鉴权失败抛 401

**对应正文**：[07 安全 - JWT](07-security-and-transactions.md)

---

## 阶段 3：API 层详解

### 9. `app/api/users.py` — 用户路由

```python
router = APIRouter(prefix="/users", tags=["用户管理"])

@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),  # 强制鉴权
):
    return svc.create_user(payload)
```

**学习点**：
- `APIRouter` 模块化路由
- `response_model` 自动序列化+过滤
- `Depends` 嵌套依赖（get_db → get_user_service → 路由）
- 鉴权用 `Depends(get_current_user_id)`
- 路由无 try/except（全局处理器）

**对应正文**：[02 FastAPI](02-fastapi-internals.md)

### 10. `app/exception_handlers.py` — 全局异常处理

```python
def register_exception_handlers(app):
    @app.exception_handler(UserNotFoundError)
    async def handle(_, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected(_, exc):
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
```

**学习点**：
- `@app.exception_handler` 注册全局处理器
- 500 不暴露细节（安全）
- `logger.exception` 自动带堆栈

**对应正文**：[08 异常处理](08-exceptions-and-logging.md)

---

## 阶段 4：入口与测试

### 11. `main.py` — 应用入口

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动完成")
    yield
    engine.dispose()
    logger.info("应用已关闭")

app = FastAPI(
    title="用户管理 API",
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,  # 生产关闭文档
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(users_router)
```

**学习点**：
- `lifespan` 替代弃用的 `on_event`
- 生产环境关闭 `/docs`
- 注册路由 + 异常处理器

**对应正文**：[02 FastAPI - lifespan](02-fastapi-internals.md)

### 12. `tests/test_api.py` — 测试

```python
client = TestClient(app)

def _login(username, password):
    r = client.post("/token", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def test_full_flow():
    # 0. 未登录 → 401
    # 1. 创建种子用户（绕过鉴权）
    # 2. 登录拿 token
    # 3. 密码错误 → 401
    # 4. 用户名冲突 → 409
    # 5-12. CRUD
    # 13. 健康检查
    # 14. 伪造 token → 401
```

**学习点**：
- `TestClient` 不需启动服务直接打 app
- 测试覆盖鉴权、CRUD、错误分支
- 用 `SessionLocal` 直接创建种子用户（绕过鉴权）

**对应正文**：[02 FastAPI - TestClient](02-fastapi-internals.md)

---

## 阶段 5：部署与协作

### 13. `Dockerfile` — 多阶段构建

```dockerfile
FROM python:3.11-slim AS builder
RUN apt-get install -y build-essential
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /install /usr/local
COPY . .
USER appuser
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker"]
```

**学习点**：
- 多阶段构建：builder 编译，runtime 只复制产物
- 非 root 用户
- gunicorn 管理 uvicorn worker

**对应正文**：[09 Docker](09-docker-and-cicd.md)

### 14. `scripts/check.py` — AST 校验

```python
class ForbiddenCallChecker(ast.NodeVisitor):
    def visit_Call(self, node):
        # 拼接属性链 a.b.c
        # 检查是否在禁止列表
        ...

def main():
    check_repository_no_commit()
    check_no_on_event()
    check_no_passlib()
    ...
```

**学习点**：
- `ast.parse` 解析源码
- `NodeVisitor` 访问者模式
- AST 比 grep 精确（零误报）

**对应正文**：[10 Claude Hook 与 AST](10-claude-hooks-and-ast.md)

---

## 📋 文件清单速查表

| 文件 | 行数 | 职责 | 重要性 |
|------|------|------|--------|
| `main.py` | ~100 | 应用入口 | ⭐⭐⭐⭐⭐ |
| `app/db.py` | ~80 | 数据库引擎 | ⭐⭐⭐⭐⭐ |
| `app/models/user.py` | ~40 | ORM 模型 | ⭐⭐⭐⭐⭐ |
| `app/schema/user.py` | ~80 | Pydantic 校验 | ⭐⭐⭐⭐⭐ |
| `app/repository/user_repo.py` | ~120 | 数据访问 | ⭐⭐⭐⭐⭐ |
| `app/service/user_service.py` | ~230 | 业务逻辑+事务 | ⭐⭐⭐⭐⭐ |
| `app/service/auth_service.py` | ~80 | JWT 鉴权 | ⭐⭐⭐⭐ |
| `app/api/users.py` | ~100 | 用户路由 | ⭐⭐⭐⭐ |
| `app/api/auth.py` | ~40 | 登录路由 | ⭐⭐⭐ |
| `app/exception_handlers.py` | ~50 | 全局异常 | ⭐⭐⭐⭐ |
| `app/logger.py` | ~50 | 日志配置 | ⭐⭐⭐ |
| `tests/test_api.py` | ~120 | 冒烟测试 | ⭐⭐⭐ |
| `Dockerfile` | ~50 | 容器构建 | ⭐⭐⭐⭐ |
| `docker-compose.yml` | ~80 | 多服务编排 | ⭐⭐⭐⭐ |
| `.github/workflows/ci.yml` | ~100 | CI/CD | ⭐⭐⭐ |
| `scripts/check.py` | ~200 | AST 校验 | ⭐⭐⭐ |
| `alembic/env.py` | ~80 | 迁移环境 | ⭐⭐⭐ |

---

## 🎯 推荐学习路径

### 路径 1：从入口往下（自顶向下）

```
main.py
  ↓ 看路由注册
app/api/users.py
  ↓ 看 Depends 链
app/service/user_service.py
  ↓ 看 ORM 操作
app/repository/user_repo.py
  ↓ 看表结构
app/models/user.py
  ↓ 看连接配置
app/db.py
```

### 路径 2：从数据往上（自底向上）

```
.env.example → app/db.py → app/models/
  ↓
app/schema/
  ↓
app/repository/
  ↓
app/service/
  ↓
app/api/ → main.py
```

### 路径 3：按系列文章顺序

1. 读 [01-03 篇](README.md) 打基础
2. 读项目阶段 1（基础设施）
3. 读 [04-05 篇](README.md) 学 ORM 和迁移
4. 读项目阶段 2（业务层）
5. 读 [06-08 篇](README.md) 学架构
6. 读项目阶段 3（API 层）
7. 读 [09-10 篇](README.md) 学部署
8. 读项目阶段 5（部署）

---

## ✅ 学完验证

读完所有文件后，你应该能回答：

- [ ] 为什么 `app/db.py` 用 `yield` 写 `get_db`？
- [ ] 为什么 `app/repository/user_repo.py` 不调 `db.commit()`？
- [ ] 为什么 `app/schema/user.py` 要分 4 个模型？
- [ ] 为什么 `app/service/user_service.py` 抛业务异常而不抛 HTTPException？
- [ ] 为什么 `app/api/users.py` 路由没有 try/except？
- [ ] 为什么 `main.py` 用 `lifespan` 而不是 `on_event`？
- [ ] 为什么 `Dockerfile` 用多阶段构建？
- [ ] 为什么 `scripts/check.py` 用 AST 而不是 grep？

每个问题都能答上来，说明你掌握了项目设计思想。

---

**下一篇**：[12 动手实战](12-hands-on-projects.md) — 5 个扩展任务带你动手改项目。
