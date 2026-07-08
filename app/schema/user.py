"""用户 Schema：定义请求体和响应体的校验规则。

- UserCreate: 创建用户时的请求体
- UserUpdate: 更新用户时的请求体（所有字段可选）
- UserOut:    返回给前端的响应体（不含密码）
- UserInDB:   内部数据库存储模型（含哈希密码）
- Page:       分页响应通用模型
"""
# 启用 PEP 563 延迟注解求值，让注解字符串在运行时才解析
# 这样可以前向引用尚未定义的类型，也避免部分 Python 3.9 兼容性问题
from __future__ import annotations

# Optional 用于标注可空类型，等价于 X | None（3.10+ 写法），3.9 用 Optional 更兼容
# Generic/List/TypeVar 用于定义泛型分页模型
from typing import Generic, List, Optional, TypeVar

# Pydantic v2 是数据校验库，基于类型注解自动校验数据
# - BaseModel: 所有模型的基类，继承后字段自动获得校验能力
# - ConfigDict: 模型配置字典，比如 from_attributes 让模型能从 ORM 对象属性创建
# - Field: 字段约束，比如必填、最小长度、正则、描述等
from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """用户基础字段，供其他模型继承复用。"""

    # Field(...) 第一个参数 ... 表示必填（不能用 None）
    # min_length/max_length 限制字符串长度
    # pattern 是正则约束，这里限定 username 只能是字母数字下划线
    username: str = Field(
        ..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$",
        description="用户名，3-20 位字母数字下划线",
    )


class UserCreate(UserBase):
    """创建用户请求体：含明文密码，仅用于接收，不会持久化。

    继承 UserBase 拿到 username 字段，自己再加 password。
    Service 层会先把 password 哈希再交给 Repository 存储。
    """

    password: str = Field(
        ..., min_length=6, max_length=64,
        description="密码，6-64 位",
    )


class UserUpdate(BaseModel):
    """更新用户请求体：所有字段可选，只更新传入的字段。

    不继承 UserBase，因为 username 在更新时是可选的。
    """

    # Optional[str] = None 表示字段可以传也可以不传，不传时为 None
    username: Optional[str] = Field(
        default=None, min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$",
    )
    password: Optional[str] = Field(
        default=None, min_length=6, max_length=64,
    )


class UserOut(UserBase):
    """对外响应体：不含密码相关字段。

    用作 API 的 response_model，FastAPI 会自动过滤掉未声明的字段，
    保证不会把 hashed_password 返回给前端。
    """

    id: int

    # Pydantic v2 配置：from_attributes=True 允许从普通 Python 对象的属性创建模型
    # 这样可以直接 UserOut.model_validate(orm_obj) 转换
    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserOut):
    """数据库存储模型：额外包含哈希后的密码。

    仅供 Repository 层使用，永远不会直接序列化返回给前端。
    """

    hashed_password: str


# ── 分页通用模型 ──────────────────────────────────────────
# TypeVar 让泛型 Page 模型能装任意类型的 items
T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页响应模型，可装任意类型列表。

    用法：
        Page[UserOut](items=[...], total=100, skip=0, limit=20)
    """

    items: List[T]                              # 当前页数据
    total: int                                  # 总条数
    skip: int                                   # 跳过条数
    limit: int                                  # 每页数量
    has_more: bool = False                      # 是否还有更多数据
