# 03 - Pydantic v2 数据校验深入

> 系列文章第 3 篇。本篇讲清楚 Pydantic v2 的核心机制、与 v1 的区别、Field 约束、自定义校验器、泛型模型、`model_config` 配置。

## 你将学到

- Pydantic 是什么、为什么 FastAPI 选它
- v1 vs v2 的关键差异（迁移指南）
- `BaseModel` 的工作原理
- `Field` 的所有约束用法
- `model_validate` / `model_dump` / `model_config`
- 自定义校验器 `@field_validator` / `@model_validator`
- 泛型模型 `Generic[T]`
- `from_attributes`（替代 v1 的 `orm_mode`）

---

## 1. Pydantic 是什么

Pydantic 是 Python 最流行的数据校验库，由 Samuel Colvin 创建。核心思想：**用类型注解定义数据模型，自动校验**。

```python
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str

user = User(id=1, name="alice")  # ✅ 自动校验+转换
print(user.id)   # 1 (int)
print(user.name) # "alice" (str)

User(id="abc")  # ❌ 校验失败抛 ValidationError
```

### 1.1 Pydantic 做了什么

1. **校验**：数据类型对不对
2. **转换**：把字符串 `"1"` 转成 int `1`（strict 模式下不转）
3. **序列化**：把模型转成 dict / JSON
4. **文档**：FastAPI 用它生成 Swagger

### 1.2 v2 性能提升

Pydantic v2 用 Rust 重写核心（`pydantic-core`），比 v1 快 5-50 倍。

| 操作 | v1 | v2 |
|------|-----|-----|
| 校验 1M 次 | ~10s | ~0.2s |
| 序列化 | 慢 | 快 5x |
| 错误信息 | 一般 | 详细（带定位） |

---

## 2. v1 vs v2 关键差异

### 2.1 方法名变更

| v1 | v2 | 说明 |
|----|-----|------|
| `.dict()` | `.model_dump()` | 转字典 |
| `.json()` | `.model_dump_json()` | 转 JSON 字符串 |
| `.parse_obj()` | `.model_validate()` | 从 dict 创建 |
| `.parse_raw()` | `.model_validate_json()` | 从 JSON 字符串创建 |
| `.from_orm()` | `.model_validate()` | 从 ORM 对象创建（需 `from_attributes=True`） |
| `.copy()` | `.model_copy()` | 复制模型 |
| `Config` 类 | `model_config = ConfigDict(...)` | 配置 |
| `class Config:` | `model_config` | 配置写法变了 |

### 2.2 校验器改名

| v1 | v2 |
|----|-----|
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |

### 2.3 `Config` 改 `model_config`

```python
# v1
class User(BaseModel):
    id: int
    class Config:
        orm_mode = True
        allow_population_by_field_name = True

# v2
class User(BaseModel):
    id: int
    model_config = ConfigDict(
        from_attributes=True,  # orm_mode 改名
        populate_by_name=True,  # allow_population_by_field_name 改名
    )
```

### 2.4 本项目用到的 v2 特性

```python
# schema/user.py
class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)  # v2 写法
```

```python
# service/user_service.py
return UserOut.model_validate(user_in_db)  # v2 方法名
return [UserOut.model_validate(u) for u in users]
```

---

## 3. `BaseModel` 工作原理

### 3.1 定义即收集

```python
class User(BaseModel):
    id: int
    name: str
```

`BaseModel` 的元类在类创建时扫描所有字段，生成 `__fields__` 元数据：

```python
print(User.model_fields)
# {
#   'id': FieldInfo(annotation=int, required=True),
#   'name': FieldInfo(annotation=str, required=True),
# }
```

### 3.2 实例化时校验

```python
user = User(id=1, name="alice")
```

执行流程：
1. Pydantic 拿到 `{"id": 1, "name": "alice"}`
2. 遍历 `model_fields`，对每个字段校验
3. `id: int` → 检查 1 是 int，✅
4. `name: str` → 检查 "alice" 是 str，✅
5. 校验通过，创建实例

### 3.3 校验失败

```python
User(id="abc")
# ValidationError: 1 validation error for User
# id
#   Input should be a valid integer [type=int_type, input_value='abc']
```

错误信息包含：
- 字段名（`id`）
- 错误类型（`int_type`）
- 输入值（`input_value='abc'`）

---

## 4. `Field` 详解

`Field` 用来给字段加约束。

### 4.1 必填 vs 可选 vs 默认值

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    # 必填（不传报错）
    id: int = Field(...)

    # 可选，默认 None
    email: str | None = Field(default=None)

    # 默认值
    is_active: bool = Field(default=True)

    # 默认工厂（每次创建新对象）
    tags: list[str] = Field(default_factory=list)
```

`...`（Ellipsis）表示必填，是 Pydantic 约定。

### 4.2 字符串约束

```python
class User(BaseModel):
    username: str = Field(
        ...,
        min_length=3,           # 最短 3 字符
        max_length=20,          # 最长 20 字符
        pattern=r"^[a-zA-Z0-9_]+$",  # 正则约束
    )
    password: str = Field(..., min_length=6, max_length=64)
```

### 4.3 数字约束

```python
class Product(BaseModel):
    price: float = Field(..., gt=0, le=10000)  # 大于 0，小于等于 10000
    quantity: int = Field(..., ge=0)  # 大于等于 0
    discount: float = Field(default=0, ge=0, lt=1)  # 0 ≤ x < 1
```

| 约束 | 含义 |
|------|------|
| `gt=N` | > N |
| `ge=N` | ≥ N |
| `lt=N` | < N |
| `le=N` | ≤ N |
| `multiple_of=N` | 是 N 的倍数 |

### 4.4 列表/字典约束

```python
class Article(BaseModel):
    tags: list[str] = Field(..., min_length=1, max_length=10)  # 1-10 个标签
    metadata: dict[str, str] = Field(..., min_length=1)
```

### 4.5 文档元信息

```python
class User(BaseModel):
    username: str = Field(
        ...,
        description="用户名，3-20 位字母数字下划线",
        examples=["alice", "bob"],
    )
```

`description` 和 `examples` 显示在 Swagger 文档里。

### 4.6 别名（alias）

数据库字段叫 `user_name`，但你想用 `username`：

```python
class User(BaseModel):
    username: str = Field(..., alias="user_name")

# 用别名创建
User.model_validate({"user_name": "alice"})  # ✅
User(username="alice")  # ❌ 默认不能用字段名

# 启用 populate_by_name 后两者都行
class User(BaseModel):
    username: str = Field(..., alias="user_name")
    model_config = ConfigDict(populate_by_name=True)

User(username="alice")  # ✅
User.model_validate({"user_name": "alice"})  # ✅
```

---

## 5. `model_validate` vs `model_dump`

### 5.1 `model_validate`：从对象创建模型

```python
# 从 dict 创建
user = User.model_validate({"id": 1, "name": "alice"})

# 从 ORM 对象创建（需要 from_attributes=True）
user_orm = UserORM(id=1, name="alice")
user = User.model_validate(user_orm)

# 从另一个 Pydantic 模型创建
user_in_db = UserInDB(id=1, name="alice", hashed_password="...")
user_out = UserOut.model_validate(user_in_db)  # 自动取同名字段
```

**关键**：`model_validate` 是 v2 万能入口，替代 v1 的 `parse_obj` / `from_orm`。

### 5.2 `model_dump`：转字典

```python
user = User(id=1, name="alice", hashed_password="xxx")

user.model_dump()
# {"id": 1, "name": "alice", "hashed_password": "xxx"}

# 排除字段
user.model_dump(exclude={"hashed_password"})
# {"id": 1, "name": "alice"}

# 只包含某些字段
user.model_dump(include={"id", "name"})
# {"id": 1, "name": "alice"}

# 排除 None 值
user.model_dump(exclude_none=True)
```

### 5.3 `model_dump_json`：转 JSON 字符串

```python
user.model_dump_json()
# '{"id":1,"name":"alice","hashed_password":"xxx"}'

# 美化
user.model_dump_json(indent=2)
```

### 5.4 本项目的用法

```python
# Service 层：UserInDB → UserOut
def list_users(self):
    users = self._repo.list_all()  # 返回 list[UserInDB]
    return [UserOut.model_validate(u) for u in users]  # 转成 UserOut
```

为什么这么做？`UserInDB` 含 `hashed_password`，`UserOut` 不含。`model_validate` 自动取同名字段，丢弃多余字段（实际是按 `UserOut` 字段定义提取）。

---

## 6. `ConfigDict` 配置

### 6.1 常用配置项

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        # 允许从对象属性创建（替代 v1 orm_mode）
        from_attributes=True,

        # 允许用字段名赋值（搭配 alias）
        populate_by_name=True,

        # 额外字段处理
        extra="ignore",  # ignore / forbid / allow

        # 严格模式（不自动转换类型）
        strict=False,

        # 允许 mutation（实例字段可修改）
        frozen=False,

        # 字段按定义顺序输出（v2 默认按字母序）
        # 注意：v2 默认就是定义顺序，但显式声明更清晰
    )
```

### 6.2 `extra` 选项

```python
# extra="allow"：允许额外字段
class Foo(BaseModel):
    model_config = ConfigDict(extra="allow")
    x: int

Foo(x=1, y=2)  # ✅ y 也保留

# extra="ignore"：忽略额外字段（默认）
class Foo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: int

Foo(x=1, y=2)  # y 被丢弃

# extra="forbid"：禁止额外字段
class Foo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: int

Foo(x=1, y=2)  # ❌ ValidationError
```

### 6.3 `frozen`：不可变模型

```python
class User(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    name: str

user = User(id=1, name="alice")
user.name = "bob"  # ❌ ValidationError: User is frozen
```

适合做值对象、配置等不可变数据。

### 6.4 本项目的 `UserOut`

```python
class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
```

`from_attributes=True` 让 `UserOut.model_validate(orm_obj)` 能从 ORM 对象属性提取数据。

---

## 7. 自定义校验器

### 7.1 `@field_validator`：字段级校验

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    username: str
    age: int

    @field_validator("username")
    @classmethod
    def username_must_not_contain_space(cls, v: str) -> str:
        if " " in v:
            raise ValueError("用户名不能包含空格")
        return v

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("年龄不能为负")
        return v
```

**注意**：
- 必须加 `@classmethod`
- 校验失败抛 `ValueError`（Pydantic 自动转 ValidationError）
- 必须返回值（修改后的值会替换原值）

### 7.2 `@model_validator`：跨字段校验

```python
from pydantic import BaseModel, model_validator

class PasswordChange(BaseModel):
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("两次密码不一致")
        return self
```

**`mode="after"`**：在所有字段校验完后执行，能访问 `self`。

**`mode="before"`**：在字段校验前执行，能拿到原始输入：

```python
@model_validator(mode="before")
@classmethod
def remove_extra_fields(cls, data: Any) -> Any:
    if isinstance(data, dict):
        data.pop("extra_field", None)  # 删除多余字段
    return data
```

### 7.3 校验器应用场景

- 字段级：用户名格式、邮箱格式、手机号格式
- 模型级：两次密码一致、开始时间 < 结束时间、字段间约束

---

## 8. 泛型模型 `Generic[T]`

### 8.1 定义泛型模型

```python
from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool = False
```

### 8.2 使用

```python
# 装具体类型的分页
class UserOut(BaseModel):
    id: int
    name: str

page = Page[UserOut](
    items=[UserOut(id=1, name="alice")],
    total=1,
    skip=0,
    limit=20,
)

# 序列化
print(page.model_dump())
# {'items': [{'id': 1, 'name': 'alice'}], 'total': 1, ...}
```

### 8.3 在 FastAPI 里用

```python
@router.get("", response_model=Page[UserOut])
def list_users():
    return Page[UserOut](items=[...], total=10, ...)
```

`response_model=Page[UserOut]` 让 Swagger 知道返回结构是装 `UserOut` 的分页。

### 8.4 类型参数约束

```python
# 约束 T 必须是 BaseModel
T = TypeVar("T", bound=BaseModel)

class Page(BaseModel, Generic[T]):
    items: List[T]
```

---

## 9. `from_attributes` 详解

### 9.1 为什么需要

Service 层返回 `UserInDB`（Pydantic 模型），但 Repository 层返回的是 ORM `User` 对象（SQLAlchemy 模型）。怎么转换？

```python
# ORM 对象
user_orm = User(id=1, username="alice", hashed_password="...")

# 直接 model_validate？
UserInDB.model_validate(user_orm)  # ❌ v1 默认不支持
```

### 9.2 启用 `from_attributes`

```python
class UserInDB(UserOut):
    hashed_password: str
    model_config = ConfigDict(from_attributes=True)
```

启用后：

```python
UserInDB.model_validate(user_orm)  # ✅ 从 user_orm 的属性提取
```

### 9.3 工作原理

`from_attributes=True` 让 `model_validate` 接受：
- dict（直接取 key）
- 任意对象（用 `getattr(obj, field_name)` 取属性）

```python
# 等价于
UserInDB(
    id=user_orm.id,
    username=user_orm.username,
    hashed_password=user_orm.hashed_password,
)
```

### 9.4 本项目为什么不直接用

本项目 Repository 层手动转：

```python
# repository/user_repo.py
@staticmethod
def _to_schema(user: User) -> UserInDB:
    return UserInDB(
        id=user.id,
        username=user.username,
        hashed_password=user.hashed_password,
    )
```

而不是用 `from_attributes`。**原因**：
1. 显式转换更清晰
2. 不依赖 ORM 对象的属性名匹配
3. ORM 字段名和 Schema 字段名不一致时更灵活

但 `UserOut` 还是开了 `from_attributes=True`，方便 `UserOut.model_validate(user_in_db)` 这种 Schema 间转换。

---

## 10. 继承与复用

### 10.1 字段继承

```python
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)

class UserCreate(UserBase):
    # 继承 username，加 password
    password: str = Field(..., min_length=6)

class UserOut(UserBase):
    # 继承 username，加 id
    id: int

class UserInDB(UserOut):
    # 继承 username + id，加 hashed_password
    hashed_password: str
```

继承链：

```
BaseModel
   ↓
UserBase (username)
   ↓
UserCreate (+password)  UserOut (+id)
                            ↓
                       UserInDB (+hashed_password)
```

### 10.2 配置继承

```python
class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str

class UserOut(UserBase):
    id: int
    # 自动继承 from_attributes=True
```

### 10.3 校验器继承

字段校验器会随字段继承。如果子类重定义字段，需要重新声明校验器。

---

## 11. 性能优化

### 11.1 用 `strict` 模式

```python
class User(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int

User(id="1")  # ❌ strict 模式不自动转换
User(id=1)    # ✅
```

strict 模式不自动转换类型，更安全也更快。

### 11.2 用 `model_construct` 跳过校验

```python
# 已知数据已校验过，跳过校验直接创建
user = User.model_construct(id=1, name="alice")
```

适合从可信源（如数据库）加载数据时跳过校验，性能更好。

### 11.3 复用 `TypeAdapter`

```python
from pydantic import TypeAdapter

# 校验 list[int]，不用每次创建 BaseModel
list_int = TypeAdapter(list[int])
list_int.validate_python([1, 2, 3])  # ✅
```

---

## 12. 常见坑

### 12.1 可变默认值

```python
# ❌ 所有实例共享同一个 list
class Foo(BaseModel):
    tags: list[str] = []

# ✅ 用 default_factory
class Foo(BaseModel):
    tags: list[str] = Field(default_factory=list)
```

### 12.2 `Optional[X]` 默认值

```python
# ❌ 注解说可空，但默认值必填
class Foo(BaseModel):
    x: Optional[int]  # Pydantic 要求必须传 x（即使为 None）

# ✅ 设默认值
class Foo(BaseModel):
    x: Optional[int] = None
```

### 12.3 v1 / v2 混用

```python
# v1 写法在 v2 不工作
class Foo(BaseModel):
    x: int
    class Config:  # ❌ v2 不识别
        orm_mode = True

# v2 写法
class Foo(BaseModel):
    x: int
    model_config = ConfigDict(from_attributes=True)
```

### 12.4 校验器忘加 `@classmethod`

```python
# ❌ 报错
@field_validator("x")
def check_x(cls, v):  # 缺 @classmethod
    return v

# ✅
@field_validator("x")
@classmethod
def check_x(cls, v):
    return v
```

### 12.5 `model_validate` vs 直接构造

```python
# 直接构造：只接受关键字参数
User(id=1, name="alice")

# model_validate：接受 dict / 对象
User.model_validate({"id": 1, "name": "alice"})
User.model_validate(some_orm_obj)  # 需要 from_attributes=True
```

---

## 13. 自测题

### Q1：下面代码在 Pydantic v2 上能跑吗？

```python
class User(BaseModel):
    id: int
    class Config:
        orm_mode = True
```

<details>
<summary>查看答案</summary>

不能。v2 用 `model_config = ConfigDict(from_attributes=True)`，`Config` 类和 `orm_mode` 是 v1 写法。
</details>

### Q2：怎么让 `User.model_validate(orm_obj)` 工作？

<details>
<summary>查看答案</summary>

加 `model_config = ConfigDict(from_attributes=True)`。
</details>

### Q3：`Page[UserOut]` 是什么意思？

<details>
<summary>查看答案</summary>

泛型模型实例化。`Page` 是泛型类，`Page[UserOut]` 表示"装 UserOut 类型的分页"，`items` 字段类型变成 `List[UserOut]`。
</details>

### Q4：`Field(...)` 第一个参数 `...` 表示什么？

<details>
<summary>查看答案</summary>

`...`（Ellipsis）表示字段必填。`Field(default=None)` 表示可选默认 None。
</details>

---

## 14. 小结

| 概念 | v1 | v2 |
|------|-----|-----|
| 转字典 | `.dict()` | `.model_dump()` |
| 转 JSON | `.json()` | `.model_dump_json()` |
| 从 dict 创建 | `.parse_obj()` | `.model_validate()` |
| 从 ORM 创建 | `.from_orm()` | `.model_validate()` + `from_attributes=True` |
| 字段校验器 | `@validator` | `@field_validator` |
| 模型校验器 | `@root_validator` | `@model_validator` |
| 配置 | `class Config:` | `model_config = ConfigDict(...)` |

| 概念 | 关键点 |
|------|--------|
| `Field(...)` | 必填字段 |
| `Field(default=None)` | 可选字段 |
| `model_validate` | 万能创建方法（dict/对象） |
| `model_dump` | 万能序列化方法 |
| `from_attributes` | 从对象属性创建（替代 orm_mode） |
| `Generic[T]` | 泛型模型，如 `Page[T]` |

## 15. 下篇预告

下一篇讲 **SQLAlchemy 2.0 ORM 完全指南**：`Mapped`/`mapped_column`、Session、查询、flush vs commit、连接池、关系映射。

---

**延伸阅读**：
- [Pydantic v2 官方文档](https://docs.pydantic.dev/latest/)
- [Pydantic v2 迁移指南](https://docs.pydantic.dev/latest/migration/)
- [pydantic-core（Rust 实现）](https://github.com/pydantic/pydantic-core)
