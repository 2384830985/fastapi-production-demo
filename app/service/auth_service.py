"""鉴权服务：JWT 编解码 + 登录认证 + FastAPI 依赖。

设计要点：
- SECRET_KEY / ACCESS_TOKEN_EXPIRE_MINUTES 从环境变量读取，不硬编码
- 算法用 HS256（对称签名，单机部署够用；多服务共享密钥即可）
- get_current_user 作为 FastAPI 依赖注入，路由用 Depends() 即可强制鉴权
- 鉴权失败统一抛 fastapi.HTTPException(401)，由 FastAPI 默认处理器返回 WWW-Authenticate 头
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

# PyJWT：JWT 编解码库，纯 Python，无 C 扩展依赖
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# JWT 签名算法（对称密钥）
ALGORITHM = "HS256"

# 从环境变量读取密钥和过期时间
# 必须设置 SECRET_KEY，否则启动后所有 token 操作都会失败
SECRET_KEY = os.getenv("SECRET_KEY", "")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# OAuth2PasswordBearer 会从 Authorization: Bearer <token> 头读取 token
# tokenUrl 指向登录接口路径，会出现在 /docs 的 Authorize 按钮配置里
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """签发 JWT access token。

    Args:
        subject: token 主体，这里用用户 id（字符串形式）
        expires_minutes: 自定义过期时间，None 时用全局默认

    Returns:
        编码后的 JWT 字符串

    Raises:
        RuntimeError: SECRET_KEY 未配置
    """
    if not SECRET_KEY:
        # 启动时未配置密钥，拒绝签发 token，避免弱密钥被暴力破解
        raise RuntimeError("SECRET_KEY 未配置，无法签发 JWT")

    minutes = expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        # exp 是 JWT 标准字段，PyJWT 校验时自动检查过期
        "exp": now + timedelta(minutes=minutes),
        "iat": now,  # 签发时间
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """解码并校验 JWT，失败抛 401。

    Returns:
        JWT payload 字典
    """
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY 未配置，无法校验 JWT")
    try:
        # PyJWT 自动校验 exp、签名
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """FastAPI 依赖：从 token 解出当前用户 id（int）。

    路由用 `user_id: int = Depends(get_current_user_id)` 接收。
    鉴权失败抛 401，由 FastAPI 默认异常处理返回。
    """
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 缺少 sub 字段",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token subject 非合法用户 id",
            headers={"WWW-Authenticate": "Bearer"},
        )
