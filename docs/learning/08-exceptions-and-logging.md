# 08 - 异常处理与日志系统

> 系列文章第 8 篇。本篇讲清楚业务异常设计、全局异常处理器、logging 模块、结构化日志、生产日志策略。

## 你将学到

- 业务异常与 HTTP 异常解耦
- FastAPI 全局异常处理器
- 异常映射的过粗陷阱（`IntegrityError` 不一定都是 409）
- 错误响应脱敏：为什么不能 `str(exc)` 直接返回
- Python `logging` 模块原理
- 结构化日志格式
- 日志级别选择
- 容器化日志收集

---

## 1. 异常处理设计

### 1.1 为什么要设计异常

考虑两种错误处理方式：

**返回错误码**：

```python
def create_user(payload):
    if exists(payload.username):
        return {"error": "用户名已存在", "code": 409}
    ...
```

问题：
- 调用方必须检查返回值
- 容易忘记检查
- 错误传播路径不清晰

**抛异常**：

```python
def create_user(payload):
    if exists(payload.username):
        raise UserAlreadyExistsError(...)
    ...
```

优势：
- 不处理会自动传播
- 错误路径清晰
- 业务逻辑与错误处理分离

### 1.2 业务异常 vs HTTP 异常

```python
# ❌ Service 层抛 HTTP 异常
from fastapi import HTTPException
class UserService:
    def create_user(self, payload):
        if exists(payload.username):
            raise HTTPException(409, "用户名已存在")
```

问题：
- Service 层绑定 HTTP 概念
- Service 无法被 CLI/定时任务复用
- 业务错误码（409）写在业务层

```python
# ✅ Service 层抛业务异常
class UserAlreadyExistsError(Exception):
    """用户名已存在"""

class UserService:
    def create_user(self, payload):
        if exists(payload.username):
            raise UserAlreadyExistsError(...)
```

业务异常继承 `Exception`，不知道 HTTP。API 层负责翻译。

### 1.3 本项目的异常体系

```python
# app/service/user_service.py
class UserAlreadyExistsError(Exception):
    """用户名已存在（应映射为 HTTP 409 Conflict）"""

class UserNotFoundError(Exception):
    """用户不存在（应映射为 HTTP 404 Not Found）"""
```

```python
# app/service/auth_service.py（JWT 鉴权）
# 鉴权失败直接抛 HTTPException，因为这是 HTTP 层的关心点
raise HTTPException(
    status_code=401,
    detail="无效或过期的凭证",
    headers={"WWW-Authenticate": "Bearer"},
)
```

**区别**：
- 业务异常：业务规则违反（用户名冲突、资源不存在）
- HTTP 异常：HTTP 协议层问题（未认证、无权限、参数错误）

---

## 2. 全局异常处理器

### 2.1 不用全局处理器的代码

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
        raise HTTPException(500, detail="内部错误")

@router.put("/{user_id}")
def update_user(user_id, payload, svc=Depends(...)):
    try:  # 重复 try/except
        return svc.update_user(user_id, payload)
    except UserAlreadyExistsError as e:
        raise HTTPException(409, detail=str(e))
    ...
```

每个路由重复 try/except，代码冗余。

### 2.2 全局处理器

```python
# app/exception_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(UserNotFoundError)
    async def handle_user_not_found(_: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UserAlreadyExistsError)
    async def handle_user_already_exists(_: Request, exc: UserAlreadyExistsError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError):
        logger.warning("数据库完整性约束错误: %s", exc)
        return JSONResponse(status_code=409, content={"detail": "数据冲突"})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
```

### 2.3 注册

```python
# main.py
from app.exception_handlers import register_exception_handlers

app = FastAPI(...)
register_exception_handlers(app)
```

### 2.4 路由变干净

```python
@router.post("")
def create_user(payload, svc=Depends(...)):
    return svc.create_user(payload)  # 无 try/except
```

业务异常直接抛，全局处理器统一处理。

### 2.5 处理器参数

```python
@app.exception_handler(UserNotFoundError)
async def handle(_: Request, exc: UserNotFoundError):
    ...
```

- `_: Request`：请求对象（可拿 URL、method 等）
- `exc: UserNotFoundError`：抛出的异常实例

### 2.6 异常映射表

| 业务异常 | HTTP | 触发场景 |
|---------|------|---------|
| `UserNotFoundError` | 404 | 用户不存在 |
| `UserAlreadyExistsError` | 409 | 用户名冲突 |
| `IntegrityError` | 409 | DB 完整性约束兜底（含唯一、外键、非空等） |
| `HTTPException(401)` | 401 | JWT 鉴权失败（token 过期/无效/缺失） |
| `RequestValidationError` | 422 | Pydantic 请求体校验失败（FastAPI 内置） |
| `Exception` | 500 | 未捕获异常兜底 |

**注意 `IntegrityError` 映射的过粗问题**：把所有 `IntegrityError` 都映射成 409 会掩盖外键约束、非空约束等其他错误。当前实现是 MVP 的折中，更严谨的做法是检查 `exc.orig` 的错误码：

```python
@app.exception_handler(IntegrityError)
async def handle_integrity_error(_, exc: IntegrityError):
    # MySQL 错误码：1062 唯一冲突，1452 外键约束，1048 非空
    code = getattr(exc.orig, "args", [None])[0]
    if code == 1062:
        return JSONResponse(409, {"detail": "数据冲突，可能违反唯一约束"})
    logger.exception("未处理的完整性约束错误: %s", exc)
    return JSONResponse(500, {"detail": "数据库约束错误"})
```

### 2.7 错误响应不暴露内部细节

500 错误、健康检查失败等场景下，**绝对不能**把 `str(exc)` 直接返回给客户端。

```python
# ❌ 危险：泄露数据库连接串、表名、SQL 等内部信息
@app.get("/health")
def health_check(db):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(503, {"detail": str(e)})  # ← 不要这样做

# ✅ 安全：只返回通用状态，详情记日志
@app.get("/health")
def health_check(db):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logger.error("健康检查数据库异常: %s", e)  # 服务端记录
        return JSONResponse(503, content={"status": "degraded", "db": "error"})
        # ↑ 客户端只看到通用状态，看不到内部错误
```

500 兜底同理：

```python
@app.exception_handler(Exception)
async def handle_unexpected_error(_, exc):
    logger.exception("未处理异常: %s", exc)  # 服务端记完整堆栈
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},  # 客户端只看到通用错误
    )
```

**安全考虑**：错误响应里不要带 SQL、文件路径、堆栈、内部 host 等信息。攻击者能通过这些信息推断系统架构、寻找攻击面。

### 2.8 FastAPI 内置异常

FastAPI 自动处理：
- `RequestValidationError` → 422（Pydantic 校验失败）
- `HTTPException` → 对应状态码
- `StarletteHTTPException` → 对应状态码

你只需处理业务异常和兜底 `Exception`。

---

## 3. Python `logging` 模块

### 3.1 为什么不用 `print`

| 维度 | print | logging |
|------|-------|---------|
| 级别 | 无 | DEBUG/INFO/WARNING/ERROR |
| 输出 | stdout | 文件/网络/任意 |
| 格式 | 固定 | 可配置 |
| 性能 | 差 | 好（异步、缓冲） |
| 关闭 | 改代码 | 改配置 |

### 3.2 logging 核心组件

```
Logger（记录器）
   ↓ 发出 LogRecord
Handler（处理器）
   ↓ 决定输出位置
Formatter（格式器）
   ↓ 决定格式
输出到 stdout/文件/网络
```

### 3.3 日志级别

| 级别 | 数值 | 适用场景 |
|------|------|---------|
| DEBUG | 10 | 详细调试信息 |
| INFO | 20 | 关键流程节点 |
| WARNING | 30 | 警告但不影响功能 |
| ERROR | 40 | 错误，影响当前操作 |
| CRITICAL | 50 | 严重错误，系统不可用 |

```python
logger.debug("查询用户 id=%s", user_id)
logger.info("用户创建成功 id=%s", user.id)
logger.warning("用户名冲突 username=%s", username)
logger.error("数据库连接失败: %s", exc)
logger.exception("未处理异常")  # 自动带堆栈
```

### 3.4 `logger.exception` vs `logger.error`

```python
try:
    do_something()
except Exception as e:
    logger.error("失败: %s", e)        # 只记错误消息
    logger.exception("失败: %s", e)    # 错误消息 + 完整堆栈
    logger.error("失败", exc_info=True) # 等价于 exception
```

异常处理里用 `logger.exception` 最方便。

### 3.5 本项目的日志配置

```python
# app/logger.py
import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,  # 输出到 stdout
        force=True,         # 覆盖已有配置
    )

    # 降低第三方库日志级别
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
```

### 3.6 获取 logger

```python
from app.logger import get_logger

logger = get_logger(__name__)  # 用模块名作 logger 名

logger.info("用户创建成功 id=%s", user.id)
```

`__name__` 是模块全名（如 `app.service.user_service`），日志里能看到是哪个模块输出的。

---

## 4. 结构化日志

### 4.1 本项目的日志格式

```
2026-07-07 17:21:35 | INFO    | app.service.user_service:161 | 用户创建成功 id=2 username=alice
       时间         级别              模块名:行号                    消息
```

### 4.2 格式说明

| 字段 | 占位符 | 说明 |
|------|--------|------|
| 时间 | `%(asctime)s` | 易读时间 |
| 级别 | `%(levelname)-7s` | 左对齐 7 字符 |
| 模块 | `%(name)s` | logger 名 |
| 行号 | `%(lineno)d` | 出错行号 |
| 消息 | `%(message)s` | 日志内容 |

### 4.3 为什么用 `key=value` 风格

```python
logger.info("用户创建成功 id=%s username=%s", user.id, user.username)
# 输出：用户创建成功 id=2 username=alice
```

而不是：

```python
logger.info(f"用户创建成功，用户ID是{user.id}，用户名是{user.username}")
# 输出：用户创建成功，用户ID是2，用户名是alice
```

`key=value` 优势：
- 易于 grep 过滤：`grep "username=alice" app.log`
- 易于日志系统解析（ELK/Loki）
- 字段边界清晰

### 4.4 用 `%` 不用 f-string

```python
# ✅ 推荐：用 % 占位符
logger.info("用户创建成功 id=%s username=%s", user.id, user.username)

# ❌ 不推荐：用 f-string
logger.info(f"用户创建成功 id={user.id} username={user.username}")
```

**原因**：
- `%` 是延迟格式化，日志级别不够时不格式化（性能好）
- f-string 总是格式化，即使日志被过滤

```python
# DEBUG 日志被过滤时
logger.debug("复杂计算 %s", expensive_calc())  # expensive_calc 仍会执行
# 实际上 logging 会先检查级别，不够就不调用参数
# 但 f-string 在传给 logger 前就执行了
```

### 4.5 JSON 结构化日志（生产推荐）

本项目的 `key=value` 格式人眼可读，但机器解析不如 JSON。生产可以用 `python-json-logger`：

```python
# pip install python-json-logger
from pythonjsonlogger import jsonlogger

formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
handler.setFormatter(formatter)

# 输出：
# {"asctime": "2026-07-07 17:21:35", "levelname": "INFO", "name": "app.service.user_service", "message": "用户创建成功"}
```

JSON 格式便于 ELK/Loki/CloudWatch 解析和查询。

---

## 5. 日志输出位置

### 5.1 stdout vs 文件

| 输出位置 | 优势 | 劣势 |
|---------|------|------|
| stdout | 容器自动收集，无需管理文件 | 进程退出日志丢失（除非收集） |
| 文件 | 持久化 | 需管理轮转、磁盘空间 |

### 5.2 为什么容器化用 stdout

```python
stream=sys.stdout
```

- **docker logs / kubectl logs 自动收集**
- **无需管理日志文件轮转**（Docker/k8s 负责）
- **可聚合**：对接 ELK、Loki、CloudWatch、DataDog 等

### 5.3 文件日志（非容器化）

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "/var/log/app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,  # 保留 5 个备份
)
```

`RotatingFileHandler` 按大小轮转，避免日志文件无限增长。

### 5.4 日志轮转策略

| 策略 | 工具 | 说明 |
|------|------|------|
| 按大小 | RotatingFileHandler | 超过 N MB 切割 |
| 按时间 | TimedRotatingFileHandler | 每天/每小时切割 |
| 容器 | Docker/k8s | 自动 |
| 系统 | logrotate | Linux 系统级 |

---

## 6. 日志级别使用规范

### 6.1 什么时候用什么级别

```python
# DEBUG：详细调试信息，生产关闭
logger.debug("查询 SQL: %s", stmt)
logger.debug("用户对象: %s", user.__dict__)

# INFO：关键流程节点，生产开启
logger.info("用户创建成功 id=%s username=%s", user.id, user.username)
logger.info("应用启动完成")

# WARNING：异常但不影响功能
logger.warning("用户名冲突 username=%s", username)
logger.warning("重试第 %s 次", retry_count)

# ERROR：错误，影响当前操作
logger.error("数据库连接失败: %s", exc)
logger.error("发送邮件失败 user_id=%s", user_id)

# CRITICAL：严重错误，系统不可用
logger.critical("数据库完全不可用")
```

### 6.2 本项目的日志示例

```python
# Service 层
def create_user(self, payload):
    if self._repo.get_by_username(payload.username):
        logger.warning("创建用户失败：用户名已存在 username=%s", payload.username)
        raise UserAlreadyExistsError(...)

    try:
        user = self._repo.add(...)
        self._commit()
    except IntegrityError:
        logger.warning("创建用户触发唯一约束 username=%s", payload.username)
        raise UserAlreadyExistsError(...)

    logger.info("用户创建成功 id=%s username=%s", user.id, user.username)
    return UserOut.model_validate(user)
```

### 6.3 日志级别配置

```bash
# 开发环境
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload

# 生产环境
LOG_LEVEL=INFO python -m uvicorn main:app
```

环境变量控制级别，代码不改。

---

## 7. 日志中不要记录什么

### 7.1 敏感信息

```python
# ❌ 危险
logger.info("登录请求 password=%s", password)
logger.info("数据库连接 %s", DATABASE_URL)  # 含密码
logger.info("用户 token=%s", token)
logger.info("信用卡号 %s", credit_card)

# ✅ 安全
logger.info("登录请求 username=%s", username)
logger.info("数据库连接 host=%s db=%s", DB_HOST, DB_NAME)
logger.info("用户登录成功 user_id=%s", user_id)
```

### 7.2 PII 数据脱敏

```python
def mask_email(email: str) -> str:
    """邮箱脱敏：alice@example.com → a***@example.com"""
    name, domain = email.split("@")
    return f"{name[0]}***@{domain}"

logger.info("用户邮箱 %s", mask_email(user.email))
```

### 7.3 大对象

```python
# ❌ 日志爆炸
logger.debug("响应体 %s", large_response.json())

# ✅ 只记关键信息
logger.debug("响应状态 %s 长度 %s", response.status_code, len(response.content))
```

---

## 8. 日志收集架构

### 8.1 单机

```
应用 → stdout → 文件 → logrotate
```

### 8.2 容器化

```
应用 → stdout → docker logs → docker logs driver
                              ↓
                          json-file / journald / fluentd
```

### 8.3 集群

```
应用 → stdout
       ↓
容器运行时收集
       ↓
日志代理（Fluent Bit / Filebeat）
       ↓
日志存储（Loki / Elasticsearch）
       ↓
日志查询（Grafana / Kibana）
```

### 8.4 告警

```
应用 → ERROR 日志
       ↓
日志代理匹配 ERROR
       ↓
告警系统（AlertManager / PagerDuty）
       ↓
通知值班人员
```

---

## 9. 自测题

### Q1：Service 层为什么抛业务异常而不抛 HTTPException？

<details>
<summary>查看答案</summary>

Service 层应该与 HTTP 解耦，可以被 CLI/定时任务/其他 Service 复用。HTTPException 是 HTTP 概念，绑定后降低复用性。
</details>

### Q2：500 错误为什么不返回 `str(exc)`？

<details>
<summary>查看答案</summary>

`str(exc)` 可能包含 SQL 语句、文件路径、数据库连接串等敏感信息。客户端只看到通用错误"服务器内部错误"，服务端日志记完整堆栈。
</details>

### Q3：为什么用 `logger.info("x=%s", x)` 而不是 `logger.info(f"x={x}")`？

<details>
<summary>查看答案</summary>

`%` 是延迟格式化，日志级别不够时不格式化（性能好）。f-string 总是格式化，即使日志被过滤。
</details>

### Q4：容器化部署为什么日志输出到 stdout？

<details>
<summary>查看答案</summary>

docker logs / kubectl logs 自动收集 stdout，无需管理日志文件轮转。可对接 ELK/Loki/CloudWatch 等日志系统。
</details>

---

## 10. 小结

| 概念 | 关键点 |
|------|--------|
| 业务异常 | 继承 Exception，不绑 HTTP |
| 全局异常处理器 | `@app.exception_handler` 注册 |
| 500 不暴露细节 | 安全考虑，只返回通用错误 |
| logging 组件 | Logger → Handler → Formatter |
| 日志级别 | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `logger.exception` | 自动带堆栈 |
| `%` 占位符 | 延迟格式化，性能好 |
| stdout 输出 | 容器化友好 |
| 不记敏感信息 | 密码、token、PII |

## 11. 下篇预告

下一篇讲 **Docker 容器化与 CI/CD**：多阶段构建、Compose、GitHub Actions、镜像缓存优化。

---

**延伸阅读**：
- [Python logging 文档](https://docs.python.org/3/library/logging.html)
- [FastAPI 异常处理](https://fastapi.tiangolo.com/zh/tutorial/handling-errors/)
- [python-json-logger](https://github.com/madzak/python-json-logger)
- [12-Factor App Logs](https://12factor.net/logs)
