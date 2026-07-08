# 安全设计
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


## 密码安全

### 哈希算法

使用 **bcrypt**（业界推荐），不用 MD5/SHA1/SHA256 等不带盐的算法。

| 算法 | 安全性 | 用途 |
|------|--------|------|
| bcrypt | ✅ 推荐 | 密码哈希 |
| argon2 | ✅ 更强（但依赖多） | 密码哈希 |
| PBKDF2 | ⚠️ 可接受 | 密码哈希 |
| MD5/SHA1 | ❌ 已破 | 不可用于密码 |
| SHA256 | ❌ 太快 | 不可用于密码（可用于文件指纹） |

### 为什么选 bcrypt

- **自带盐值**：每次哈希结果不同，防彩虹表
- **可调工作因子**：算力提升时增加 rounds 保持安全
- **抗 GPU/ASIC 攻击**：基于 Blowfish 算法，内存访问模式不友好
- **业界标准**：OWASP 推荐

### 实现代码

```python
# app/service/user_service.py
import bcrypt

def hash_password(plain_password: str) -> str:
    """密码哈希，rounds=12 是推荐工作因子。"""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)  # 约 250ms/次
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")  # 形如 '$2b$12$...'

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """常量时间比对，防时序攻击。"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
```

### rounds 选择

| rounds | 耗时 | 适用场景 |
|--------|------|---------|
| 10 | ~100ms | 测试 |
| 12 | ~250ms | **推荐**，生产 |
| 14 | ~1s | 高安全要求 |
| 16 | ~4s | 极端安全（影响体验） |

每增加 1，耗时翻倍。平衡安全与体验，12 是业界推荐。

### 为什么不用 passlib

- passlib 1.7.4 与 bcrypt 4.x+ 不兼容（调用 `bcrypt.__about__.__version__` 已移除）
- 持续刷 warning 日志
- 直接用 bcrypt 官方包更轻量、API 更直接

### 密码存储

- 数据库列 `hashed_password` 仅存哈希值（`$2b$12$...` 格式，约 60 字符）
- VARCHAR(128) 留余量，未来换算法不需要改 schema
- **绝不存明文**

### 密码不返回

- `UserOut` Schema 不含 `hashed_password` 字段
- API 用 `response_model=UserOut`，FastAPI 自动过滤未声明字段
- 双保险：即使 service 误返回 `UserInDB`，也会被过滤

### 密码不进日志

```python
# ✅ 正确
logger.info("用户创建成功 id=%s username=%s", user.id, user.username)

# ❌ 错误（密码进日志）
logger.info("用户创建成功 password=%s", payload.password)
```

---

## 配置安全

### 环境变量管理

- 敏感信息（密码、key）走 `.env`
- `.env` 已在 `.gitignore` 排除，不进 git
- 部署时用系统环境变量或容器 secret，不依赖 `.env`

### 配置优先级

```
系统环境变量 > .env 文件 > 代码默认值
```

`load_dotenv()` **不会覆盖**已存在的系统环境变量，所以：
- 本地开发：写 `.env`
- 生产：在容器/k8s 设置环境变量

### 常见敏感配置

| 配置 | 示例 | 存放位置 |
|------|------|---------|
| DB_PASSWORD | 123456 | .env / 系统环境变量 |
| JWT_SECRET | random_str | .env / 系统环境变量 |
| API_KEY | xxx | .env / 系统环境变量 |
| SMTP_PASSWORD | xxx | .env / 系统环境变量 |

### .env 文件示例

```bash
# .env（git忽略）
DB_USER=root
DB_PASSWORD=your_strong_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testdb
LOG_LEVEL=INFO
```

---

## SQL 注入防护

### 使用 ORM 参数化查询

```python
# ✅ 安全（ORM 自动参数化）
user = db.scalars(select(User).where(User.id == user_id)).one_or_none()

# ✅ 安全（text + 参数）
db.execute(text("SELECT 1"))

# ❌ 危险（字符串拼接）
db.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### Pydantic 自动校验

路径参数 `user_id: int` 会自动校验类型，传非数字直接 422，不会到 SQL 层。

---

## 异常信息泄露防护

### 500 错误不暴露细节

```python
@app.exception_handler(Exception)
async def handle_unexpected_error(_, exc: Exception):
    logger.exception("未处理异常: %s", exc)  # 服务端记完整堆栈
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},  # 客户端只看到通用错误
    )
```

**不要**返回 `str(exc)`，可能包含：
- SQL 语句
- 文件路径
- 内部异常堆栈
- 第三方库敏感信息

---

## 传输安全

### HTTPS

- 生产必须 HTTPS，否则密码明文传输
- 用 Nginx 反向代理 + Let's Encrypt
- 或 Cloudflare 免费 SSL

### 配置示例

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    # ...
}
```

---

## API 安全（待完善）

### 鉴权（TODO）

当前接口无鉴权，生产需加：

- **JWT 登录**：POST /auth/login 返回 token，后续请求带 `Authorization: Bearer <token>`
- **接口权限**：基于角色的访问控制（RBAC）

### 限流（TODO）

防止暴力破解和 DDoS：

- 用 `slowapi` 或 API Gateway
- 登录接口：每 IP 每分钟 10 次
- 创建接口：每用户每分钟 30 次

### CORS（TODO）

前后端分离时配置：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

⚠️ 生产环境 `allow_origins` 不要用 `["*"]`。

---

## 依赖安全

### 定期更新

```bash
# 检查过期依赖
pip list --outdated

# 安全漏洞扫描
pip install pip-audit
pip-audit
```

### 锁定版本

生产用 lock 文件：
- `pip-compile`（pip-tools）
- 或 `poetry.lock`

---

## 日志安全

### 不记录敏感信息

```python
# ❌ 危险
logger.info("登录请求 password=%s", password)
logger.info("数据库连接 %s", DATABASE_URL)  # 含密码

# ✅ 安全
logger.info("登录请求 username=%s", username)
logger.info("数据库连接 host=%s db=%s", DB_HOST, DB_NAME)
```

### 日志保留策略

- 生产日志保留 30-90 天
- 用 logrotate 或 ELK/Loki 管理
- 含 PII 数据需脱敏（如手机号、邮箱）

---

## 安全检查清单

部署前检查：

- [ ] 所有密码走环境变量，不在代码
- [ ] `.env` 在 `.gitignore`
- [ ] 密码用 bcrypt 哈希（不是明文）
- [ ] 响应不含 `hashed_password` 字段
- [ ] 500 错误不返回内部细节
- [ ] 启用 HTTPS
- [ ] 加鉴权（JWT）
- [ ] 加限流
- [ ] 配置 CORS（不用 `*`）
- [ ] 依赖无已知漏洞（pip-audit）
- [ ] 日志不含敏感信息
- [ ] 数据库备份策略就位
