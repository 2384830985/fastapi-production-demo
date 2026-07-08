"""Alembic 迁移环境配置。

改造点：
1. 从 .env 读取数据库 URL（不硬编码）
2. 引入项目的 Base.metadata，支持 autogenerate
3. 让 Alembic 知道所有 ORM 模型
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv()

# 引入项目数据库配置和 Base
import os
from app.db import DATABASE_URL, Base
# 导入所有 ORM 模型，确保 metadata 注册
import app.models  # noqa: F401

# Alembic 配置对象（读取 alembic.ini）
config = context.config

# 用项目 DATABASE_URL 覆盖 alembic.ini 里的配置
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 关键：把项目 Base.metadata 给 Alembic，autogenerate 才能识别模型变化
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本但不连数据库。

    用法：alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 比较类型和 server_default，让 autogenerate 更精确
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连数据库执行迁移。

    用法：alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
