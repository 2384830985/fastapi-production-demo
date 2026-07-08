"""FastAPI 应用入口。

启动：
    uvicorn main:app --reload
访问：
    http://127.0.0.1:8000/docs   # Swagger 文档（仅 development/staging）
    http://127.0.0.1:8000/redoc  # ReDoc 文档（仅 development/staging）

生产环境（APP_ENV=production）下自动关闭文档暴露。
"""
# contextlib.asynccontextmanager：把生成器函数转成异步上下文管理器
# FastAPI 0.93+ 推荐用它定义 lifespan，替代弃用的 on_event("startup")/("shutdown")
from contextlib import asynccontextmanager

import os
from typing import Any, AsyncIterator, Dict

# FastAPI 是基于 Starlette + Pydantic 的现代 Web 框架
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
# CORSMiddleware：跨域中间件，前后端分离时必需
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

# 从 app/api 包导入用户路由和鉴权路由
from app.api import users_router, auth_router
# 导入数据库引擎、Base
from app.db import engine
# 日志系统初始化
from app.logger import setup_logging, get_logger
# 全局异常处理器
from app.exception_handlers import register_exception_handlers
# 启动时配置校验（fail-fast）
from app.config import validate_config
# 限流中间件
from app.ratelimit import setup_ratelimit
# 导入 ORM 模型，触发 Base.metadata 注册
# 用 from import 避免占用 `app` 名字（与下方 FastAPI 实例冲突）
from app import models  # noqa: F401

# 先初始化日志，后续代码才能用
setup_logging()
logger = get_logger(__name__)

# 启动时校验配置，缺失必需环境变量直接退出（fail-fast）
validate_config()


# 当前应用环境，决定是否暴露 API 文档
APP_ENV = os.getenv("APP_ENV", "development").lower()
# production 环境关闭 docs/redoc/openapi.json，避免接口暴露
DOCS_ENABLED = APP_ENV not in ("production", "prod")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子。

    生产环境 schema 迁移由 Alembic 负责（docker-compose 启动时执行
    `alembic upgrade head`），此处不再调 create_all，避免 schema 漂移。

    yield 之前 = startup 阶段（应用启动时执行一次）
    yield 之后 = shutdown 阶段（应用关闭时执行一次）
    """
    # 启动时仅记录日志，建表交给 Alembic
    logger.info("应用启动完成，环境=%s，文档暴露=%s", APP_ENV, DOCS_ENABLED)

    yield  # 应用运行期间挂起

    # ── 关闭阶段：释放连接池资源 ────────────────────
    engine.dispose()
    logger.info("应用已关闭，连接池释放")


# 创建 FastAPI 应用实例，传入 lifespan
# production 环境下 docs_url/redoc_url/openapi_url 设为 None，关闭接口文档暴露
app = FastAPI(
    title="用户管理 API",
    description="FastAPI 四层架构示例：路由 / 业务 / 校验 / 数据库（MySQL）",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

# ── CORS 中间件：跨域配置 ────────────────────────────────
# 前后端分离时必需，否则浏览器拦截跨域请求
# 环境变量 CORS_ORIGINS 配置允许的前端域名，逗号分隔
# 生产环境务必设为具体域名，不要用 *
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册限流中间件
setup_ratelimit(app)


@app.get("/", tags=["默认"], summary="健康检查")
def health() -> Dict[str, str]:
    """根路径简单探活（不查数据库）。"""
    return {"status": "ok"}


@app.get("/health", tags=["默认"], summary="完整健康检查（含数据库连通性）")
def health_check(db: Session = Depends(get_db)) -> Any:
    """检查应用和数据库连通性。

    返回：
        {"status": "ok", "db": "ok"} 全部正常
        {"status": "degraded", "db": "error"} 数据库异常（不返回内部细节）
    """
    try:
        # SELECT 1 测试数据库连通性
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        # 不向客户端暴露内部错误细节（如连接串、表名），只记日志
        logger.error("健康检查数据库异常: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "error"},
        )


# 注册鉴权路由（/token 登录接口）
app.include_router(auth_router)
# 注册用户管理路由，所有 /users 路径由它处理
app.include_router(users_router)
