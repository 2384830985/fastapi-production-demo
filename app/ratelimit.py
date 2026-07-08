"""限流配置：用 slowapi 防止暴力破解和 DDoS。

策略：
- 登录接口：每 IP 每分钟 10 次（防爆破）
- 创建/更新接口：每 IP 每分钟 30 次
- 普通查询：每 IP 每分钟 60 次
"""
from __future__ import annotations

# slowapi 是 FastAPI 的限流中间件
# - Limiter: 限流器，支持多种存储后端（默认内存）
# - SlowAPIMiddleware: 中间件
# - _rate_limit_exceeded_handler: 默认超限响应
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI

# 用客户端 IP 作为限流 key
# 也可以自定义（如按 user_id 限流已登录用户）
limiter = Limiter(key_func=get_remote_address)


def setup_ratelimit(app: FastAPI) -> None:
    """注册限流中间件和异常处理器。

    在 main.py 启动时调用一次。
    """
    # slowapi 要求把 limiter 存到 app.state
    app.state.limiter = limiter
    # 注册超限异常处理器（429 Too Many Requests）
    # slowapi 的 handler 签名与 Starlette 期望类型不完全匹配，是已知问题
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    # 注册中间件
    app.add_middleware(SlowAPIMiddleware)


# 常用限流策略（装饰器用）
RATE_LOGIN = "10/minute"      # 登录：每分钟 10 次
RATE_WRITE = "30/minute"      # 写操作：每分钟 30 次
RATE_READ = "60/minute"       # 读操作：每分钟 60 次
