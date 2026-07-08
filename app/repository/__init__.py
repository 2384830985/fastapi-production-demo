"""Repository 层：数据访问层，封装所有持久化逻辑。

使用 SQLAlchemy 2.0 ORM 操作 MySQL。
对 Service 层暴露 UserRepo，需要传入 db session。
"""
from .user_repo import UserRepo

__all__ = ["UserRepo"]
