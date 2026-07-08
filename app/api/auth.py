"""鉴权路由：登录接口签发 JWT。

接口：
- POST /token：用户名 + 密码换 access_token（限流：每 IP 每分钟 10 次，防爆破）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ratelimit import limiter, RATE_LOGIN
from app.schema.auth import LoginRequest, Token
from app.service import UserService, get_user_service, create_access_token

router = APIRouter(tags=["鉴权"])


@router.post(
    "/token",
    response_model=Token,
    summary="登录获取 access_token",
)
@limiter.limit(RATE_LOGIN)  # 登录接口限流：每 IP 每分钟 10 次，防暴力破解
def login(
    request: Request,  # slowapi 要求路由第一个参数是 request
    payload: LoginRequest,
    svc: UserService = Depends(get_user_service),
) -> Token:
    """用户名 + 密码换 JWT。

    前端拿到 token 后，后续请求带 `Authorization: Bearer <token>`。
    认证失败统一返回 401，不区分用户名不存在/密码错误，防爆破。
    限流：每 IP 每分钟 10 次，超限返回 429。
    """
    user = svc.authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # JWT subject 用用户 id（字符串），解码后可还原
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, token_type="bearer")
