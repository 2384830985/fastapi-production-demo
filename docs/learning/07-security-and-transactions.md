# 07 - 密码安全与事务边界
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 7 篇。本篇讲清楚密码哈希原理、bcrypt 工作因子、JWT 鉴权、ACID 事务、事务边界设计。

## 你将学到

- 密码哈希算法选型（为什么选 bcrypt）
- bcrypt 的工作因子（rounds）怎么选
- salt 是什么，为什么需要
- 时序攻击与常量时间比对
- JWT 鉴权原理与实现（含 SECRET_KEY 兜底、鉴权失败抛 401）
- ACID 事务特性
- 事务边界设计原则
- 并发场景下的唯一约束兜底
- 生产级 JWT 配置清单

---

## 1. 密码安全基础

### 1.1 为什么不能存明文

```sql
-- 明文存储（绝对禁止）
SELECT username, password FROM users;
-- alice | secret123
```

风险：
- 数据库被拖库 → 所有密码泄露
- DBA 能看所有密码
- 日志可能记录密码
- 备份文件含明文

### 1.2 为什么不用 MD5/SHA

```python
import hashlib
hashlib.md5("secret123".encode()).hexdigest()
# e9d9c89e8f4e8b0c5c0e6a0a0a0a0a0a
```

**问题**：
1. **无盐**：相同密码哈希相同，彩虹表破解
2. **太快**：MD5 设计为快，GPU 每秒算几十亿次，暴力破解容易
3. **已被破**：MD5 有碰撞攻击

SHA256 也一样不适合密码，因为太快。

### 1.3 密码哈希算法的要求

| 要求 | 说明 |
|------|------|
| 慢 | 让暴力破解不可行（每次几百毫秒） |
| 自带盐 | 相同密码哈希不同 |
| 可调工作因子 | 算力提升时增加难度 |
| 抗 GPU/ASIC | 内存访问模式不友好 |

满足这些的算法：**bcrypt**、**argon2**、**PBKDF2**。

---

## 2. bcrypt 详解

### 2.1 bcrypt 哈希格式

```
$2b$12$dxST926hVXIIdXzMe3kQ3OL.e5w4vLp9qX8oWmW7qYqXbYjJvHsXy
```

拆解：

| 部分 | 含义 |
|------|------|
| `$2b` | 算法标识（bcrypt） |
| `$12` | 工作因子（2^12 = 4096 轮） |
| `$dxST926hVXIIdXzMe3kQ3O` | 盐（22 字符 base64） |
| `L.e5w4vLp9qX8oWmW7qYqXbYjJvHsXy` | 哈希值（31 字符） |

总共 60 字符，所以数据库列用 `VARCHAR(128)` 留余量。

### 2.2 工作因子（rounds）

```python
salt = bcrypt.gensalt(rounds=12)
```

`rounds=12` 表示 2^12 = 4096 轮迭代。

| rounds | 耗时 | 适用场景 |
|--------|------|---------|
| 10 | ~100ms | 测试 |
| 12 | ~250ms | **推荐**，生产 |
| 14 | ~1s | 高安全 |
| 16 | ~4s | 极端安全 |

**每增加 1，耗时翻倍**。

### 2.3 为什么 12 是推荐

- 用户登录等 250ms 可接受
- 暴力破解每次 250ms，1 亿个密码需要 ~290 天
- 算力提升后可调到 13、14

### 2.4 盐（salt）的作用

```python
bcrypt.hashpw(b"secret123", bcrypt.gensalt())
# b'$2b$12$AAAA...xxx'  ← 第一次

bcrypt.hashpw(b"secret123", bcrypt.gensalt())
# b'$2b$12$BBBB...yyy'  ← 第二次，不同
```

**相同密码每次哈希结果不同**，因为盐不同。

盐的作用：
- 防彩虹表攻击
- 相同密码不同用户哈希不同

bcrypt **自动加盐**，你不用手动管理。

### 2.5 验证密码

```python
def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8"),
    )
```

`checkpw` 内部：
1. 从 `hashed` 解析出盐和工作因子
2. 用相同参数哈希 `plain`
3. 常量时间比对两个哈希

**常量时间比对**：无论匹配与否，耗时相同，防时序攻击。

### 2.6 时序攻击是什么

```python
# 危险的比对方式
def bad_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False  # ← 第一个不同字符就返回
    return True
```

攻击者测量响应时间：
- 第 1 字符错了：100ns
- 第 2 字符错了：200ns
- ...

通过时间差推断正确字符，逐字破解。

`bcrypt.checkpw` 用常量时间比对，所有字符都比完才返回，耗时与匹配程度无关。

### 2.7 本项目的实现

```python
# app/service/user_service.py
import bcrypt

def hash_password(plain_password: str) -> str:
    """密码哈希，rounds=12"""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """常量时间比对"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
```

### 2.8 为什么不用 passlib

passlib 是密码哈希库的封装，但：
- passlib 1.7.4 与 bcrypt 4.x+ 不兼容
- 调用 `bcrypt.__about__.__version__` 已被移除
- 持续刷 warning 日志

直接用 bcrypt 官方包更轻量、API 更直接。

---

## 3. JWT 鉴权

### 3.1 JWT 是什么

JWT (JSON Web Token) 是一种紧凑的自包含 token，用于无状态鉴权。

格式：`header.payload.signature`

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwiZXhwIjoxNjk5OTk5OTk5fQ.signature
```

### 3.2 JWT 工作流程

```
1. 用户登录（POST /token）
   ↓
   服务端验证密码
   ↓
   服务端签发 JWT（含 user_id，过期时间）
   ↓
   返回 token 给客户端

2. 客户端访问受保护接口
   ↓
   请求头带 Authorization: Bearer <token>
   ↓
   服务端验证签名 + 过期时间
   ↓
   解析出 user_id，执行业务
```

### 3.3 JWT vs Session

| 维度 | Session | JWT |
|------|---------|-----|
| 状态 | 服务端存 | 无状态 |
| 存储 | 服务端内存/Redis | 客户端 |
| 扩展 | 需共享 session | 天然分布式 |
| 撤销 | 立即生效 | 难（需黑名单） |
| 大小 | 小 | 较大 |

### 3.4 本项目的 JWT 实现

**签发 token**：

```python
# app/service/auth_service.py
import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

# 从环境变量读取密钥和过期时间
# SECRET_KEY 必须显式设置，否则拒绝签发
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """签发 JWT，subject 通常是 str(user_id)。"""
    if not SECRET_KEY:
        # 关键：未配置密钥时拒绝签发，避免弱密钥被暴力破解
        raise RuntimeError("SECRET_KEY 未配置，无法签发 JWT")

    minutes = expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,                          # subject（用户 ID 字符串）
        "exp": now + timedelta(minutes=minutes),  # 过期时间，PyJWT 自动校验
        "iat": now,                               # 签发时间
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
```

**解码 token**：

```python
def decode_token(token: str) -> dict:
    """解码 JWT，失败抛 HTTPException(401)。

    注意：这里直接抛 HTTPException 而不是返回 None，
    让调用方代码更简洁，错误响应也更统一（带 WWW-Authenticate 头）。
    """
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY 未配置，无法校验 JWT")
    try:
        # PyJWT 自动校验 exp、签名
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

> **为什么抛 HTTPException 而不返回 None**：`auth_service` 已经承担了"鉴权失败 → HTTP 401"的语义，路由层就不用再写 `if user_id is None: raise ...`，依赖注入链条更干净。这也意味着 `auth_service` 是 Service 层里唯一知道 HTTP 概念的特例，因为它本质是 Web 中间件的一部分。

### 3.5 FastAPI 鉴权依赖

```python
# app/service/auth_service.py
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

# OAuth2PasswordBearer 会从 Authorization: Bearer <token> 头读取 token
# tokenUrl 指向登录接口路径，会出现在 /docs 的 Authorize 按钮配置里
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """FastAPI 依赖：从 token 解出当前用户 id（int）。"""
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(401, "token 缺少 sub 字段",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(401, "token subject 非合法用户 id",
                            headers={"WWW-Authenticate": "Bearer"})
```

### 3.6 路由使用

```python
# app/api/users.py
@router.get("")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),  # ← 强制鉴权
):
    return svc.list_users(skip=skip, limit=limit)
```

`Depends(get_current_user_id)` 强制所有受保护接口验证 token。变量名用 `_` 表示"参数被消费但不使用"，避免 lint 警告。

### 3.7 JWT 安全要点

| 要点 | 说明 | 本项目实现 |
|------|------|-----------|
| SECRET_KEY 强随机 | 用 `secrets.token_urlsafe(32)` 生成 | `.env.example` 注释提示生成命令 |
| SECRET_KEY 未配置拒绝服务 | 防止弱密钥上生产 | `create_access_token` 抛 RuntimeError |
| 不要存敏感信息 | JWT payload 可解码（只签名防篡改） | 只放 `sub` / `exp` / `iat` |
| 设置过期时间 | 防止 token 泄露后永久有效 | `ACCESS_TOKEN_EXPIRE_MINUTES` 默认 60 |
| HTTPS 传输 | 防 token 被截获 | 反向代理层做 TLS |
| 不撤销用短过期 | 配合 refresh token 续期 | 当前只有 access token |
| 鉴权失败统一 401 | 不区分"用户不存在"和"密码错误" | `authenticate_user` 都返回 None |

### 3.8 登录认证实现

```python
# app/service/user_service.py
def authenticate_user(self, username: str, plain_password: str) -> Optional[UserOut]:
    """登录认证：用户名 + 密码。

    Returns:
        认证成功返回 UserOut，用户不存在或密码错误统一返回 None。
        两种失败不区分，防爆破。
    """
    user = self._repo.get_by_username(username)
    if user is None:
        return None  # 用户不存在
    if not verify_password(plain_password, user.hashed_password):
        logger.warning("登录失败：密码错误 username=%s", username)
        return None  # 密码错误
    logger.info("登录成功 username=%s", username)
    return UserOut.model_validate(user)
```

**关键**：用户不存在和密码错误都返回 None，不告诉具体原因，防爆破。

对应的登录路由：

```python
# app/api/auth.py
@router.post("/token", response_model=Token)
def login(payload: LoginRequest, svc: UserService = Depends(get_user_service)) -> Token:
    user = svc.authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误",
                            headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, token_type="bearer")
```

### 3.9 生产级 JWT 配置清单

部署前逐项检查：

- [ ] `SECRET_KEY` 用 `python -c "import secrets;print(secrets.token_urlsafe(32))"` 生成
- [ ] `SECRET_KEY` 写入 `.env`，`.env` 在 `.gitignore` 中
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES` 不要过长（建议 ≤ 60 分钟）
- [ ] 未配置 `SECRET_KEY` 时应用启动/签发直接失败（`RuntimeError`）
- [ ] 鉴权失败返回 401 + `WWW-Authenticate: Bearer` 头
- [ ] `/token` 接口对登录失败统一返回 401，不区分原因
- [ ] 所有写接口（POST/PUT/DELETE）必带 `Depends(get_current_user_id)`
- [ ] 读接口（GET）也鉴权（本项目的 `/users` 列表也需登录）
- [ ] `APP_ENV=production` 时关闭 `/docs` `/redoc` `/openapi.json`（详见 [09 篇](09-docker-and-cicd.md)）

---

## 4. ACID 事务特性

### 4.1 ACID 是什么

| 特性 | 英文 | 含义 |
|------|------|------|
| 原子性 | Atomicity | 全部成功或全部回滚 |
| 一致性 | Consistency | 数据约束不破坏 |
| 隔离性 | Isolation | 并发事务互不干扰 |
| 持久性 | Durability | 提交后不丢 |

### 4.2 原子性举例

转账 100 元：A 扣 100，B 加 100。

- 全部成功：A=900, B=1100 ✅
- 全部回滚：A=1000, B=1000 ✅
- 部分成功：A=900, B=1000 ❌（钱丢了）

原子性保证"全部或全部回滚"。

### 4.3 隔离级别

MySQL InnoDB 默认 `REPEATABLE READ`：

| 级别 | 脏读 | 不可重复读 | 幻读 |
|------|------|----------|------|
| READ UNCOMMITTED | ✅ | ✅ | ✅ |
| READ COMMITTED | ❌ | ✅ | ✅ |
| REPEATABLE READ | ❌ | ❌ | ❌（MySQL 用 MVCC 解决） |
| SERIALIZABLE | ❌ | ❌ | ❌ |

- 脏读：读到未提交数据
- 不可重复读：同一查询两次结果不同
- 幻读：同一查询两次行数不同

---

## 5. 事务边界设计

### 5.1 本项目的事务模型

```
Repository：add/flush/delete（不 commit）
   ↓
Service：commit / rollback（控制事务）
```

### 5.2 为什么 Repository 不 commit

考虑转账：

```python
# ❌ Repository 各自 commit
def transfer(self, from_id, to_id, amount):
    self._repo.debit(from_id, amount)   # commit 了
    self._repo.credit(to_id, amount)    # 失败
    # 第一个已提交，第二个失败 → 钱丢了
```

```python
# ✅ Repository 不 commit，Service 控制
def transfer(self, from_id, to_id, amount):
    try:
        self._repo.debit(from_id, amount)   # flush
        self._repo.credit(to_id, amount)    # flush
        self._commit()  # 一起提交
    except Exception:
        self._repo._db.rollback()  # 一起回滚
        raise
```

### 5.3 事务范围原则

**事务范围越小越好**：
- 不在事务里做 HTTP 请求（外部调用可能慢）
- 不在事务里做重计算
- 事务只包数据库操作

```python
# ❌ 事务里有 HTTP 调用
def create_user_and_send_email(self, payload):
    try:
        user = self._repo.add(...)
        send_email(payload.username)  # 慢，占着数据库连接
        self._commit()
    except Exception:
        self._repo._db.rollback()

# ✅ 先提交事务，再发邮件
def create_user_and_send_email(self, payload):
    user = self._repo.add(...)
    self._commit()  # 先提交
    try:
        send_email(payload.username)  # 失败不影响用户创建
    except Exception:
        logger.warning("邮件发送失败 user_id=%s", user.id)
```

### 5.4 异常处理

```python
def _commit(self) -> None:
    try:
        self._repo._db.commit()
    except Exception:
        self._repo._db.rollback()
        raise
```

**关键**：commit 失败必须 rollback，否则 session 状态混乱。

---

## 6. 并发场景：唯一约束兜底

### 6.1 竞态条件

```python
def create_user(self, payload):
    # 1. 检查用户名
    if self._repo.get_by_username(payload.username):
        raise UserAlreadyExistsError(...)
    # 2. 创建用户
    user = self._repo.add(...)
    self._commit()
```

并发场景：
```
请求 A                    请求 B
  ↓                        ↓
检查 alice 不存在          检查 alice 不存在
  ↓                        ↓
INSERT alice              INSERT alice
  ↓                        ↓
commit                    commit
                          ↑ UNIQUE 约束冲突
```

### 6.2 数据库兜底

Service 层前置检查 + DB 唯一约束兜底：

```python
def create_user(self, payload):
    # 前置检查（友好提示）
    if self._repo.get_by_username(payload.username):
        raise UserAlreadyExistsError(...)

    try:
        user = self._repo.add(...)
        self._commit()
    except IntegrityError:  # ← DB 兜底
        self._repo._db.rollback()
        raise UserAlreadyExistsError(...)
```

**关键**：捕获 `IntegrityError`，主动 rollback。

### 6.3 数据库唯一约束

```python
# app/models/user.py
username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
#                                                    ↑ UNIQUE 约束
```

数据库层保证唯一性，是最后一道防线。

---

## 7. 密码安全检查清单

部署前检查：

- [ ] 密码用 bcrypt 哈希（不是 MD5/SHA）
- [ ] 工作因子 ≥ 12
- [ ] 数据库列只存哈希值，无明文
- [ ] 响应不含 `hashed_password` 字段
- [ ] 日志不记录密码
- [ ] `verify_password` 用常量时间比对
- [ ] 登录失败不区分"用户不存在"和"密码错误"
- [ ] JWT SECRET_KEY 强随机（`secrets.token_urlsafe(32)`）
- [ ] SECRET_KEY 未配置时应用拒绝签发 token（RuntimeError 兜底）
- [ ] JWT 设置过期时间（建议 ≤ 60 分钟）
- [ ] 所有 `/users` 接口 `Depends(get_current_user_id)` 强制鉴权
- [ ] HTTPS 传输（反向代理层）
- [ ] `APP_ENV=production` 时关闭 `/docs` `/openapi.json`

---

## 8. 自测题

### Q1：bcrypt 工作因子 12 vs 14，安全性差多少？

<details>
<summary>查看答案</summary>

每增加 1，耗时翻倍。14 比 12 慢 4 倍（2^2）。暴力破解时间也乘 4。但用户登录等待 1s 可能影响体验，需平衡。
</details>

### Q2：为什么 `bcrypt.checkpw` 是常量时间比对？

<details>
<summary>查看答案</summary>

防时序攻击。如果用普通字符串比较，匹配字符越多耗时越长，攻击者能通过响应时间推断正确字符。常量时间比对无论匹配与否耗时相同。
</details>

### Q3：JWT payload 能放密码吗？

<details>
<summary>查看答案</summary>

**不能**。JWT payload 只签名防篡改，不加密。任何人都能用 base64 解码看到 payload 内容。只放 user_id 等非敏感信息。
</details>

### Q4：为什么 Repository 不调 `db.commit()`？

<details>
<summary>查看答案</summary>

让 Service 控制事务边界，多个 Repository 操作可组合为一个事务（如转账场景）。Repository 自己 commit 后无法回滚。
</details>

### Q5：并发创建用户名重复，怎么兜底？

<details>
<summary>查看答案</summary>

1. Service 层前置检查（友好提示）
2. 数据库 UNIQUE 约束（最后防线）
3. Service 捕获 `IntegrityError`，rollback + 抛业务异常
</details>

---

## 9. 小结

| 概念 | 关键点 |
|------|--------|
| bcrypt | 慢哈希，自带盐，可调工作因子 |
| rounds=12 | 推荐值，约 250ms |
| 常量时间比对 | 防时序攻击 |
| JWT | 无状态 token，payload 不加密 |
| ACID | 原子/一致/隔离/持久 |
| 事务边界 | Service 控制，Repository 不 commit |
| 唯一约束兜底 | DB 层 + Service 捕获 IntegrityError |

## 10. 下篇预告

下一篇讲 **异常处理与日志系统**：业务异常映射、全局处理器、logging 模块、结构化日志、日志收集。

---

**延伸阅读**：
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [bcrypt 论文](https://www.usenix.org/legacy/events/usenix99/provos/provos.pdf)
- [JWT 官方文档](https://jwt.io/)
- [PyJWT 文档](https://pyjwt.readthedocs.io/)
- [MySQL 事务隔离级别](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html)
