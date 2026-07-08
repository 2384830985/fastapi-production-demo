# 01 - Python 现代特性与类型注解

> 系列文章第 1 篇。本篇讲清楚 Python 3.9+ 项目里类型注解的方方面面，以及项目中那些"看不太懂"的语法到底怎么回事。

## 你将学到

- Python 类型注解的运行机制（hint 不是强制）
- `from __future__ import annotations` 到底做了什么
- `Optional[X]` vs `X | None` 的区别与历史
- `TypeVar` + `Generic` 实现泛型类（为后面的 `Page[T]` 做准备）
- 为什么本项目用 `Optional[X]` 而不是 `X | None`
- `Mapped[X]` 这种"自定义注解"是怎么实现的

---

## 1. 类型注解的本质：hint，不是强制

Python 是动态类型语言，但 3.5+ 引入了**类型注解（type hints）**，让你能给变量、参数、返回值标注类型。

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

greet("Alice")   # ✅ 正常
greet(123)       # ⚠️ 运行时不会报错！
```

**关键认知**：类型注解**不会在运行时强制校验**。Python 解释器只把它存起来，第三方工具（mypy、pyright、Pydantic）才会用它做检查。

### 1.1 运行时类型注解在哪？

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

print(greet.__annotations__)
# {'name': <class 'str'>, 'return': <class 'str'>}
```

函数的注解被存到 `__annotations__` 属性里。模块、类也有这个属性。

### 1.2 谁会读这些注解？

| 工具 | 用途 |
|------|------|
| **mypy** | 静态类型检查（运行前检查） |
| **pyright** | VS Code 默认检查器 |
| **Pydantic** | 运行时数据校验（把注解变成校验规则） |
| **SQLAlchemy 2.0** | 用 `Mapped[X]` 推断列类型 |
| **FastAPI** | 用注解自动生成 Swagger 文档 |

本项目里，Pydantic 和 SQLAlchemy 是真正利用类型注解干活的关键。

---

## 2. `from __future__ import annotations` 详解

你在项目里会看到这行：

```python
from __future__ import annotations
```

它做了什么？为什么需要它？

### 2.1 没有它时的限制

Python 3.9 及更早版本，类型注解在**定义时**就被求值：

```python
class Node:
    def __init__(self, value: int, next: "Node | None" = None):
        # ↑ 这里必须用字符串，因为 Node 还没定义完
        self.value = value
        self.next = next
```

如果不加引号：

```python
class Node:
    def __init__(self, next: Node | None = None):  # ❌ NameError: Node 未定义
        ...
```

因为 Python 在解析 `__init__` 时，`Node` 类还没定义完，名字 `Node` 还不存在。

### 2.2 加了 `__future__` 后

```python
from __future__ import annotations

class Node:
    def __init__(self, next: Node | None = None):  # ✅ 不报错
        ...
```

`from __future__ import annotations` 启用 **PEP 563 - 延迟注解求值**：所有注解在定义时不求值，而是存成**字符串**。

验证：

```python
from __future__ import annotations

def foo(x: int) -> str:
    return str(x)

print(foo.__annotations__)
# {'x': 'int', 'return': 'str'}  ← 字符串，不是类型对象
```

### 2.3 谁来"求值"这些字符串？

需要用注解的库（Pydantic、SQLAlchemy）会调用 `typing.get_type_hints()` 把字符串解析回类型对象。

```python
from __future__ import annotations
import typing

def foo(x: int) -> str:
    return str(x)

print(typing.get_type_hints(foo))
# {'x': <class 'int'>, 'return': <class 'str'>}  ← 真正的类型对象
```

### 2.4 为什么本项目用它

- **前向引用**：类方法返回自身类型（如 `def clone(self) -> "User"`）
- **避免循环 import**：注解是字符串，不会触发 import
- **兼容性**：在 Python 3.9 上能用 `X | None` 语法（部分场景）

> ⚠️ 但 Pydantic v2 在 Python 3.9 上对 `X | None` 解析仍有 bug，所以本项目用 `Optional[X]` 更稳。

---

## 3. `Optional[X]` vs `X | None` 全面对比

### 3.1 历史演进

| Python 版本 | 推荐写法 | 示例 |
|------------|---------|------|
| 3.5 - 3.9 | `Optional[X]` | `Optional[int]` |
| 3.10+ | `X \| None` | `int \| None` |

两者**完全等价**，都表示"可以是 X，也可以是 None"。

### 3.2 `Optional` 的本质

```python
from typing import Optional

# 这两行完全等价
x: Optional[int]
x: int | None

# Optional 其实就是 Union 的语法糖
Optional[int]  # 等价于 Union[int, None]
```

### 3.3 为什么本项目混用？

你看项目代码会发现：

```python
# schema/user.py
from __future__ import annotations
from typing import Optional

class UserUpdate(BaseModel):
    username: Optional[str] = None  # 用 Optional
```

```python
# service/user_service.py
def get_user(self, user_id: int) -> UserOut:  # 不用 Optional
    ...
```

**原因**：
1. `from __future__ import annotations` 让所有注解变成字符串，运行时不解析
2. 但 **Pydantic v2 会用 `get_type_hints()` 解析**这些字符串
3. Pydantic v2 在 Python 3.9 上解析 `str | None` 时有兼容性 bug
4. 用 `Optional[str]` 100% 兼容所有 Python 3.9+ 版本

### 3.4 怎么选？

| 场景 | 推荐写法 |
|------|---------|
| Python 3.10+ 项目 | `X \| None`（更简洁） |
| Python 3.9 项目（用 Pydantic） | `Optional[X]`（兼容性好） |
| Python 3.9 项目（不用 Pydantic） | 加 `__future__` 后可用 `X \| None` |

本项目要兼容 3.9 且用 Pydantic v2，所以统一用 `Optional[X]`。

---

## 4. 泛型：`TypeVar` + `Generic`

本项目的分页模型用了泛型：

```python
from typing import Generic, List, TypeVar

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    ...
```

这是什么意思？

### 4.1 为什么需要泛型

考虑分页响应：用户列表、订单列表、文章列表结构都一样（items + total + skip + limit），但 items 类型不同。

不用泛型的做法（重复代码）：

```python
class UserPage(BaseModel):
    items: List[UserOut]
    total: int

class OrderPage(BaseModel):
    items: List[OrderOut]
    total: int
```

用泛型（一份代码）：

```python
T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
```

### 4.2 `TypeVar` 是什么

```python
T = TypeVar("T")
```

`TypeVar` 创建一个**类型变量**，相当于函数的"参数"。`T` 是约定俗成的名字（Type 的首字母），但可以叫任何名字。

### 4.3 `Generic[T]` 是什么

```python
class Page(BaseModel, Generic[T]):
```

继承 `Generic[T]` 声明：`Page` 是个泛型类，`T` 是它的类型参数。

### 4.4 使用方式

```python
# 用 Page[UserOut] 表示"装 UserOut 的分页"
user_page: Page[UserOut] = Page(
    items=[UserOut(id=1, username="alice")],
    total=1,
)

# 用 Page[OrderOut] 表示"装 OrderOut 的分页"
order_page: Page[OrderOut] = Page(
    items=[OrderOut(id=1, amount=100)],
    total=1,
)
```

### 4.5 在 FastAPI 里用

```python
@router.get("", response_model=Page[UserOut])
def list_users():
    return svc.list_users()
```

`response_model=Page[UserOut]` 告诉 FastAPI：返回值是装 `UserOut` 的分页。Swagger 文档会自动生成正确结构。

### 4.6 类型变量约束

可以约束 `T` 必须是某个类的子类：

```python
T = TypeVar("T", bound=BaseModel)  # T 必须是 BaseModel 子类
T = TypeVar("T", int, float)        # T 必须是 int 或 float
```

本项目没约束，因为 `Page` 可以装任何类型。

---

## 5. SQLAlchemy 2.0 的 `Mapped[X]` 是怎么实现的

你会在 ORM 模型里看到：

```python
class User(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(20))
```

`Mapped[int]` 不是 Python 内置的，是 SQLAlchemy 自己定义的。它是怎么工作的？

### 5.1 `Mapped` 的本质

SQLAlchemy 在 `sqlalchemy.orm` 模块定义了 `Mapped` 类：

```python
# SQLAlchemy 源码简化版
class Mapped(Generic[T]):
    """描述 ORM 属性的类型注解"""
    pass
```

它就是一个泛型容器，用来标注"这一列是什么类型"。

### 5.2 工作流程

1. **定义时**：`id: Mapped[int] = mapped_column(...)` 只是注解，运行时被存成字符串（如果加了 `__future__`）或 `Mapped[int]` 对象
2. **类创建完**：SQLAlchemy 的 `DeclarativeBase` 元类扫描所有 `Mapped[X]` 注解
3. **解析类型**：`Mapped[int]` → 列类型是 `int` → SQLAlchemy 推断用 `Integer`
4. **生成列**：调用 `mapped_column(...)` 配置列属性，组合成完整的列定义

### 5.3 类型推断

```python
id: Mapped[int] = mapped_column(Integer, primary_key=True)
#       ↑ 类型注解                ↑ 实际列配置

# 如果不显式指定列类型，SQLAlchemy 会从注解推断：
id: Mapped[int]      # → Integer
name: Mapped[str]    # → String (默认 VARCHAR)
is_active: Mapped[bool]  # → Boolean
```

### 5.4 可选列（nullable）

```python
# 必填列（NOT NULL）
username: Mapped[str]

# 可空列（NULL allowed）
email: Mapped[Optional[str]]   # 用 Optional
email: Mapped[str | None]       # Python 3.10+ 写法
```

SQLAlchemy 看到 `Optional[str]` 就知道这列允许 NULL。

---

## 6. 实战：本项目的类型注解

### 6.1 `schema/user.py` 完整分析

```python
from __future__ import annotations
from typing import Optional, Generic, List, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=64)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3)
    password: Optional[str] = Field(default=None, min_length=6)

class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class UserInDB(UserOut):
    hashed_password: str

class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool = False
```

逐行解读：

| 行 | 类型注解 | 作用 |
|----|---------|------|
| `username: str = Field(...)` | 必填字符串 | Pydantic 校验非空、长度、正则 |
| `password: Optional[str] = None` | 可空字符串 | 更新时字段可选，不传为 None |
| `id: int` | 必填整数 | 响应里一定有 id |
| `hashed_password: str` | 必填字符串 | 内部用，不对外 |
| `items: List[T]` | 泛型列表 | 可装任意类型的列表 |

### 6.2 `models/user.py` 的 `Mapped`

```python
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.current_timestamp())
```

注意：`created_at: Mapped[str]` 实际应该是 `Mapped[datetime]`，但项目简化用 str。生产建议用 `Mapped[datetime.datetime]`。

---

## 7. 常见坑与最佳实践

### 7.1 坑 1：`Optional[X]` 默认值忘记设 None

```python
# ❌ 错误：注解说可空，但默认值必填
class Foo(BaseModel):
    x: Optional[int]  # Pydantic 会要求必须传 x（即使为 None）

# ✅ 正确
class Foo(BaseModel):
    x: Optional[int] = None  # 不传时默认 None
```

### 7.2 坑 2：注解和实际值不匹配

```python
# 注解说 int，但赋值字符串，运行时不报错（注解不强制）
x: int = "hello"  # ⚠️ mypy 会警告，但 Python 不报错
```

### 7.3 坑 3：循环 import

```python
# a.py
from b import B
class A:
    b: B  # 如果 b.py 也 import a，会循环

# 解决：用字符串注解 + __future__
from __future__ import annotations
class A:
    b: "B"  # 字符串，不触发 import
```

### 7.4 最佳实践

1. **始终加 `from __future__ import annotations`**：前向引用不报错
2. **Python 3.9 项目用 `Optional[X]`**：兼容性最好
3. **类型注解要准确**：用 mypy/pyright 检查
4. **Pydantic 模型字段加 `Field(...)`**：明确必填、可选、约束
5. **泛型类继承 `Generic[T]`**：复用代码

---

## 8. 自测题

### Q1：下面代码输出什么？

```python
from __future__ import annotations

def foo(x: int) -> str:
    return str(x)

print(foo.__annotations__)
```

<details>
<summary>查看答案</summary>

```python
{'x': 'int', 'return': 'str'}
```

注解是字符串，不是类型对象。
</details>

### Q2：下面哪种写法在 Python 3.9 + Pydantic v2 上最安全？

A. `x: int | None`
B. `x: Optional[int]`
C. `x: Union[int, None]`

<details>
<summary>查看答案</summary>

**B 和 C 最安全**。`Optional[int]` 就是 `Union[int, None]` 的别名。`int | None` 在 3.9 + Pydantic v2 上有兼容性 bug。
</details>

### Q3：`Mapped[int]` 是 Python 内置的吗？

<details>
<summary>查看答案</summary>

不是。`Mapped` 是 SQLAlchemy 2.0 在 `sqlalchemy.orm` 模块定义的泛型类，用来描述 ORM 列的类型。
</details>

---

## 9. 小结

| 概念 | 关键点 |
|------|--------|
| 类型注解 | hint 不是强制，运行时不校验 |
| `__future__ annotations` | 让注解变成字符串，延迟求值 |
| `Optional[X]` | 等价 `X \| None`，3.9 兼容性好 |
| `TypeVar + Generic` | 实现泛型类，如 `Page[T]` |
| `Mapped[X]` | SQLAlchemy 自定义注解，描述列类型 |

## 10. 下篇预告

下一篇讲 **FastAPI 框架入门与原理**：ASGI 是什么、依赖注入怎么工作、路由怎么匹配、生命周期钩子、为什么 FastAPI 比 Flask 快。

---

**延伸阅读**：
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 563 - Postponed Evaluation of Annotations](https://peps.python.org/pep-0563/)
- [PEP 604 - Allow writing union types as X | Y](https://peps.python.org/pep-0604/)
- [typing 模块文档](https://docs.python.org/3/library/typing.html)
