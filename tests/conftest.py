"""pytest 公共 fixture：所有测试文件共享。

提供：
- 测试用 db session（in-memory SQLite，速度快）
- 测试用 client
- 测试用 token
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path（必须在 import app 之前）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 测试前必须设置 SECRET_KEY，否则 JWT 签发会 fail-fast
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "test")  # 不实际连，仅占位

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.models import User  # noqa: E402,F401  # 触发模型注册
from main import app  # noqa: E402


# ── 测试数据库（SQLite in-memory，每个测试函数独立）──────
@pytest.fixture
def db_session():
    """每个测试函数独立的 in-memory SQLite session。

    速度快（不用连 MySQL），隔离性好（互不影响）。
    """
    # SQLite in-memory，连接保持打开才能共享数据
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── 测试客户端（用测试 db）──────────────────────────────
@pytest.fixture
def client(db_session):
    """TestClient，db 依赖被替换为测试 session。"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # session 由 fixture 关闭

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── 种子用户 + token ────────────────────────────────────
@pytest.fixture
def seed_user(db_session):
    """创建一个测试用户，返回 UserInDB。"""
    from app.service.user_service import UserService
    from app.schema.user import UserCreate

    svc = UserService.from_db(db_session)
    user = svc.create_user(UserCreate(username="alice", password="secret123"))
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(client, seed_user):
    """登录拿 token，返回带 Authorization 的 headers。"""
    r = client.post(
        "/token",
        json={"username": "alice", "password": "secret123"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
