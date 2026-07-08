"""用户 ORM 模型：对应 MySQL 中的 users 表。"""
from __future__ import annotations

# SQLAlchemy 列类型
# - Integer: 整数
# - String: 定长/变长字符串
# - Boolean: 布尔
# - DateTime: 日期时间
from sqlalchemy import Integer, String, DateTime, func

# Mapped / mapped_column 是 SQLAlchemy 2.0 的新写法
# - Mapped[类型] 用类型注解声明列类型
# - mapped_column(...) 配置列属性（主键、长度、默认值等）
from sqlalchemy.orm import Mapped, mapped_column

# Base 是所有 ORM 模型的基类，定义在 app/db.py
from app.db import Base


class User(Base):
    """用户表 ORM 模型。"""

    __tablename__ = "users"  # 数据库表名

    # 主键，自增（MySQL AUTO_INCREMENT）
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 用户名：varchar(20)，唯一索引（用户名不能重复）
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    # 哈希密码：varchar(128)，bcrypt 哈希结果约 60 字符，留余量到 128
    # nullable=False 表示不允许 NULL
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)

    # 创建时间：默认当前时间（用 server_default 让 MySQL 自己填）
    created_at: Mapped[str] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False,
    )

    # 更新时间：每次更新自动刷新为当前时间
    updated_at: Mapped[str] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """调试友好输出。"""
        return f"<User id={self.id} username={self.username!r}>"
