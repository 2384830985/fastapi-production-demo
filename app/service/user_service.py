"""用户业务服务：封装业务规则。

- 密码使用 bcrypt 哈希后存储，不保留明文。
- 业务异常统一抛出，由 API 层捕获并转为 HTTP 响应。
- 控制事务边界：Repository 不 commit，Service 负责 commit/rollback。
"""
from __future__ import annotations

# Optional 标注可空类型（3.9 兼容写法，等价于 X | None）
from typing import Optional

# bcrypt 是业界推荐的密码哈希算法库
# 直接用官方 bcrypt 包，不用 passlib（passlib 1.7.4 与 bcrypt 4.x+ 不兼容会持续报 warning）
# - gensalt(rounds=12): 生成盐值，rounds=12 是推荐工作因子（约 250ms/次）
# - hashpw(password, salt): 返回哈希字符串
# - checkpw(password, hashed): 常量时间比对，防时序攻击
import bcrypt

# IntegrityError：SQLAlchemy 的唯一约束冲突等数据库完整性错误
# 当 INSERT/UPDATE 触发 UNIQUE 约束时抛出，用于并发兜底
from sqlalchemy.exc import IntegrityError

# Repository 层：数据访问
# - UserRepo 是数据仓库类，需要传入 db session
from app.repository import UserRepo
# Schema 层：数据模型
# - UserCreate/UserUpdate: 请求体模型（service 接收的参数）
# - UserOut: 对外响应模型（service 返回给 API 层的）
# - UserInDB: 内部存储模型（含哈希密码，service 内部用）
from app.schema.user import UserCreate, UserOut, UserUpdate, Page
# 数据库会话依赖
from app.db import get_db
# FastAPI 依赖注入
from fastapi import Depends
# Session 类型注解
from sqlalchemy.orm import Session
# 日志
from app.logger import get_logger

logger = get_logger(__name__)


# ── 密码哈希工具函数 ──────────────────────────────────────
def hash_password(plain_password: str) -> str:
    """把明文密码哈希为 bcrypt 字符串。

    返回值形如 '$2b$12$...'（共 60 字符），包含算法、工作因子、盐、哈希值。
    """
    # bcrypt 要求输入是 bytes，密码用 utf-8 编码
    password_bytes = plain_password.encode("utf-8")
    # rounds=12 是平衡安全与性能的推荐值（每增加 1，耗时翻倍）
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    # 返回 str 便于存数据库（VARCHAR(128)）
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码是否匹配 bcrypt 哈希。

    内部用常量时间比对，防时序攻击。
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # hashed_password 格式异常（不是合法 bcrypt 字符串）
        return False


# ── 自定义业务异常 ────────────────────────────────────────
# 这些异常会被 API 层捕获并映射为 HTTP 状态码
class UserAlreadyExistsError(Exception):
    """用户名已存在（应映射为 HTTP 409 Conflict）。"""


class UserNotFoundError(Exception):
    """用户不存在（应映射为 HTTP 404 Not Found）。"""


class UserService:
    """用户业务服务，依赖 UserRepo。

    职责：
    1. 执行业务规则校验（用户名唯一等）
    2. 把明文密码哈希后传给 Repository
    3. 控制事务边界（commit / rollback）
    4. 把 UserInDB 转成 UserOut 返回（屏蔽密码字段）
    """

    def __init__(self, repo: UserRepo) -> None:
        self._repo = repo

    @classmethod
    def from_db(cls, db: Session) -> "UserService":
        """工厂方法：从 db session 创建 UserService。"""
        return cls(UserRepo(db))

    # ── 内部事务辅助 ─────────────────────────────────────
    def _commit(self) -> None:
        """提交事务，失败时自动 rollback 并抛出。

        把 commit 集中在这里，方便统一加日志或监控。
        """
        try:
            self._repo._db.commit()
        except Exception:
            self._repo._db.rollback()
            raise

    # ── 查询（只读，无事务） ──────────────────────────────
    def list_users(self, skip: int = 0, limit: int = 20) -> Page[UserOut]:
        """分页返回用户列表（不含密码）。"""
        users = self._repo.list_all(skip=skip, limit=limit)
        total = self._repo.count()
        return Page[UserOut](
            items=[UserOut.model_validate(u) for u in users],
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total,
        )

    def get_user(self, user_id: int) -> UserOut:
        """按 id 查询单个用户，不存在抛 UserNotFoundError。"""
        user = self._repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"用户 id={user_id} 不存在")
        return UserOut.model_validate(user)

    # ── 创建（写事务） ────────────────────────────────────
    def create_user(self, payload: UserCreate) -> UserOut:
        """创建用户。

        流程：
        1. 校验用户名不重复（友好提示）
        2. 把明文密码哈希（绝不存明文）
        3. 调用 Repository 写入，提交事务
        4. 并发场景下数据库 unique 约束兜底，转业务异常
        """
        # 业务规则：用户名唯一（前置检查给出友好错误信息）
        if self._repo.get_by_username(payload.username) is not None:
            logger.warning("创建用户失败：用户名已存在 username=%s", payload.username)
            raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

        # 关键：密码哈希，bcrypt 会自动加盐
        hashed = hash_password(payload.password)

        try:
            user = self._repo.add(
                username=payload.username,
                hashed_password=hashed,
            )
            self._commit()  # 提交事务
        except IntegrityError:
            # 并发场景：两个请求同时通过前置检查，数据库 unique 约束兜底
            self._repo._db.rollback()
            logger.warning("创建用户触发唯一约束 username=%s", payload.username)
            raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

        logger.info("用户创建成功 id=%s username=%s", user.id, user.username)
        return UserOut.model_validate(user)

    # ── 更新（写事务） ────────────────────────────────────
    def update_user(self, user_id: int, payload: UserUpdate) -> UserOut:
        """更新用户，仅更新传入的字段。"""
        existing = self._repo.get(user_id)
        if existing is None:
            raise UserNotFoundError(f"用户 id={user_id} 不存在")

        # 若改用户名，需校验新用户名不冲突
        if payload.username and payload.username != existing.username:
            if self._repo.get_by_username(payload.username) is not None:
                raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

        # 若传了密码，先哈希
        new_hashed = None
        if payload.password:
            new_hashed = hash_password(payload.password)

        try:
            updated = self._repo.update(
                user_id=user_id,
                username=payload.username,
                hashed_password=new_hashed,
            )
            self._commit()  # 提交事务
        except IntegrityError:
            self._repo._db.rollback()
            logger.warning("更新用户触发唯一约束 user_id=%s", user_id)
            raise UserAlreadyExistsError(f"用户名 '{payload.username}' 已存在")

        logger.info("用户更新成功 id=%s", user_id)
        return UserOut.model_validate(updated)

    # ── 删除（写事务） ────────────────────────────────────
    def delete_user(self, user_id: int) -> None:
        """删除用户，不存在抛 UserNotFoundError。"""
        if not self._repo.delete(user_id):
            raise UserNotFoundError(f"用户 id={user_id} 不存在")
        self._commit()  # 提交事务
        logger.info("用户删除成功 id=%s", user_id)

    # ── 密码校验（用于登录等场景） ────────────────────────
    def verify_password(self, username: str, plain_password: str) -> bool:
        """校验明文密码是否匹配哈希。

        供登录接口调用：先按用户名查出存储的哈希，再 verify 比对。
        """
        user = self._repo.get_by_username(username)
        if user is None:
            return False
        # 调用模块级 verify_password 做常量时间比对
        return verify_password(plain_password, user.hashed_password)

    def authenticate_user(self, username: str, plain_password: str) -> Optional[UserOut]:
        """登录认证：用户名 + 密码。

        Returns:
            认证成功返回 UserOut，用户不存在或密码错误返回 None。
        两种失败统一返回 None，避免暴露"用户名不存在"等差异化提示，防爆破。
        """
        user = self._repo.get_by_username(username)
        if user is None:
            return None
        if not verify_password(plain_password, user.hashed_password):
            logger.warning("登录失败：密码错误 username=%s", username)
            return None
        logger.info("登录成功 username=%s", username)
        return UserOut.model_validate(user)


# ── 依赖注入工厂 ──────────────────────────────────────────
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """依赖注入：每个请求创建一个 UserService，传入独立的 db session。

    FastAPI 会先调用 get_db 拿到 session，再传给本函数。
    请求结束 get_db 自动关闭 session。
    """
    return UserService.from_db(db)
