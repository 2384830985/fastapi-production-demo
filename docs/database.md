# 数据库设计
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


## 表结构

### users 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| username | VARCHAR(20) | UNIQUE, NOT NULL, INDEX | 用户名 |
| hashed_password | VARCHAR(128) | NOT NULL | bcrypt 哈希密码 |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

### DDL

```sql
CREATE TABLE users (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    username        VARCHAR(20)  NOT NULL,
    hashed_password VARCHAR(128) NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username),
    KEY idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 连接配置

通过环境变量配置（`app/db.py`）：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| DB_USER | root | 用户名 |
| DB_PASSWORD | (无) | 密码 |
| DB_HOST | localhost | 主机 |
| DB_PORT | 3306 | 端口 |
| DB_NAME | testdb | 数据库名 |

URL 格式：
```
mysql+pymysql://user:password@host:port/dbname?charset=utf8mb4
```

## 连接池

| 参数 | 值 | 说明 |
|------|-----|------|
| pool_pre_ping | True | 借出前 ping，避免失效连接 |
| pool_recycle | 3600 | 每小时回收（MySQL 默认 8h 超时） |
| pool_size | 5（默认） | 连接池大小，生产建议 10-20 |
| max_overflow | 10（默认） | 突发时额外连接，生产建议 20 |

## ORM 模型

文件：`app/models/user.py`

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[str] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
```

### SQLAlchemy 2.0 写法说明

- `Mapped[类型]`：类型注解
- `mapped_column(...)`：列配置
- `server_default=func.current_timestamp()`：让 MySQL 填默认值（DDL 带 DEFAULT）
- `onupdate=func.current_timestamp()`：更新时 MySQL 自动刷新

## Alembic 迁移

### 初始化（已完成）

```bash
alembic init alembic
```

### 配置（已完成）

- `alembic.ini`：主配置
- `alembic/env.py`：从 .env 读 URL，引入 Base.metadata

### 加新字段流程

```bash
# 1. 修改 app/models/user.py
class User(Base):
    ...
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)

# 2. 生成迁移
alembic revision --autogenerate -m "add email column"
# 生成 alembic/versions/xxx_add_email_column.py

# 3. 检查迁移脚本
# 打开生成的 .py 文件，确认 upgrade/downgrade 正确

# 4. 执行迁移
alembic upgrade head

# 5. 验证
mysql -u root -p testdb -e "DESC users;"
```

### 迁移脚本结构

```python
"""add email column

Revision ID: abc123
Revises: 45dbf61ddb4a
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(100), unique=True, nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'email')
```

### 常用命令

| 命令 | 作用 |
|------|------|
| `alembic current` | 当前版本 |
| `alembic history` | 迁移历史 |
| `alembic upgrade head` | 升级到最新 |
| `alembic upgrade +1` | 升级一个版本 |
| `alembic downgrade -1` | 回滚一个版本 |
| `alembic downgrade base` | 回滚到初始 |
| `alembic revision --autogenerate -m "msg"` | 自动生成迁移 |
| `alembic revision -m "msg"` | 生成空迁移（手写） |
| `alembic upgrade head --sql` | 离线生成 SQL |

### Docker 中执行迁移

```bash
# 启动后执行迁移
docker compose exec app alembic upgrade head

# 或在启动脚本里自动执行
# 修改 Dockerfile CMD:
# CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

### 已有数据库接入 Alembic

如果数据库已有表但没用 Alembic：

```bash
alembic stamp head  # 标记当前为最新，不执行 SQL
```

之后改模型生成的迁移才能正常 upgrade。

## 常见问题

### Q: autogenerate 没识别到变化？

A:
1. 确认 `app/models/__init__.py` 导入了新模型
2. 确认 `alembic/env.py` 的 `target_metadata = Base.metadata`
3. autogenerate 不识别：
   - 表名变更
   - 服务端 DEFAULT 变化（用 `compare_server_default=True`）
   - 类型细微变化（用 `compare_type=True`）

### Q: 迁移失败怎么处理？

A:
```bash
# 1. 查看当前版本
alembic current

# 2. 手动修复数据库（如删掉残留的表/列）

# 3. 标记当前版本（不执行 SQL）
alembic stamp <revision_id>

# 4. 继续升级
alembic upgrade head
```

### Q: 多人协作时迁移冲突？

A:
- 拉代码后先 `alembic upgrade head`
- 生成的迁移文件**不要**改文件名（revision id）
- 合并冲突时保留两个迁移，按时间顺序排列 `down_revision`
