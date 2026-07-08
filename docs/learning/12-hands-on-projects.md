# 12 - 动手实战（5 个扩展任务）

> 系列文章第 12 篇（附录 B）。本篇给你 5 个由易到难的扩展任务，每个任务带详细实现指南，带你真正动手改项目。

## 你将学到

- 如何给项目加新字段
- 如何加新模块（订单系统）
- 如何加 Refresh Token
- 如何加 RBAC 角色权限
- 如何加 Redis 缓存

---

## 🎯 任务概览

| # | 任务 | 难度 | 涉及知识点 |
|---|------|------|----------|
| 1 | 给 User 加 email 字段 | ⭐ | Alembic 迁移、Schema、ORM |
| 2 | 加订单模块（Order CRUD） | ⭐⭐⭐ | 四层架构实战 |
| 3 | 加 Refresh Token | ⭐⭐ | JWT、安全 |
| 4 | 加 RBAC 角色权限 | ⭐⭐⭐⭐ | 鉴权、依赖注入 |
| 5 | 加 Redis 缓存用户查询 | ⭐⭐⭐⭐ | 缓存、性能 |

每完成一个任务，你的项目就离生产级更近一步。

---

## 任务 1：给 User 加 email 字段

**目标**：User 表加 `email` 字段，支持注册时填邮箱，查询时返回。

### 1.1 改 ORM 模型

```python
# app/models/user.py
class User(Base):
    ...
    email: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
```

### 1.2 生成迁移

```bash
source env/bin/activate
alembic revision --autogenerate -m "add email column"
```

检查生成的 `alembic/versions/xxx_add_email_column.py`：

```python
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(100), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade():
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")
```

### 1.3 执行迁移

```bash
alembic upgrade head
```

### 1.4 改 Schema

```python
# app/schema/user.py
class UserBase(BaseModel):
    username: str = Field(...)
    email: Optional[str] = Field(default=None, pattern=r"^[\w.-]+@[\w.-]+\.\w+$")

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = Field(default=None, pattern=r"^[\w.-]+@[\w.-]+\.\w+$")
```

### 1.5 改 Repository

```python
# app/repository/user_repo.py
@staticmethod
def _to_schema(user: User) -> UserInDB:
    return UserInDB(
        id=user.id,
        username=user.username,
        email=user.email,  # 加这行
        hashed_password=user.hashed_password,
    )

def get_by_email(self, email: str) -> Optional[UserInDB]:
    user = self._db.scalars(select(User).where(User.email == email)).one_or_none()
    return self._to_schema(user) if user else None
```

### 1.6 改 Service

```python
# app/service/user_service.py
def create_user(self, payload: UserCreate) -> UserOut:
    if self._repo.get_by_username(payload.username):
        raise UserAlreadyExistsError(...)
    if payload.email and self._repo.get_by_email(payload.email):
        raise UserAlreadyExistsError("邮箱已被使用")  # 可以新建一个异常类
    ...
```

### 1.7 测试

```bash
# 启动
python -m uvicorn main:app --reload

# 创建带 email 的用户
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123","email":"alice@example.com"}'
```

### 1.8 验证清单

- [ ] 数据库 `users` 表有 `email` 列
- [ ] 创建用户时能填 email
- [ ] email 格式校验生效
- [ ] email 重复时报错
- [ ] `alembic downgrade -1` 能回滚

---

## 任务 2：加订单模块（Order CRUD）

**目标**：实现订单模块，用户能创建/查询自己的订单。

### 2.1 设计

```
orders 表
- id: INT PK
- user_id: INT FK → users.id
- amount: DECIMAL(10, 2)
- status: VARCHAR(20)  -- pending/paid/cancelled
- created_at: DATETIME
```

### 2.2 创建 ORM 模型

```python
# app/models/order.py
from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.current_timestamp())

    # 关系（可选）
    user: Mapped["User"] = relationship(back_populates="orders")
```

```python
# app/models/user.py 加
class User(Base):
    ...
    orders: Mapped[List["Order"]] = relationship(back_populates="user")
```

```python
# app/models/__init__.py
from .user import User
from .order import Order
```

### 2.3 生成迁移

```bash
alembic revision --autogenerate -m "add orders table"
alembic upgrade head
```

### 2.4 创建 Schema

```python
# app/schema/order.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class OrderCreate(BaseModel):
    amount: float = Field(..., gt=0, description="订单金额")

class OrderUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern=r"^(pending|paid|cancelled)$")

class OrderOut(BaseModel):
    id: int
    user_id: int
    amount: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 2.5 创建 Repository

```python
# app/repository/order_repo.py
class OrderRepo:
    def __init__(self, db: Session):
        self._db = db

    def add(self, user_id: int, amount: float) -> OrderOut:
        order = Order(user_id=user_id, amount=amount)
        self._db.add(order)
        self._db.flush()
        return OrderOut.model_validate(order)

    def get(self, order_id: int) -> Optional[OrderOut]:
        order = self._db.scalars(select(Order).where(Order.id == order_id)).one_or_none()
        return OrderOut.model_validate(order) if order else None

    def list_by_user(self, user_id: int, skip: int = 0, limit: int = 20):
        orders = self._db.scalars(
            select(Order).where(Order.user_id == user_id).offset(skip).limit(limit)
        ).all()
        return [OrderOut.model_validate(o) for o in orders]
```

### 2.6 创建 Service

```python
# app/service/order_service.py
class OrderService:
    def __init__(self, repo: OrderRepo):
        self._repo = repo

    @classmethod
    def from_db(cls, db):
        return cls(OrderRepo(db))

    def create_order(self, user_id: int, payload: OrderCreate) -> OrderOut:
        order = self._repo.add(user_id=user_id, amount=payload.amount)
        self._commit()
        return order

    def get_order(self, order_id: int, user_id: int) -> OrderOut:
        order = self._repo.get(order_id)
        if order is None:
            raise OrderNotFoundError(...)
        if order.user_id != user_id:
            raise OrderNotFoundError(...)  # 不暴露存在性
        return order

    def list_my_orders(self, user_id: int, skip: int = 0, limit: int = 20):
        return self._repo.list_by_user(user_id, skip, limit)
```

### 2.7 创建 API

```python
# app/api/orders.py
router = APIRouter(prefix="/orders", tags=["订单管理"])

@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    user_id: int = Depends(get_current_user_id),
    svc: OrderService = Depends(get_order_service),
):
    return svc.create_order(user_id, payload)

@router.get("", response_model=Page[OrderOut])
def list_my_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    svc: OrderService = Depends(get_order_service),
):
    orders = svc.list_my_orders(user_id, skip, limit)
    return Page[OrderOut](items=orders, total=len(orders), skip=skip, limit=limit)
```

### 2.8 注册路由

```python
# main.py
from app.api import users_router, auth_router, orders_router
app.include_router(orders_router)
```

### 2.9 验证清单

- [ ] 创建订单（带 token）
- [ ] 查询自己的订单
- [ ] 查不到别人的订单
- [ ] 分页查询正常
- [ ] 数据库 FK 约束生效

---

## 任务 3：加 Refresh Token

**目标**：access token 短期（15 分钟），refresh token 长期（7 天），用 refresh 续期。

### 3.1 设计

```
登录 → 返回 access_token (15min) + refresh_token (7d)
access 过期 → 用 refresh 换新的 access
refresh 过期 → 重新登录
```

### 3.2 改 Schema

```python
# app/schema/auth.py
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str
```

### 3.3 改 auth_service

```python
# app/service/auth_service.py
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")

def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), "refresh")

def _create_token(user_id: int, expires_delta: timedelta, token_type: str) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + expires_delta,
        "type": token_type,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str, expected_type: str = None) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if expected_type and payload.get("type") != expected_type:
            return None
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None
```

### 3.4 改登录接口

```python
# app/api/auth.py
@router.post("/token", response_model=Token)
def login(payload: LoginRequest, svc=Depends(get_user_service)):
    user = svc.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )

@router.post("/refresh", response_model=Token)
def refresh_token(payload: RefreshRequest):
    user_id = decode_token(payload.refresh_token, expected_type="refresh")
    if user_id is None:
        raise HTTPException(401, "refresh_token 无效或过期")
    return Token(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),  # 滚动续期
    )
```

### 3.5 验证清单

- [ ] 登录返回 access + refresh
- [ ] access 能调接口
- [ ] refresh 不能调普通接口（type 检查）
- [ ] `/refresh` 接口能换新 token
- [ ] 过期的 refresh 报 401

---

## 任务 4：加 RBAC 角色权限

**目标**：User 加 role 字段（admin/user），admin 能查所有用户，普通用户只能查自己。

### 4.1 改 ORM

```python
# app/models/user.py
class User(Base):
    ...
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
```

```bash
alembic revision --autogenerate -m "add role column"
alembic upgrade head
```

### 4.2 改 Schema

```python
# app/schema/user.py
class UserOut(UserBase):
    id: int
    role: str
    model_config = ConfigDict(from_attributes=True)
```

### 4.3 加权限依赖

```python
# app/service/auth_service.py
def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(401, ...)
    return user_id

def get_current_user(
    user_id: int = Depends(get_current_user_id),
    svc: UserService = Depends(get_user_service),
) -> UserOut:
    return svc.get_user(user_id)

def require_admin(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    if current_user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return current_user
```

### 4.4 用在路由上

```python
# app/api/users.py
@router.get("", response_model=Page[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    svc: UserService = Depends(get_user_service),
    _: UserOut = Depends(require_admin),  # 只有 admin 能查列表
):
    return svc.list_users(skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
    current_user: UserOut = Depends(get_current_user),
):
    # 普通用户只能查自己
    if current_user.role != "admin" and user_id != current_user.id:
        raise HTTPException(403, "无权查看其他用户")
    return svc.get_user(user_id)
```

### 4.5 验证清单

- [ ] 普通用户查列表 → 403
- [ ] admin 查列表 → 200
- [ ] 普通用户查自己 → 200
- [ ] 普通用户查别人 → 403
- [ ] admin 查任何人 → 200

---

## 任务 5：加 Redis 缓存用户查询

**目标**：用 Redis 缓存 `get_user` 结果，减轻数据库压力。

### 5.1 安装依赖

```bash
pip install redis
```

### 5.2 Redis 客户端

```python
# app/cache.py
import redis
import json
import os

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
)

CACHE_TTL = 300  # 5 分钟
```

### 5.3 改 Service

```python
# app/service/user_service.py
from app.cache import redis_client, CACHE_TTL

class UserService:
    def get_user(self, user_id: int) -> UserOut:
        cache_key = f"user:{user_id}"

        # 1. 先查缓存
        cached = redis_client.get(cache_key)
        if cached:
            return UserOut.model_validate_json(cached)

        # 2. 缓存没有，查数据库
        user = self._repo.get(user_id)
        if user is None:
            raise UserNotFoundError(...)

        user_out = UserOut.model_validate(user)

        # 3. 写缓存
        redis_client.setex(cache_key, CACHE_TTL, user_out.model_dump_json())

        return user_out

    def update_user(self, user_id, payload):
        updated = super().update_user(user_id, payload)
        # 更新时清缓存
        redis_client.delete(f"user:{user_id}")
        return updated

    def delete_user(self, user_id):
        super().delete_user(user_id)
        redis_client.delete(f"user:{user_id}")
```

### 5.4 docker-compose 加 Redis

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]

  app:
    environment:
      REDIS_URL: redis://redis:6379/0
```

### 5.5 验证清单

- [ ] 第一次查询命中数据库
- [ ] 第二次查询命中缓存（看日志）
- [ ] 更新用户后缓存被清
- [ ] 删除用户后缓存被清
- [ ] Redis 宕机不影响主流程（try/except 兜底）

### 5.6 进阶：缓存兜底

```python
def get_user(self, user_id):
    cache_key = f"user:{user_id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return UserOut.model_validate_json(cached)
    except Exception:
        logger.warning("Redis 异常，降级查数据库")

    user = self._repo.get(user_id)
    ...
    try:
        redis_client.setex(cache_key, CACHE_TTL, user_out.model_dump_json())
    except Exception:
        logger.warning("Redis 写缓存失败")
    return user_out
```

**关键**：Redis 异常不能影响主流程，降级到数据库。

---

## 🎯 任务完成后

完成 5 个任务后，你的项目具备：

| 能力 | 任务 |
|------|------|
| 字段扩展 | 1 |
| 完整模块开发 | 2 |
| JWT 续期 | 3 |
| 权限控制 | 4 |
| 缓存优化 | 5 |

这已经是一个**接近真实生产**的项目了。

---

## 📋 学习建议

1. **按顺序做**：任务由易到难，每个任务都基于前面
2. **先自己尝试**：看任务描述先动手，卡住再看实现指南
3. **跑测试验证**：每完成一步跑 `python tests/test_api.py`
4. **提交 git**：每个任务一个 commit，方便回滚

**下一篇**：[13 面试题集](13-interview-questions.md) — 30 道面试题覆盖项目所有知识点。
