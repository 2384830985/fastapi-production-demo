"""ORM 模型层：用 SQLAlchemy 定义数据库表结构。

与 Schema 层的区别：
- Schema (Pydantic): 用于 API 数据校验和序列化，不接触数据库
- Model  (SQLAlchemy): 用于 ORM 映射数据库表，不直接返回给前端
"""
# 导入 User 模型，触发 Base.metadata 注册（main.py 启动时建表依赖此导入）
from .user import User

__all__ = ["User"]
