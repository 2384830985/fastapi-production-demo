# 05 - Alembic 数据库迁移原理与实践
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 5 篇。本篇讲清楚 Alembic 的工作原理、autogenerate、版本图、生产迁移策略。

## 你将学到

- 为什么需要数据库迁移工具
- Alembic 的工作原理
- `autogenerate` 怎么识别模型变化
- 版本图（revision graph）与 `down_revision`
- `stamp`、`upgrade`、`downgrade` 的区别
- 多人协作时的迁移冲突解决
- 生产环境迁移策略

---

## 1. 为什么需要迁移工具

### 1.1 不用迁移工具的痛

```python
# 开发时建表
Base.metadata.create_all(engine)  # 只建不存在的表
```

**问题**：加字段怎么办？

```python
class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]  # ← 新增字段
```

`create_all` **不会修改已有表**，新字段不会加到 `users` 表。

### 1.2 手动 SQL 的问题

```sql
ALTER TABLE users ADD COLUMN email VARCHAR(100);
```

问题：
- 多人协作时谁先执行？冲突怎么办？
- 测试/生产环境怎么同步？
- 回滚怎么做？
- 哪些 SQL 已执行过？

### 1.3 迁移工具的作用

Alembic 解决以上问题：

| 功能 | 说明 |
|------|------|
| 版本控制 | 数据库当前版本记录在 `alembic_version` 表 |
| 自动生成 | 对比 ORM 模型与数据库，生成迁移脚本 |
| 升级/回滚 | `upgrade head` / `downgrade -1` |
| 多人协作 | 迁移脚本提交 git，团队共享 |

---

## 2. Alembic 工作原理

### 2.1 核心组件

```
项目
├── alembic.ini              # 主配置
├── alembic/
│   ├── env.py               # 迁移环境（连接 DB、加载模型）
│   ├── script.py.mako       # 迁移脚本模板
│   └── versions/            # 迁移脚本目录
│       ├── 001_init.py
│       ├── 002_add_email.py
│       └── 003_add_index.py
└── app/models/              # ORM 模型
```

### 2.2 工作流程

```
1. 改 ORM 模型（app/models/user.py 加字段）
        ↓
2. alembic revision --autogenerate -m "add email"
   - Alembic 连数据库，对比 ORM 与实际表结构
   - 生成 alembic/versions/xxx_add_email.py
        ↓
3. 检查迁移脚本（autogenerate 不一定 100% 准确）
        ↓
4. alembic upgrade head
   - 执行 upgrade() 函数
   - 更新 alembic_version 表
        ↓
5. 数据库 schema 更新完成
```

### 2.3 `alembic_version` 表

Alembic 在数据库里建一张 `alembic_version` 表：

```sql
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- 当前版本
SELECT * FROM alembic_version;
-- version_num
-- --------------
-- 45dbf61ddb4a
```

`alembic upgrade head` 时：
1. 读 `alembic_version` 表，知道当前版本
2. 找出当前版本到 `head` 之间的所有迁移
3. 按顺序执行每个迁移的 `upgrade()` 函数
4. 每执行一个，更新 `alembic_version` 表

---

## 3. `env.py` 配置详解

### 3.1 本项目的 env.py

```python
# alembic/env.py
from dotenv import load_dotenv
load_dotenv()

from app.db import DATABASE_URL, Base
import app.models  # 触发 ORM 模型注册

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata  # 关键：让 autogenerate 识别模型
```

### 3.2 关键配置

| 配置 | 作用 |
|------|------|
| `DATABASE_URL` | 从 `.env` 读取，不硬编码 |
| `import app.models` | 触发 ORM 模型注册到 `Base.metadata` |
| `target_metadata = Base.metadata` | autogenerate 用这个 metadata 对比 |

### 3.3 `compare_type` 和 `compare_server_default`

```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    compare_type=True,           # 检测列类型变化
    compare_server_default=True, # 检测默认值变化
)
```

默认 Alembic 不检测列类型变化，加这两个参数让 autogenerate 更精确。

---

## 4. 迁移脚本结构

### 4.1 自动生成的脚本

```python
"""add email column

Revision ID: abc123def456
Revises: 45dbf61ddb4a
Create Date: 2026-07-07 12:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "abc123def456"
down_revision = "45dbf61ddb4a"  # 上一个版本
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email")
```

### 4.2 关键字段

| 字段 | 说明 |
|------|------|
| `revision` | 当前迁移的唯一 ID（自动生成） |
| `down_revision` | 上一个迁移的 ID（构成版本链） |
| `upgrade()` | 升级时执行 |
| `downgrade()` | 回滚时执行 |

### 4.3 版本图（revision graph）

```
(base) ← 001 ← 002 ← 003 ← ... ← head
```

每个迁移通过 `down_revision` 指向上一个，形成链。`alembic upgrade head` 从当前版本沿链走到 `head`。

---

## 5. `op` 操作详解

### 5.1 表操作

```python
# 建表
op.create_table(
    "users",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.String(20), nullable=False),
)

# 删表
op.drop_table("users")

# 改表名
op.rename_table("users", "user_accounts")
```

### 5.2 列操作

```python
# 加列
op.add_column("users", sa.Column("email", sa.String(100)))

# 删列
op.drop_column("users", "email")

# 改列名
op.alter_column("users", "name", new_column_name="username")

# 改列类型
op.alter_column("users", "age", type_=sa.Float)

# 改默认值
op.alter_column("users", "is_active", server_default=sa.text("true"))
```

### 5.3 索引操作

```python
# 建索引
op.create_index("idx_users_email", "users", ["email"], unique=True)

# 删索引
op.drop_index("idx_users_email", table_name="users")
```

### 5.4 数据迁移

```python
def upgrade():
    # 加字段
    op.add_column("users", sa.Column("full_name", sa.String(100)))

    # 回填数据
    op.execute("UPDATE users SET full_name = CONCAT(first_name, ' ', last_name)")

    # 删旧字段
    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")
```

**关键**：数据迁移 SQL 必须在 `upgrade()` 里，不能依赖应用代码。

---

## 6. 常用命令

### 6.1 命令速查

| 命令 | 作用 |
|------|------|
| `alembic init alembic` | 初始化 |
| `alembic revision -m "msg"` | 生成空迁移（手写） |
| `alembic revision --autogenerate -m "msg"` | 自动生成迁移 |
| `alembic upgrade head` | 升级到最新 |
| `alembic upgrade +1` | 升级一个版本 |
| `alembic upgrade abc123` | 升级到指定版本 |
| `alembic downgrade -1` | 回滚一个版本 |
| `alembic downgrade base` | 回滚到初始 |
| `alembic current` | 查看当前版本 |
| `alembic history` | 迁移历史 |
| `alembic stamp head` | 标记当前为最新（不执行 SQL） |
| `alembic upgrade head --sql` | 离线模式，生成 SQL 不执行 |

### 6.2 `stamp head` 详解

```bash
# 数据库已有表，没用过 Alembic，现在要接入
alembic stamp head
```

`stamp head` 把 `head` 版本写入 `alembic_version` 表，**但不执行任何 SQL**。

之后改模型生成的迁移才能正常 `upgrade`。

### 6.3 离线模式 `--sql`

```bash
alembic upgrade head --sql > migration.sql
```

生成纯 SQL 脚本，不连数据库。适合：
- 生产环境 DBA 审核后手动执行
- 离线环境（无数据库连接）

---

## 7. `autogenerate` 的局限

### 7.1 能识别的变化

| 变化 | 识别 |
|------|------|
| 新增表 | ✅ |
| 删除表 | ✅ |
| 新增列 | ✅ |
| 删除列 | ✅ |
| 改列类型 | ✅（需 `compare_type=True`） |
| 改默认值 | ✅（需 `compare_server_default=True`） |
| 新增索引 | ✅ |
| 删除索引 | ✅ |

### 7.2 不能识别的变化

| 变化 | 不识别 |
|------|--------|
| 改表名 | ❌（会当作删表 + 建表） |
| 改列名 | ❌（会当作删列 + 加列，**丢数据**） |
| 数据迁移 | ❌（autogenerate 不动数据） |
| 复杂约束 | ⚠️ 部分 |

### 7.3 改列名怎么办

```python
# 手动改迁移脚本
def upgrade():
    # 用 alter_column 改名，不丢数据
    op.alter_column("users", "name", new_column_name="username")

def downgrade():
    op.alter_column("users", "username", new_column_name="name")
```

### 7.4 检查迁移脚本（必做）

**autogenerate 生成的脚本一定要检查**：

```bash
alembic revision --autogenerate -m "add email"
# 打开 alembic/versions/xxx_add_email.py
# 检查 upgrade() 和 downgrade() 是否正确
```

特别是：
- 删列操作：确认不是改名被误识别
- 数据类型：`String(20)` 长度对不对
- `nullable`：是否符合预期
- `downgrade`：能否真正回滚

---

## 8. 多人协作冲突

### 8.1 冲突场景

```
A 改了模型，生成迁移 001_add_email
B 同时改了模型，生成迁移 001_add_age
两人都 push，git 合并后：
    001_add_email（down_revision = base）
    001_add_age（down_revision = base）
    两条分支，head 不唯一
```

### 8.2 解决方案

让其中一个迁移接在另一个后面：

```python
# 修改 001_add_age.py
revision = "abc_age"
down_revision = "xyz_email"  # 改成接在 add_email 后面
```

或者用 `alembic merge`：

```bash
alembic merge -m "merge branches" abc_email abc_age
# 生成一个 merge 迁移，down_revision 指向两个分支
```

### 8.3 预防措施

1. **拉代码再生成迁移**：避免冲突
2. **迁移文件不改名**：revision id 是唯一的
3. **小步快跑**：一个改动一个迁移，避免大迁移
4. **及时合并**：避免长期分叉

---

## 9. 本项目实战

### 9.1 初始化（已完成）

```bash
alembic init alembic
```

### 9.2 改造 env.py（已完成）

```python
# 关键三行
load_dotenv()
from app.db import DATABASE_URL, Base
import app.models
config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata
```

### 9.3 已有数据库接入（已完成）

```bash
alembic stamp head  # 标记当前为最新
```

### 9.4 加新字段完整流程

```bash
# 1. 改模型
vim app/models/user.py
# 加：email: Mapped[Optional[str]] = mapped_column(String(100), unique=True)

# 2. 生成迁移
alembic revision --autogenerate -m "add email column"

# 3. 检查迁移脚本
cat alembic/versions/xxx_add_email_column.py
# 确认 upgrade: op.add_column("users", sa.Column("email", ...))
# 确认 downgrade: op.drop_column("users", "email")

# 4. 执行迁移
alembic upgrade head

# 5. 验证
mysql -u root -p testdb -e "DESC users;"

# 6. 提交 git
git add alembic/versions/xxx_add_email_column.py
git commit -m "feat: 加 email 字段"
```

### 9.5 Docker 中执行迁移

```bash
# 启动后手动迁移
docker compose exec app alembic upgrade head

# 或在 docker-compose.yml 启动命令里自动迁移
command: sh -c "alembic upgrade head && gunicorn main:app ..."
```

---

## 10. 生产环境迁移策略

### 10.1 迁移前准备

1. **备份数据库**：
   ```bash
   mysqldump -u root -p testdb > backup_$(date +%Y%m%d).sql
   ```

2. **测试环境验证**：先在测试库跑一遍

3. **检查迁移脚本**：特别是数据迁移

4. **评估停机时间**：大表加索引可能锁表

### 10.2 安全迁移原则

**向前兼容**：迁移后应用能正常运行一段时间

```python
# 错误：直接删字段（旧代码会报错）
def upgrade():
    op.drop_column("users", "old_field")

# 正确：分两步
# 迁移 1：加新字段
def upgrade():
    op.add_column("users", sa.Column("new_field", sa.String(100)))

# 应用发布后，确认没人用 old_field

# 迁移 2：删旧字段
def upgrade():
    op.drop_column("users", "old_field")
```

### 10.3 大表迁移技巧

**加索引**：MySQL 加索引会锁表

```python
# 用 ALGORITHM=INPLACE 避免锁表（MySQL 5.6+）
op.execute(
    "CREATE INDEX idx_users_email ON users (email) ALGORITHM=INPLACE, LOCK=NONE"
)
```

**改列类型**：可能锁表+重建表

```python
# 用 pt-online-schema-change 工具
# 或分步迁移：加新列 → 双写 → 切换 → 删旧列
```

### 10.4 回滚策略

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade abc123

# 回滚到初始
alembic downgrade base
```

**注意**：回滚可能丢数据！特别是：
- 删字段：字段里的数据没了
- 改列类型：精度可能损失

回滚前一定要备份。

---

## 11. 常见问题

### Q1：`alembic upgrade head` 报 `Can't locate revision identified by 'xxx'`

<details>
<summary>查看答案</summary>

数据库 `alembic_version` 表记录了 `xxx`，但 `versions/` 目录里找不到这个迁移文件（可能被删了）。

解决：
```bash
# 查看数据库当前版本
mysql -u root -p testdb -e "SELECT * FROM alembic_version;"

# 手动清空版本记录
mysql -u root -p testdb -e "DELETE FROM alembic_version;"

# 重新标记当前版本
alembic stamp head
```
</details>

### Q2：autogenerate 没识别到模型变化

<details>
<summary>查看答案</summary>

检查：
1. `app/models/__init__.py` 是否导入新模型
2. `alembic/env.py` 是否 `import app.models`
3. `target_metadata = Base.metadata` 是否设置
</details>

### Q3：迁移执行失败，数据库残留

<details>
<summary>查看答案</summary>

```bash
# 1. 查看当前版本
alembic current

# 2. 手动修复数据库（删残留表/列）

# 3. 标记版本（不执行 SQL）
alembic stamp <revision_id>

# 4. 继续
alembic upgrade head
```
</details>

### Q4：`alembic` 命令找不到

<details>
<summary>查看答案</summary>

```bash
source env/bin/activate
# 或
python -m alembic upgrade head
```
</details>

---

## 12. 小结

| 概念 | 关键点 |
|------|--------|
| `alembic_version` 表 | 记录数据库当前版本 |
| `revision` / `down_revision` | 构成版本链 |
| `target_metadata` | autogenerate 对比的元数据 |
| `stamp head` | 标记当前为最新，不执行 SQL |
| `upgrade head` | 升级到最新 |
| `downgrade -1` | 回滚一个版本 |
| `--sql` | 离线模式，生成 SQL 不执行 |
| `compare_type=True` | 检测列类型变化 |

**最佳实践**：
- ✅ autogenerate 后必检查脚本
- ✅ 改列名用手动 `alter_column`
- ✅ 数据迁移在 `upgrade()` 里用 `op.execute`
- ✅ 生产迁移前备份
- ✅ 大表用 `ALGORITHM=INPLACE`
- ✅ 向前兼容设计（分步迁移）

## 13. 下篇预告

下一篇讲 **四层架构设计原理**：依赖方向、解耦、Repository 模式、DTO 转换、为什么这么分层。

---

**延伸阅读**：
- [Alembic 官方文档](https://alembic.sqlalchemy.org/en/latest/)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Alembic Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
