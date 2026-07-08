"""鉴权相关 Schema：登录请求体、Token 响应、Token 解析后的载荷。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求体：用户名 + 明文密码。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class Token(BaseModel):
    """登录成功后返回的 access_token 结构。

    符合 OAuth2 Bearer 规范，前端用 `Authorization: Bearer <token>` 携带。
    """

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="token 类型，固定 bearer")


class TokenPayload(BaseModel):
    """JWT 解码后的载荷，对应 JWT 的 payload 部分。

    sub 字段为用户 id（字符串形式），exp 为过期时间戳。
    """

    sub: Optional[str] = None
    exp: Optional[int] = None
