"""API 层：定义 HTTP 路由，处理请求/响应、异常映射。

对外暴露 users_router 和 auth_router，由 main.py 通过 app.include_router 注册。
"""
# 导入用户路由器和鉴权路由器，供 main.py 使用
from .users import router as users_router
from .auth import router as auth_router

__all__ = ["users_router", "auth_router"]
