"""接口冒烟测试：用 TestClient 直接打 API，不需要启动服务。

TestClient 内部用 httpx 发起请求，但走的是 ASGI 协议直接调用 app，
不需要真的监听端口，速度快、CI 友好。
"""
import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，便于直接 `python tests/test_api.py` 运行
# 否则 from main import app 会找不到模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 测试需要 SECRET_KEY 才能签发 JWT，本地未设置时给一个测试占位值
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

# TestClient 是 Starlette 提供的测试客户端，模拟 HTTP 请求直接打到 FastAPI app
from fastapi.testclient import TestClient  # noqa: E402

# 导入应用实例
from main import app  # noqa: E402

# 创建测试客户端
client = TestClient(app)


def _login(username: str, password: str) -> str:
    """登录拿 access_token，返回带 Bearer 前缀的 Authorization 头值。"""
    r = client.post("/token", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_flow():
    """完整的增删改查冒烟测试，覆盖所有接口、鉴权和关键错误分支。"""
    # 0. 未登录访问应返回 401
    r = client.get("/users")
    assert r.status_code == 401, r.text

    # 1. 创建用户（创建接口本身也需要鉴权，先无 token 创建第一个用户走特殊路径）
    #    由于没有用户，无法登录获取 token，这里通过直接调 service 创建种子用户
    from app.service import UserService
    from app.schema.user import UserCreate
    from app.db import SessionLocal
    with SessionLocal() as db:
        svc = UserService.from_db(db)
        try:
            svc.create_user(UserCreate(username="alice", password="secret123"))
            db.commit()
        except Exception:
            db.rollback()

    # 2. 登录拿 token
    headers = _login("alice", "secret123")

    # 3. 登录失败：密码错误 → 401
    r = client.post("/token", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401

    # 4. 用户名冲突（应返回 409）
    r = client.post("/users", json={"username": "alice", "password": "secret123"}, headers=headers)
    assert r.status_code == 409

    # 5. 创建另一个用户
    r = client.post("/users", json={"username": "bob", "password": "bobpass"}, headers=headers)
    assert r.status_code == 201, r.text
    bob = r.json()
    assert "password" not in bob  # 响应不含密码
    bob_id = bob["id"]

    # 6. 查询列表（分页响应）
    r = client.get("/users", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 2

    # 7. 分页参数
    r = client.get("/users?skip=0&limit=5", headers=headers)
    assert r.status_code == 200
    assert r.json()["limit"] == 5

    # 8. 查询单个
    r = client.get(f"/users/{bob_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "bob"

    # 9. 更新用户名
    r = client.put(f"/users/{bob_id}", json={"username": "bob_new"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "bob_new"

    # 10. 校验失败：密码过短（应返回 422）
    r = client.put(f"/users/{bob_id}", json={"password": "123"}, headers=headers)
    assert r.status_code == 422

    # 11. 删除
    r = client.delete(f"/users/{bob_id}", headers=headers)
    assert r.status_code == 204

    # 12. 删除后查不到（应返回 404）
    r = client.get(f"/users/{bob_id}", headers=headers)
    assert r.status_code == 404

    # 13. 健康检查
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"

    # 14. 伪造 token 应返回 401
    r = client.get("/users", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401

    print("✅ 全部测试通过")


if __name__ == "__main__":
    test_full_flow()
