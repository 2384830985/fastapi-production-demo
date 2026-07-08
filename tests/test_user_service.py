"""Service 层单元测试：mock Repository，测业务逻辑。

不连数据库，速度快，隔离性好。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from app.schema.user import UserCreate, UserUpdate, UserInDB  # noqa: E402
from app.service.user_service import (  # noqa: E402
    UserService,
    UserAlreadyExistsError,
    UserNotFoundError,
    hash_password,
    verify_password,
)


# ── 密码哈希工具测试 ────────────────────────────────────
class TestPasswordHashing:
    """密码哈希相关测试。"""

    def test_hash_password_returns_bcrypt_format(self):
        """哈希结果应是 $2b$ 格式。"""
        hashed = hash_password("secret123")
        assert hashed.startswith("$2b$12$")

    def test_hash_password_different_each_time(self):
        """相同密码每次哈希不同（盐不同）。"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_verify_password_correct(self):
        """正确密码应验证通过。"""
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_password_wrong(self):
        """错误密码应验证失败。"""
        hashed = hash_password("secret123")
        assert verify_password("wrong", hashed) is False

    def test_verify_password_invalid_hash(self):
        """无效哈希格式应返回 False（不抛异常）。"""
        assert verify_password("any", "not-a-valid-hash") is False


# ── UserService 单元测试 ────────────────────────────────
class TestUserServiceCreate:
    """create_user 业务逻辑测试。"""

    def test_create_user_success(self):
        """正常创建用户。"""
        repo = MagicMock()
        repo.get_by_username.return_value = None
        repo.add.return_value = UserInDB(id=1, username="alice", hashed_password="x")

        svc = UserService(repo)
        result = svc.create_user(UserCreate(username="alice", password="secret123"))

        assert result.username == "alice"
        assert result.id == 1
        repo.add.assert_called_once()
        # 密码被哈希（不是明文传给 repo）
        _, kwargs = repo.add.call_args
        assert kwargs["hashed_password"] != "secret123"
        assert kwargs["hashed_password"].startswith("$2b$12$")

    def test_create_user_duplicate_raises(self):
        """用户名已存在应抛 UserAlreadyExistsError。"""
        repo = MagicMock()
        repo.get_by_username.return_value = UserInDB(
            id=1, username="alice", hashed_password="x"
        )

        svc = UserService(repo)
        with pytest.raises(UserAlreadyExistsError):
            svc.create_user(UserCreate(username="alice", password="secret123"))

        # 不应调用 add
        repo.add.assert_not_called()

    def test_create_user_integrity_error_fallback(self):
        """并发场景：DB 唯一约束兜底。"""
        from sqlalchemy.exc import IntegrityError

        repo = MagicMock()
        repo.get_by_username.return_value = None  # 前置检查通过
        repo.add.side_effect = IntegrityError("stmt", "params", "orig")
        repo._db = MagicMock()

        svc = UserService(repo)
        with pytest.raises(UserAlreadyExistsError):
            svc.create_user(UserCreate(username="alice", password="secret123"))

        # 应该 rollback
        repo._db.rollback.assert_called_once()


class TestUserServiceGet:
    """get_user 业务逻辑测试。"""

    def test_get_user_success(self):
        """正常查询。"""
        repo = MagicMock()
        repo.get.return_value = UserInDB(id=1, username="alice", hashed_password="x")

        svc = UserService(repo)
        result = svc.get_user(1)

        assert result.id == 1
        assert result.username == "alice"

    def test_get_user_not_found_raises(self):
        """用户不存在应抛 UserNotFoundError。"""
        repo = MagicMock()
        repo.get.return_value = None

        svc = UserService(repo)
        with pytest.raises(UserNotFoundError):
            svc.get_user(999)


class TestUserServiceUpdate:
    """update_user 业务逻辑测试。"""

    def test_update_user_success(self):
        """正常更新。"""
        existing = UserInDB(id=1, username="alice", hashed_password="x")
        updated = UserInDB(id=1, username="alice_new", hashed_password="x")

        repo = MagicMock()
        repo.get.return_value = existing
        repo.update.return_value = updated
        repo.get_by_username.return_value = None  # 新用户名不冲突

        svc = UserService(repo)
        result = svc.update_user(1, UserUpdate(username="alice_new"))

        assert result.username == "alice_new"

    def test_update_user_not_found_raises(self):
        """用户不存在应抛异常。"""
        repo = MagicMock()
        repo.get.return_value = None

        svc = UserService(repo)
        with pytest.raises(UserNotFoundError):
            svc.update_user(999, UserUpdate(username="newname"))

    def test_update_user_username_conflict_raises(self):
        """改用户名时新名字冲突应抛 UserAlreadyExistsError。"""
        existing = UserInDB(id=1, username="alice", hashed_password="x")
        other = UserInDB(id=2, username="bob", hashed_password="x")

        repo = MagicMock()
        repo.get.return_value = existing
        repo.get_by_username.return_value = other  # 新名字已存在

        svc = UserService(repo)
        with pytest.raises(UserAlreadyExistsError):
            svc.update_user(1, UserUpdate(username="bob"))

    def test_update_user_password_gets_hashed(self):
        """更新密码时应该哈希。"""
        existing = UserInDB(id=1, username="alice", hashed_password="old")
        updated = UserInDB(id=1, username="alice", hashed_password="new")

        repo = MagicMock()
        repo.get.return_value = existing
        repo.update.return_value = updated
        repo.get_by_username.return_value = None

        svc = UserService(repo)
        svc.update_user(1, UserUpdate(password="newpass123"))

        _, kwargs = repo.update.call_args
        assert kwargs["hashed_password"] != "newpass123"
        assert kwargs["hashed_password"].startswith("$2b$12$")


class TestUserServiceDelete:
    """delete_user 业务逻辑测试。"""

    def test_delete_user_success(self):
        """正常删除。"""
        repo = MagicMock()
        repo.delete.return_value = True

        svc = UserService(repo)
        svc.delete_user(1)
        repo.delete.assert_called_once_with(1)

    def test_delete_user_not_found_raises(self):
        """用户不存在应抛异常。"""
        repo = MagicMock()
        repo.delete.return_value = False

        svc = UserService(repo)
        with pytest.raises(UserNotFoundError):
            svc.delete_user(999)


class TestUserServiceAuthenticate:
    """authenticate_user 登录认证测试。"""

    def test_authenticate_success(self):
        """用户名密码正确应返回 UserOut。"""
        hashed = hash_password("secret123")
        repo = MagicMock()
        repo.get_by_username.return_value = UserInDB(
            id=1, username="alice", hashed_password=hashed
        )

        svc = UserService(repo)
        result = svc.authenticate_user("alice", "secret123")
        assert result is not None
        assert result.username == "alice"

    def test_authenticate_user_not_found_returns_none(self):
        """用户不存在返回 None（不区分原因，防爆破）。"""
        repo = MagicMock()
        repo.get_by_username.return_value = None

        svc = UserService(repo)
        assert svc.authenticate_user("ghost", "any") is None

    def test_authenticate_wrong_password_returns_none(self):
        """密码错误返回 None。"""
        hashed = hash_password("secret123")
        repo = MagicMock()
        repo.get_by_username.return_value = UserInDB(
            id=1, username="alice", hashed_password=hashed
        )

        svc = UserService(repo)
        assert svc.authenticate_user("alice", "wrong") is None
