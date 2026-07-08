# 14 - 常见错误与调试技巧
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 14 篇（附录 D）。本篇收录 25 个项目实战中常见的错误及排查方法，按主题分组，每个错误附原因和解决方案。

## 你将学到

- 启动/数据库/ORM/FastAPI/Pydantic/Docker/Alembic/CI 常见错误
- 错误原因分析
- 排查步骤
- 调试技巧

---

## 📋 错误分类

| 类别 | 题数 |
|------|------|
| 启动错误 | 4 |
| 数据库错误 | 5 |
| ORM/SQLAlchemy 错误 | 3 |
| FastAPI 错误 | 4 |
| Docker 错误 | 4 |
| Alembic 错误 | 3 |
| CI/CD 错误 | 2 |

---

## 一、启动错误

### E1：`ModuleNotFoundError: No module named 'fastapi'`

**原因**：依赖未装或虚拟环境未激活。

**解决**：
```bash
source env/bin/activate
pip install -r requirements.txt
```

**排查**：
```bash
which python  # 确认是 env/bin/python
pip list | grep fastapi
```

---

### E2：`ImportError: cannot import name 'X' from 'Y'`

**原因**：版本不匹配或循环 import。

**解决**：
1. 检查版本：`pip show Y`
2. 升级：`pip install --upgrade Y`
3. 循环 import：用 `from __future__ import annotations` + 字符串注解

---

### E3：`RuntimeError: SECRET_KEY 未配置，无法签发 JWT`

**原因**：项目启动时 `SECRET_KEY` 环境变量未设置。

**解决**：
```bash
# .env 文件
SECRET_KEY=your_strong_random_key

# 或命令行
SECRET_KEY=xxx python -m uvicorn main:app --reload
```

**生成强密钥**：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### E4：`ERROR: Address already in use: 8000`

**原因**：8000 端口被占用。

**解决**：
```bash
# 查端口占用
lsof -i :8000

# 杀进程
lsof -ti :8000 | xargs kill -9

# 或换端口
python -m uvicorn main:app --port 8001
```

---

## 二、数据库错误

### E5：`ERROR 2002 (HY000): Can't connect to local MySQL server`

**原因**：MySQL 未启动。

**解决**：
```bash
# macOS
brew services start mysql

# Linux
sudo systemctl start mysql

# Docker
docker compose up -d mysql
```

**验证**：
```bash
mysqladmin -u root -p ping
```

---

### E6：`ERROR 1045 (28000): Access denied for user 'root'@'localhost'`

**原因**：密码错误。

**解决**：重置 root 密码
```bash
brew services stop mysql
mysqld_safe --skip-grant-tables --skip-networking &
mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_pwd'; FLUSH PRIVILEGES;"
mysqladmin -u root shutdown
brew services start mysql
```

---

### E7：`Authentication plugin 'caching_sha2_password' is not supported`

**原因**：MySQL 9.x 默认用 `caching_sha2_password`，老驱动不支持。

**解决**：用 PyMySQL（本项目已用）
```bash
pip install pymysql
# DATABASE_URL 用 mysql+pymysql://...
```

---

### E8：`Unknown database 'testdb'`

**原因**：数据库不存在。

**解决**：
```bash
mysql -u root -p -e "CREATE DATABASE testdb DEFAULT CHARACTER SET utf8mb4;"
```

---

### E9：`MySQL server has gone away`

**原因**：连接失效（MySQL `wait_timeout` 关闭了空闲连接）。

**解决**：开启 `pool_pre_ping`
```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 借出前 ping
    pool_recycle=3600,   # 每小时回收
)
```

---

## 三、ORM/SQLAlchemy 错误

### E10：`'Session' object has no attribute 'scalar_one_or_none'`

**原因**：SQLAlchemy 1.x 写法，2.0 已废弃。

**解决**：用 `db.scalars(stmt).one_or_none()`
```python
# ❌ 1.x
user = db.scalar_one_or_none(select(User).where(...))

# ✅ 2.0
user = db.scalars(select(User).where(...)).one_or_none()
```

---

### E11：`IntegrityError: Duplicate entry 'alice' for key 'users.username'`

**原因**：UNIQUE 约束冲突。

**解决**：捕获 `IntegrityError`，转业务异常
```python
try:
    user = self._repo.add(...)
    self._commit()
except IntegrityError:
    self._repo._db.rollback()
    raise UserAlreadyExistsError(...)
```

---

### E12：`PendingRollbackError: This Session's transaction has been rolled back`

**原因**：上次事务失败后没 rollback，又用了同一个 session。

**解决**：异常时立即 rollback
```python
try:
    db.add(user)
    db.commit()
except Exception:
    db.rollback()  # 关键！
    raise
```

---

## 四、FastAPI 错误

### E13：`422 Unprocessable Entity`

**原因**：请求体不符合 Pydantic 模型。

**排查**：
- 看响应 `detail` 字段，定位哪个字段校验失败
- 检查 `min_length` / `max_length` / `pattern` 约束
- 检查必填字段是否传了

**示例**：
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 6 characters"
    }
  ]
}
```
说明 `password` 长度不够 6。

---

### E14：`401 Unauthorized`

**原因**：JWT token 缺失、过期或无效。

**排查**：
1. 请求头是否带 `Authorization: Bearer <token>`
2. token 是否过期（看 `exp` 字段）
3. SECRET_KEY 是否一致

**调试**：
```bash
# 解码 JWT 看 payload（不验签）
echo "<token>" | cut -d. -f2 | base64 -d

# 或用 Python
import jwt
print(jwt.decode(token, options={"verify_signature": False}))
```

---

### E15：`405 Method Not Allowed`

**原因**：HTTP 方法不匹配（如 POST 接口用 GET 访问）。

**解决**：检查路由装饰器
```python
@router.post("")  # 只接受 POST
@router.get("")   # 只接受 GET
```

---

### E16：路由匹配错误（`/users/me` 返回 422）

**原因**：路由顺序错误，动态路由在前。

**解决**：静态路径在前，动态路径在后
```python
@router.get("/me")           # ✅ 先注册
@router.get("/{user_id}")    # 后注册
```

---

## 五、Docker 错误

### E17：`Cannot connect to the Docker daemon`

**原因**：Docker Desktop 未启动。

**解决**：
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

---

### E18：`port is already allocated`

**原因**：宿主机端口被占用。

**解决**：
```bash
# 查占用
lsof -i :3306

# 停本地 MySQL
brew services stop mysql

# 或改 compose 端口映射
ports:
  - "3307:3306"  # 宿主机 3307 → 容器 3306
```

---

### E19：容器起来但 app 连不上 DB

**排查**：
```bash
# 1. 看日志
docker compose logs app

# 2. 看环境变量
docker compose exec app env | grep DB_

# 3. 测试网络
docker compose exec app ping mysql

# 4. DB_HOST 应该是 mysql（service name），不是 localhost
```

---

### E20：`alembic` 命令在容器里找不到

**原因**：镜像里没装 alembic，或 PATH 问题。

**解决**：
```bash
# 确认镜像里有 alembic
docker compose exec app which alembic

# 用 python -m
docker compose exec app python -m alembic upgrade head
```

---

## 六、Alembic 错误

### E21：`Can't locate revision identified by 'xxx'`

**原因**：数据库 `alembic_version` 记录了 `xxx`，但 `versions/` 目录没有这个迁移文件。

**解决**：
```bash
# 1. 查看数据库当前版本
mysql -u root -p testdb -e "SELECT * FROM alembic_version;"

# 2. 手动清空版本记录
mysql -u root -p testdb -e "DELETE FROM alembic_version;"

# 3. 重新标记当前版本
alembic stamp head
```

---

### E22：autogenerate 没识别到模型变化

**排查**：
1. `app/models/__init__.py` 是否导入新模型
2. `alembic/env.py` 是否 `import app.models`
3. `target_metadata = Base.metadata` 是否设置

```python
# alembic/env.py
import app.models  # 关键！触发注册
target_metadata = Base.metadata
```

---

### E23：迁移失败，数据库残留

**解决**：
```bash
# 1. 查看当前版本
alembic current

# 2. 手动修复数据库（删残留表/列）

# 3. 标记版本（不执行 SQL）
alembic stamp <revision_id>

# 4. 继续
alembic upgrade head
```

---

## 七、CI/CD 错误

### E24：CI 里 MySQL service 起不来

**原因**：healthcheck 配置错误或密码错。

**排查**：
```yaml
services:
  mysql:
    image: mysql:8.4
    env:
      MYSQL_ROOT_PASSWORD: 123456  # 与应用 DB_PASSWORD 一致
    ports: ["3306:3306"]
    options: >-
      --health-cmd="mysqladmin ping -h localhost -u root -p123456"
      --health-interval=10s
      --health-retries=10
```

**关键**：
- `health-cmd` 要带 `-u root -p123456`
- `--health-retries=10` 给 MySQL 足够启动时间

---

### E25：Docker push 失败 `denied: requested access to the resource is denied`

**原因**：Docker Hub 登录凭证错或没权限。

**解决**：
1. 检查 GitHub Secrets：`DOCKER_USERNAME` / `DOCKER_PASSWORD`
2. 用 access token 而非密码（Docker Hub → Account → Security → New Access Token）
3. 确认仓库存在且公开/私有设置正确

---

## 🛠️ 通用调试技巧

### 技巧 1：启用 SQL 日志

```python
# app/db.py
engine = create_engine(DATABASE_URL, echo=True)
```

所有 SQL 打印到 stderr，调试慢查询神器。

### 技巧 2：交互式调试

```bash
python -i
>>> from app.db import SessionLocal
>>> from app.models.user import User
>>> db = SessionLocal()
>>> db.query(User).all()
```

### 技巧 3：Swagger 在线测试

http://127.0.0.1:8000/docs 能直接发请求，看请求/响应详情。

### 技巧 4：看数据库

```bash
mysql -u root -p testdb
mysql> SELECT * FROM users;
mysql> SHOW PROCESSLIST;  # 看连接
mysql> SHOW STATUS LIKE 'Threads%';
```

### 技巧 5：容器内调试

```bash
# 进容器
docker compose exec app bash

# 容器内跑 Python
python -c "from app.db import engine; print(engine.url)"
```

### 技巧 6：调试 JWT

```python
import jwt

# 解码（不验签）
payload = jwt.decode(token, options={"verify_signature": False})
print(payload)
# {'sub': '1', 'exp': 1699999999, 'iat': 1699999999}
```

### 技巧 7：调试 Pydantic 校验

```python
from app.schema.user import UserCreate

try:
    UserCreate(username="ab", password="123")
except Exception as e:
    print(e.errors())
# [{'type': 'string_too_short', 'loc': ('username',), ...}]
```

### 技巧 8：调试 AST 校验

```bash
# 直接跑校验脚本
python scripts/check.py

# 看具体哪个文件哪行
# ❌ app/repository/user_repo.py:127 Repository 不应调用 db.commit()
```

---

## 📋 错误排查流程

遇到错误时的标准流程：

```
1. 看完整错误信息（不要只看最后一行）
   ↓
2. 定位错误类型（ImportError? IntegrityError?）
   ↓
3. 查本文档对应章节
   ↓
4. 看日志（应用日志、Docker 日志、MySQL 日志）
   ↓
5. 用调试技巧（交互式、SQL 日志、Swagger）
   ↓
6. 解决后记笔记（避免重复踩坑）
```

---

## 📊 错误速查表

| 错误信息 | 章节 | 一句话解决 |
|---------|------|----------|
| `ModuleNotFoundError` | 启动 | 激活 venv + 装依赖 |
| `Address already in use` | 启动 | `lsof -ti:8000 \| xargs kill` |
| `Can't connect to MySQL` | 数据库 | 启动 MySQL 服务 |
| `Access denied` | 数据库 | 重置 root 密码 |
| `caching_sha2_password` | 数据库 | 用 PyMySQL 驱动 |
| `MySQL server has gone away` | 数据库 | `pool_pre_ping=True` |
| `Session has no attribute` | ORM | 用 `db.scalars(stmt).one_or_none()` |
| `Duplicate entry` | ORM | 捕获 `IntegrityError` |
| `422 Unprocessable` | FastAPI | 看响应 detail 定位字段 |
| `401 Unauthorized` | FastAPI | 检查 JWT token |
| `405 Method Not Allowed` | FastAPI | 检查 HTTP 方法 |
| 路由 422 | FastAPI | 静态路径在前 |
| `Cannot connect to Docker` | Docker | 启动 Docker Desktop |
| `port already allocated` | Docker | 停本地服务或换端口 |
| 容器连不上 DB | Docker | `DB_HOST` 用 service name |
| `Can't locate revision` | Alembic | `DELETE FROM alembic_version; stamp head` |
| autogenerate 没识别 | Alembic | 检查 `import app.models` |

---

## 🎯 预防胜于治疗

### 1. 加日志

```python
logger.info("关键操作 user_id=%s", user_id)
logger.exception("失败: %s", exc)
```

### 2. 加监控

- 健康检查 `/health`
- Prometheus metrics
- 异常告警

### 3. 加测试

```bash
python tests/test_api.py  # 改完代码就跑
```

### 4. 加 CI

每次 push 自动跑 lint + test，问题早发现。

### 5. 加备份

```bash
# 数据库定时备份
mysqldump -u root -p testdb > backup_$(date +%Y%m%d).sql
```

---

## ✅ 学完后

读完本文档，你应该能：

- [ ] 5 秒内定位错误类型
- [ ] 知道每个错误的原因
- [ ] 知道排查步骤
- [ ] 会用调试技巧
- [ ] 能预防常见错误

---

**系列完结**：本系列共 14 篇文章，覆盖项目所有知识点。回到 [总索引](README.md) 复习。
