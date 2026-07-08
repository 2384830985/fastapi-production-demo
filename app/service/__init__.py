"""Service 层：业务逻辑，封装密码哈希、业务规则校验等。

依赖 Repository 层提供数据访问，对外暴露 UserService。
"""
# 导入业务类和依赖注入工厂
from .user_service import UserService, get_user_service
from .auth_service import (
    create_access_token,
    decode_token,
    get_current_user_id,
    oauth2_scheme,
)

__all__ = [
    "UserService", "get_user_service",
    "create_access_token", "decode_token", "get_current_user_id", "oauth2_scheme",
]
