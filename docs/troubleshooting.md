# 故障排查
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


## 启动问题

### 问题 1：`ModuleNotFoundError: No module named 'xxx'`

**原因**：依赖未安装或虚拟环境未激活。

**解决**：
```bash
# 激活虚拟环境
source env/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证
pip list | grep fastapi
```

### 问题 2：`ERROR 2002 (HY000): Can't connect to local MySQL server`

**原因**：MySQL 未启动。

**解决**：
```bash
# 检查 MySQL 状态
brew services list | grep mysql

# 启动
brew services start mysql

# 验证
mysql -u root -p -e "SELECT 1;"
```

### 问题 3：`ERROR 1045 (28000): Access denied for user 'root'@'localhost'`

**原因**：密码错误。

**解决**：重置 root 密码
```bash
# 1. 停 MySQL
brew services stop mysql

# 2. skip-grant-tables 启动
/usr/local/opt/mysql/bin/mysqld_safe --skip-grant-tables --skip-networking &

# 3. 重置密码
mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password'; FLUSH PRIVILEGES;"

# 4. 重启
mysqladmin -u root shutdown
brew services start mysql
```

### 问题 4：`Authentication plugin 'caching_sha2_password' is not supported`

**原因**：MySQL 9.x 默认用 `caching_sha2_password`，老驱动不支持。

**解决**：用 PyMySQL（本项目已用）
```bash
pip install pymysql
# DATABASE_URL 用 mysql+pymysql://...
```

---

## 数据库问题

### 问题 5：`Unknown database 'testdb'`

**原因**：数据库不存在。

**解决**：
```bash
mysql -u root -p -e "CREATE DATABASE testdb DEFAULT CHARACTER SET utf8mb4;"
```

### 问题 6：`Invalid MySQL server downgrade: Cannot downgrade from 90300 to 80410`

**原因**：MySQL 9.x 的数据目录被 8.x 读取，不能降级。

**解决**：
1. 备份需要的数据库（如 `mysqldump`）
2. 停 MySQL：`brew services stop mysql`
3. 删除数据目录：`rm -rf /usr/local/var/mysql/*`
4. 重新初始化：`brew services start mysql`
5. 重置 root 密码

### 问题 7：`'Session' object has no attribute 'scalar_one_or_none'`

**原因**：SQLAlchemy 1.x 写法，2.0 已废弃。

**解决**：用 `db.scalars(stmt).one_or_none()`
```python
# ❌ SQLAlchemy 1.x
user = db.scalar_one_or_none(select(User).where(...))

# ✅ SQLAlchemy 2.0
user = db.scalars(select(User).where(...)).one_or_none()
```

### 问题 8：`(trapped) error reading bcrypt version`

**原因**：passlib 1.7.4 与 bcrypt 4.x+ 不兼容。

**解决**：本项目已弃用 passlib，直接用 bcrypt
```bash
pip uninstall passlib
```

---

## Alembic 问题

### 问题 9：`alembic` 命令找不到

**解决**：
```bash
source env/bin/activate
# 或
python -m alembic upgrade head
```

### 问题 10：autogenerate 没识别到模型变化

**排查**：
1. `app/models/__init__.py` 是否导入新模型
2. `alembic/env.py` 是否 `import app.models`
3. `target_metadata = Base.metadata` 是否设置

### 问题 11：`Can't locate revision identified by 'xxx'`

**原因**：迁移文件被删除但数据库记录了该版本。

**解决**：
```bash
# 查看数据库中的版本
mysql -u root -p testdb -e "SELECT * FROM alembic_version;"

# 手动清空版本记录
mysql -u root -p testdb -e "DELETE FROM alembic_version;"

# 重新标记当前版本
alembic stamp head
```

### 问题 12：迁移失败，数据库残留

**解决**：
```bash
# 1. 查看当前版本
alembic current

# 2. 手动修复数据库（删残留表/列）

# 3. 标记版本
alembic stamp <revision_id>

# 4. 继续
alembic upgrade head
```

---

## 运行时问题

### 问题 13：端口被占用 `Address already in use`

**解决**：
```bash
# 查端口占用
lsof -i :8000

# 杀进程
lsof -ti :8000 | xargs kill -9

# 或换端口
python -m uvicorn main:app --port 8001
```

### 问题 14：`passlib` warning 持续刷屏

**原因**：passlib 与新版 bcrypt 不兼容。

**解决**：本项目已弃用 passlib，如果还有警告：
```bash
pip uninstall passlib
```

### 问题 15：日志看不到

**排查**：
```bash
# 1. 确认 LOG_LEVEL
echo $LOG_LEVEL
# 或 .env 里的值

# 2. 设为 DEBUG 看详细日志
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload

# 3. 确认日志输出到 stdout（不是文件）
# app/logger.py 配置 stream=sys.stdout
```

### 问题 16：CORS 错误

**原因**：未配置 CORS。

**解决**：在 `main.py` 加
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Docker 问题

### 问题 17：`docker compose up` 报错 `port is already allocated`

**解决**：
```bash
# 查 3306 占用
lsof -i :3306

# 停本地 MySQL
brew services stop mysql

# 或改 docker-compose.yml 端口映射
ports:
  - "3307:3306"  # 宿主机 3307 映射容器 3306
```

### 问题 18：容器起来但应用连不上 DB

**排查**：
```bash
# 1. 看日志
docker compose logs app

# 2. 进容器看环境变量
docker compose exec app env | grep DB_

# 3. 测试网络
docker compose exec app ping mysql

# 4. 如果 DB_HOST=localhost 改为 mysql（服务名）
```

### 问题 19：迁移在容器里执行失败

**原因**：容器内未安装 alembic 或路径问题。

**解决**：
```bash
# 确认镜像里有 alembic
docker compose exec app which alembic

# 用 python -m
docker compose exec app python -m alembic upgrade head
```

---

## 测试问题

### 问题 20：测试报 `IntegrityError: Duplicate entry`

**原因**：之前测试残留数据。

**解决**：
```bash
# 测试前清表
mysql -u root -p123456 -e "USE testdb; TRUNCATE TABLE users;"

# 再跑测试
python tests/test_api.py
```

### 问题 21：测试报 `httpx` 未安装

**解决**：
```bash
pip install httpx
```

---

## 性能问题

### 问题 22：接口响应慢

**排查**：
1. 开 SQLAlchemy echo 看慢 SQL
   ```python
   engine = create_engine(DATABASE_URL, echo=True)
   ```
2. 检查是否有 N+1 查询
3. 加索引（看 EXPLAIN）
4. 加分页（避免一次查全表）

### 问题 23：连接池耗尽

**症状**：`QueuePool limit of size X overflow Y reached`

**解决**：
```python
# app/db.py 加大连接池
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

---

## 调试技巧

### 1. 启用 SQL 日志

```python
# app/db.py
engine = create_engine(DATABASE_URL, echo=True)
```

### 2. 交互式调试

```bash
python -i
>>> from app.db import SessionLocal
>>> from app.models.user import User
>>> db = SessionLocal()
>>> db.query(User).all()
```

### 3. Swagger 在线测试

http://127.0.0.1:8000/docs 可以直接发请求，看请求/响应详情。

### 4. 查看数据库

```bash
mysql -u root -p testdb
mysql> SELECT * FROM users;
mysql> SHOW PROCESSLIST;  # 看连接
mysql> SHOW STATUS LIKE 'Threads%';  # 看线程
```

### 5. 容器内调试

```bash
# 进容器
docker compose exec app bash

# 容器内跑 Python
python -c "from app.db import engine; print(engine.url)"
```
