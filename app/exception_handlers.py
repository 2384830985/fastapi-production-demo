"""全局异常处理器：把业务异常统一映射为 HTTP 响应。

替代每个路由里重复的 try/except，让路由函数更干净。

注册方式：在 main.py 里调用 register_exception_handlers(app)
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.logger import get_logger
from app.service.user_service import UserNotFoundError, UserAlreadyExistsError

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """注册所有全局异常处理器。在 main.py 启动时调用一次。"""

    @app.exception_handler(UserNotFoundError)
    async def handle_user_not_found(_: Request, exc: UserNotFoundError) -> JSONResponse:
        """用户不存在 → 404"""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UserAlreadyExistsError)
    async def handle_user_already_exists(_: Request, exc: UserAlreadyExistsError) -> JSONResponse:
        """用户名冲突 → 409"""
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        """数据库完整性约束错误（如 UNIQUE 冲突）→ 409

        兜底处理：Service 层未捕获的 IntegrityError 统一转 409。
        """
        logger.warning("数据库完整性约束错误: %s", exc)
        return JSONResponse(
            status_code=409,
            content={"detail": "数据冲突，可能违反唯一约束"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """未捕获异常兜底 → 500，不向前端暴露内部错误细节"""
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"},
        )
