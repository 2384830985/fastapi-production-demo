"""用户路由：定义增删改查接口。

所有接口都需 JWT 鉴权（Depends(get_current_user_id)）。
业务异常由全局 exception_handlers 处理，路由函数保持简洁。
"""
from __future__ import annotations

# FastAPI 核心组件
# - APIRouter: 路由器，把一组路由打包，最后用 app.include_router 注册
# - Depends: 依赖注入装饰器，FastAPI 会自动调用依赖函数并把返回值作为参数传入
# - Query: 查询参数校验
from fastapi import APIRouter, Depends, Query

# Schema 层：请求/响应模型
from app.schema.user import UserCreate, UserOut, UserUpdate, Page
# Service 层：业务逻辑
from app.service import UserService, get_user_service, get_current_user_id

# 创建路由器，prefix 给所有路径加 /users 前缀，tags 用于 Swagger 文档分组
router = APIRouter(prefix="/users", tags=["用户管理"])


# ── 路由 ─────────────────────────────────────────────────
# 所有路由都通过 Depends(get_current_user_id) 强制 JWT 鉴权
# 鉴权失败由 auth_service 抛 401，FastAPI 自动返回带 WWW-Authenticate 头的响应
# response_model 自动按 UserOut 序列化（过滤密码字段）
# summary 显示在 Swagger 文档里作为接口简介


@router.get(
    "",
    response_model=Page[UserOut],
    summary="获取用户列表（分页）",
)
def list_users(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(20, ge=1, le=100, description="每页数量（1-100）"),
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),
) -> Page[UserOut]:
    """分页获取用户列表。需登录。"""
    return svc.list_users(skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="获取单个用户",
)
def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),
) -> UserOut:
    """按 id 查询单个用户，不存在会抛 UserNotFoundError（全局处理器转 404）。"""
    return svc.get_user(user_id)


@router.post(
    "",
    response_model=UserOut,
    summary="创建用户",
    status_code=201,
)
def create_user(
    payload: UserCreate,
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),
) -> UserOut:
    """创建新用户。冲突会抛 UserAlreadyExistsError（全局处理器转 409）。"""
    return svc.create_user(payload)


@router.put(
    "/{user_id}",
    response_model=UserOut,
    summary="更新用户",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),
) -> UserOut:
    """更新用户信息，仅更新传入的字段。"""
    return svc.update_user(user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="删除用户",
)
def delete_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
    _: int = Depends(get_current_user_id),
) -> None:
    """按 id 删除用户。"""
    svc.delete_user(user_id)
