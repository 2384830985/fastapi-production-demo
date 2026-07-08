"""用户数据仓库：用 SQLAlchemy ORM 操作 MySQL。

封装所有数据库操作，对 Service 层暴露 UserInDB（Pydantic）模型，
Service 层无需感知 ORM 模型 User 的存在。

事务边界设计：
- Repository 只负责 add/flush/delete，不 commit
- Service 层负责 commit 或 rollback（控制事务边界）
- 这样多个 Repository 操作可组合为一个事务（如转账场景）
"""
from __future__ import annotations

# Optional 标注可空类型
from typing import Optional

# SQLAlchemy 的 select 用来构造查询
from sqlalchemy import select
# Session 是数据库会话，所有 CRUD 都通过它执行
from sqlalchemy.orm import Session

# ORM 模型 User（对应数据库 users 表）
from app.models.user import User
# Schema 模型 UserInDB（Repository 对外暴露的数据格式）
from app.schema.user import UserInDB


class UserRepo:
    """用户仓库（MySQL 版）。每个请求传入一个独立的 db session。

    注意：本类不调用 db.commit()，事务由 Service 层控制。
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── 辅助：ORM 转 Schema ───────────────────────────────
    @staticmethod
    def _to_schema(user: User) -> UserInDB:
        """ORM 对象转 Pydantic 模型，隔离 ORM 与上层。"""
        return UserInDB(
            id=user.id,
            username=user.username,
            hashed_password=user.hashed_password,
        )

    # ── 基础查询（只读，无需事务） ─────────────────────────
    def get(self, user_id: int) -> Optional[UserInDB]:
        """按 id 查询用户。"""
        # SQLAlchemy 2.0 写法：db.scalars(stmt) 返回 ScalarResult
        # .one_or_none() 返回单条或 None，多于一条会抛异常
        user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
        return self._to_schema(user) if user else None

    def get_by_username(self, username: str) -> Optional[UserInDB]:
        """按用户名查询用户。"""
        user = self._db.scalars(select(User).where(User.username == username)).one_or_none()
        return self._to_schema(user) if user else None

    def list_all(self, skip: int = 0, limit: int = 20) -> list[UserInDB]:
        """分页返回用户列表。

        Args:
            skip: 跳过前 N 条（offset）
            limit: 最多返回 N 条
        """
        # offset + limit 实现 MySQL LIMIT offset, count
        users = self._db.scalars(
            select(User).offset(skip).limit(limit)
        ).all()
        return [self._to_schema(u) for u in users]

    def count(self) -> int:
        """返回用户总数（用于分页元数据）。"""
        from sqlalchemy import func
        return self._db.scalar(select(func.count()).select_from(User)) or 0

    # ── 写操作（不 commit，由 Service 控制） ──────────────
    def add(self, username: str, hashed_password: str) -> UserInDB:
        """新增用户到会话（不提交）。

        调用方（Service）负责 commit 或 rollback。
        flush() 把对象写入会话，触发自增 id 分配和默认值填充，
        但不真正写库，commit 后才持久化。
        """
        user = User(username=username, hashed_password=hashed_password)
        self._db.add(user)        # 加入会话
        self._db.flush()          # 触发 INSERT，分配 id 和默认值（不 commit）
        return self._to_schema(user)

    def update(
        self,
        user_id: int,
        username: Optional[str] = None,
        hashed_password: Optional[str] = None,
    ) -> Optional[UserInDB]:
        """更新用户：仅更新传入的字段。不提交。

        返回更新后的对象，找不到返回 None。
        调用方（Service）负责 commit 或 rollback。
        """
        user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
        if user is None:
            return None

        # 仅更新非 None 字段
        if username is not None:
            user.username = username
        if hashed_password is not None:
            user.hashed_password = hashed_password

        self._db.flush()  # 触发 UPDATE（不 commit）
        return self._to_schema(user)

    def delete(self, user_id: int) -> bool:
        """从会话标记删除用户。不提交。

        成功返回 True，不存在返回 False。
        调用方（Service）负责 commit 或 rollback。
        """
        user = self._db.scalars(select(User).where(User.id == user_id)).one_or_none()
        if user is None:
            return False
        self._db.delete(user)   # 标记删除
        self._db.flush()        # 触发 DELETE（不 commit）
        return True
