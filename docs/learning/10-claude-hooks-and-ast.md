# 10 - Claude Code Hook 与 AST 静态分析
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 10 篇（终篇）。本篇讲清楚 Claude Code Hook 机制、Python `ast` 模块、AST 静态分析实现、自定义校验规则。

## 你将学到

- Claude Code Hook 机制
- Hook 配置（PostEdit / PreCommit）
- Python `ast` 模块原理
- `NodeVisitor` 模式
- AST 静态分析实现
- 为什么用 AST 而不是正则

---

## 1. Claude Code Hook 机制

### 1.1 Hook 是什么

Claude Code Hook 是 Claude 编辑文件后自动执行的脚本，用于校验代码、跑测试、强制规范。

```
Claude 编辑文件
   ↓
触发 Hook（PostEdit）
   ↓
执行校验脚本
   ↓
退出码 0：通过，继续工作
退出码 非 0：失败，Claude 看到错误并修复
```

### 1.2 本项目的 Hook 设计目标

- 编辑 Python 文件后自动校验
- 检查项目规范（不 commit、不用 passlib 等）
- 跑测试
- 失败时给 Claude 清晰反馈

### 1.3 Hook 类型

| Hook | 触发时机 |
|------|---------|
| PostEdit | 编辑文件后 |
| PreCommit | git commit 前 |
| PostCommit | git commit 后 |
| PrePush | git push 前 |

本项目用 PostEdit（编辑后立即校验）和 PreCommit（提交前最后检查）。

---

## 2. Hook 配置

### 2.1 配置文件位置

```
项目根/.claude/settings.json
```

### 2.2 本项目的配置

```json
{
  "version": "0.0.1",
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(pip:*)",
      ...
    ]
  },
  "hooks": {
    "PostEdit": [
      {
        "matcher": "**/*.py",
        "hooks": [
          {
            "type": "command",
            "command": "scripts/check.sh",
            "timeout": 60
          }
        ]
      }
    ],
    "PreCommit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "scripts/check.sh",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### 2.3 配置字段

| 字段 | 说明 |
|------|------|
| `matcher` | 文件匹配模式，`**/*.py` 匹配所有 .py 文件 |
| `type: "command"` | 执行命令（目前只支持 command） |
| `command` | 要执行的脚本 |
| `timeout` | 超时秒数 |

### 2.4 Hook 输入

Hook 执行时，Claude 通过 stdin 传入 JSON：

```json
{
  "files": [
    {"path": "app/service/user_service.py"},
    {"path": "app/api/users.py"}
  ],
  "session_id": "xxx",
  "tool": "Edit"
}
```

脚本可以从 stdin 读取，知道哪些文件被修改。

### 2.5 Hook 输出

- **退出码 0**：通过，Claude 继续工作
- **退出码非 0**：失败，stderr 内容反馈给 Claude

Claude 看到错误后会尝试修复，再触发 Hook，循环直到通过。

---

## 3. Python `ast` 模块

### 3.1 什么是 AST

AST = Abstract Syntax Tree（抽象语法树）。Python 代码在执行前会被解析成 AST：

```python
# 源代码
x = 1 + 2

# AST 简化表示
Assign(
    targets=[Name(id='x')],
    value=BinOp(
        left=Constant(value=1),
        op=Add(),
        right=Constant(value=2)
    )
)
```

### 3.2 Python `ast` 模块

```python
import ast

source = """
x = 1 + 2
print(x)
"""

tree = ast.parse(source)
print(ast.dump(tree))
# Module(body=[
#     Assign(targets=[Name(id='x')], value=BinOp(...)),
#     Expr(value=Call(func=Name(id='print'), args=[Name(id='x')]))
# ])
```

`ast.parse` 把源码解析成 AST 对象。

### 3.3 为什么用 AST 而不是正则

考虑检查"Repository 层不能调 `db.commit()`"：

**正则方案**：

```bash
grep "db.commit()" app/repository/user_repo.py
```

**问题**：

```python
# 注释里的字样会被误报
"""注意：本类不调用 db.commit()，事务由 Service 层控制。"""
```

正则匹配到注释，误报。

**AST 方案**：

```python
class ForbiddenCallChecker(ast.NodeVisitor):
    def visit_Call(self, node):
        # 只看真正的函数调用，不看注释
        if is_db_commit(node.func):
            report_error(node.lineno)
```

AST 解析的是语法树，注释在解析时被丢弃，**零误报**。

### 3.4 AST 节点类型

| 节点 | 对应语法 |
|------|---------|
| `Assign` | `x = 1` |
| `Call` | `func()` |
| `Name` | `x` |
| `Attribute` | `obj.attr` |
| `FunctionDef` | `def foo():` |
| `ClassDef` | `class Foo:` |
| `Import` | `import x` |
| `ImportFrom` | `from x import y` |
| `Return` | `return x` |
| `If` | `if x:` |
| `For` | `for x in y:` |

完整列表见 [ast 模块文档](https://docs.python.org/3/library/ast.html)。

---

## 4. `NodeVisitor` 模式

### 4.1 NodeVisitor 是什么

`ast.NodeVisitor` 是访问者模式实现，遍历 AST 节点。

```python
class MyVisitor(ast.NodeVisitor):
    def visit_Call(self, node):
        # 访问到 Call 节点时执行
        print(f"调用函数: {ast.dump(node.func)}")
        self.generic_visit(node)  # 继续遍历子节点

    def visit_Name(self, node):
        # 访问到 Name 节点时执行
        print(f"变量名: {node.id}")
        self.generic_visit(node)
```

### 4.2 工作流程

```
visitor.visit(tree)
   ↓
根据节点类型调用对应 visit_XXX 方法
   ↓
generic_visit 继续遍历子节点
   ↓
直到所有节点访问完
```

### 4.3 关键方法

| 方法 | 作用 |
|------|------|
| `visit(node)` | 入口，根据节点类型分发 |
| `visit_XXX(node)` | 处理特定类型节点 |
| `generic_visit(node)` | 继续遍历子节点（必须调用，否则不深入） |

### 4.4 不调 `generic_visit` 的后果

```python
class MyVisitor(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        print(f"发现函数: {node.name}")
        # 忘了 self.generic_visit(node)
        # 函数体里的节点不会被访问
```

`generic_visit` 负责遍历子节点，不调用就只看顶层。

---

## 5. 本项目的 AST 校验实现

### 5.1 校验项

| 规则 | 错误信息 |
|------|---------|
| Repository 调 `db.commit()` | Repository 不应调用 db.commit() |
| 用 `@on_event` | 检测到 @on_event，已弃用，请用 lifespan |
| import passlib | 检测到 passlib，请直接用 bcrypt |
| Service 缺 bcrypt | 缺少 import bcrypt |
| 业务代码 `print()` | 业务代码不能直接 print()，请用 logger |
| Python 语法错误 | 语法错误 |

### 5.2 检查禁止调用：`ForbiddenCallChecker`

```python
class ForbiddenCallChecker(ast.NodeVisitor):
    """检查禁止的函数调用。"""

    def __init__(self, forbidden, file_path, message):
        self.forbidden = forbidden  # 例如 ["db.commit", "self._db.commit"]
        self.file_path = file_path
        self.message = message

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute):
            # 拼接属性链：a.b.c -> "a.b.c"
            parts = []
            cur = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                chain = ".".join(reversed(parts))
                if chain in self.forbidden:
                    ERRORS.append(f"❌ {self.file_path}:{node.lineno} {self.message}")
        self.generic_visit(node)
```

**工作原理**：

对于代码 `db.commit()`：
- AST 节点是 `Call(func=Attribute(attr='commit', value=Name(id='db')))`
- 拼接成 `"db.commit"`
- 检查是否在禁止列表里

对于 `self._db.commit()`：
- `Call(func=Attribute(attr='commit', value=Attribute(attr='_db', value=Name(id='self'))))`
- 拼接成 `"self._db.commit"`
- 检查是否在禁止列表里

### 5.3 检查禁止装饰器：`DecoratorChecker`

```python
class DecoratorChecker(ast.NodeVisitor):
    """检查禁止的装饰器。"""

    def __init__(self, forbidden_pattern, file_path, message):
        self.pattern = forbidden_pattern  # "on_event"
        self.file_path = file_path
        self.message = message

    def visit_FunctionDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def _check_decorators(self, node):
        for dec in node.decorator_list:
            # @app.on_event → Attribute(attr='on_event')
            if isinstance(dec, ast.Attribute) and dec.attr == self.pattern:
                ERRORS.append(f"❌ {self.file_path}:{node.lineno} {self.message}")
            # @app.on_event("startup") → Call(func=Attribute(attr='on_event'))
            elif isinstance(dec, ast.Call):
                inner = dec.func
                if isinstance(inner, ast.Attribute) and inner.attr == self.pattern:
                    ERRORS.append(f"❌ {self.file_path}:{node.lineno} {self.message}")
```

**关键**：装饰器可能是两种形式：
- `@app.on_event` → `Attribute`
- `@app.on_event("startup")` → `Call(func=Attribute)`

两种都要检查。

### 5.4 检查导入：`ImportChecker`

```python
class ImportChecker(ast.NodeVisitor):
    """检查是否导入了某个模块。"""

    def __init__(self, target, found):
        self.target = target  # "bcrypt"
        self.found = found    # [False]，用 list 包装可变状态

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == self.target:
                self.found[0] = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == self.target or \
           (node.module and node.module.startswith(self.target + ".")):
            self.found[0] = True
        self.generic_visit(node)
```

**为什么 `found` 用 list**：Python 闭包不能直接修改外层变量，用 list 包装可变对象绕过限制。

### 5.5 检查 print：`PrintChecker`

```python
class PrintChecker(ast.NodeVisitor):
    def __init__(self, file_path):
        self.file_path = file_path

    def visit_Call(self, node):
        func = node.func
        # print(x) → Call(func=Name(id='print'))
        if isinstance(func, ast.Name) and func.id == "print":
            ERRORS.append(f"❌ {self.file_path}:{node.lineno} 业务代码不能直接 print()，请用 logger")
        self.generic_visit(node)
```

只匹配 `print(...)`，不匹配 `logger.info(...)`。

### 5.6 主入口

```python
def main() -> int:
    print("🔍 Claude PostEdit 校验启动（AST 模式）...", file=sys.stderr)

    check_syntax_all()              # 1. 语法检查
    check_repository_no_commit()    # 2. Repository 不 commit
    check_no_on_event()             # 3. 不用 @on_event
    check_no_passlib()              # 4. 不用 passlib
    check_service_has_bcrypt()      # 5. Service 有 bcrypt
    check_no_print_in_app()         # 6. 不直接 print

    if ERRORS:
        for e in ERRORS:
            print(e, file=sys.stderr)
        return 1
    return 0
```

---

## 6. Hook 脚本入口

### 6.1 check.sh

```bash
#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -f "env/bin/activate" ]; then
    source env/bin/activate
fi

# 读取 stdin（Claude 传入的 JSON）
INPUT=$(cat)

# 1. AST 校验
if ! python scripts/check.py; then
    exit 1
fi

# 2. 跑测试（修改了 app/ 或 tests/ 时）
NEED_TEST=false
if command -v jq &> /dev/null && [ -n "$INPUT" ]; then
    FILES=$(echo "$INPUT" | jq -r '.files[]?.path // empty')
    for f in $FILES; do
        if [[ "$f" == app/* ]] || [[ "$f" == tests/* ]]; then
            NEED_TEST=true
            break
        fi
    done
fi

if [ "$NEED_TEST" = true ] && [ -f "tests/test_api.py" ]; then
    if ! python tests/test_api.py; then
        exit 1
    fi
fi

exit 0
```

### 6.2 关键设计

#### `set -e`

任何命令失败立即退出，不继续执行。

#### 激活 venv

```bash
source env/bin/activate
```

确保 `python`、`alembic` 等命令可用。

#### stdin 读取

```bash
INPUT=$(cat)
```

Claude 通过 stdin 传 JSON，`cat` 读取全部。

#### jq 解析 JSON

```bash
FILES=$(echo "$INPUT" | jq -r '.files[]?.path // empty')
```

`jq` 是命令行 JSON 处理工具，没装时降级（保守地跑测试）。

---

## 7. AST 校验的优势

### 7.1 精确无误报

```python
# 注释里的字样不会误报
"""注意：本类不调用 db.commit()"""  # AST 解析时被丢弃

# 字符串里的字样不会误报
error_msg = "请勿调用 db.commit()"  # 是 Constant 节点，不是 Call
```

### 7.2 能识别复杂模式

```python
# 正则很难匹配这种链式调用
self._db.commit()
self.db.commit()
db.commit()

# AST 拼接属性链，一次匹配
```

### 7.3 能跨节点分析

```python
# 检查"函数是否有 return"
def has_return(func_node):
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return):
            return True
    return False
```

正则做不到跨节点分析。

### 7.4 能拿到行号

```python
ERRORS.append(f"❌ {file_path}:{node.lineno} {message}")
# 输出：❌ app/repository/user_repo.py:127 Repository 不应调用 db.commit()
```

行号让 Claude 快速定位问题。

---

## 8. 扩展校验规则

### 8.1 检查函数复杂度

```python
class ComplexityChecker(ast.NodeVisitor):
    """检查函数圈复杂度（if/for/while 数量）"""

    def __init__(self, max_complexity=10):
        self.max_complexity = max_complexity

    def visit_FunctionDef(self, node):
        complexity = 0
        for n in ast.walk(node):
            if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
        if complexity > self.max_complexity:
            print(f"⚠️ {node.name} 复杂度过高: {complexity}")
        self.generic_visit(node)
```

### 8.2 检查未使用的 import

```python
def check_unused_imports(tree, source):
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.asname or alias.name)

    for imp in imports:
        if imp not in source[source.index('import'):]:  # 简化版
            print(f"⚠️ 未使用的 import: {imp}")
```

实际工具用 `autoflake` 或 `flake8-F401`。

### 8.3 检查 TODO/FIXME

```python
class TodoChecker(ast.NodeVisitor):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if "TODO" in node.value.value or "FIXME" in node.value.value:
                print(f"⚠️ {node.lineno} 发现 TODO/FIXME")
        self.generic_visit(node)
```

### 8.4 检查硬编码密码

```python
SECRET_PATTERNS = ["password", "secret", "api_key", "token"]

class HardcodedSecretChecker(ast.NodeVisitor):
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and \
               any(p in target.id.lower() for p in SECRET_PATTERNS):
                if isinstance(node.value, ast.Constant) and \
                   isinstance(node.value.value, str) and \
                   len(node.value.value) > 0:
                    print(f"❌ {node.lineno} 疑似硬编码密钥: {target.id}")
        self.generic_visit(node)
```

---

## 9. Hook 调试

### 9.1 手动测试

```bash
# 模拟 Claude 传入的 JSON
echo '{"files":[{"path":"app/service/user_service.py"}]}' | ./scripts/check.sh

# 查看退出码
echo $?
```

### 9.2 看 stderr

Hook 的 stderr 会反馈给 Claude：

```bash
./scripts/check.sh 2>&1
```

### 9.3 测试单个文件

```bash
python scripts/check.py  # 直接跑 AST 校验
```

### 9.4 模拟错误

```bash
# 故意写错
echo "def test(): db.commit()" >> app/repository/user_repo.py

# 跑校验
python scripts/check.py
# ❌ app/repository/user_repo.py:127 Repository 不应调用 db.commit()
```

---

## 10. Hook 的价值

### 10.1 自动强制规范

Claude 编辑代码后**立即校验**，违反规范立刻报错，Claude 自动修复。

### 10.2 比人工 review 快

人工 review 容易漏，Hook 100% 执行，每次都检查。

### 10.3 比单元测试早

单元测试要运行代码，Hook 在编辑时就检查，反馈更快。

### 10.4 比lint 工具针对性更强

flake8 / pylint 是通用规则，Hook 能检查项目特定规范（如"Repository 不 commit"）。

---

## 11. 自测题

### Q1：为什么用 AST 而不是 grep 检查代码规范？

<details>
<summary>查看答案</summary>

- grep 会匹配注释和字符串里的字样，误报
- AST 只看真正代码，零误报
- AST 能识别复杂模式（链式调用、跨节点分析）
- AST 能拿到行号，定位精准
</details>

### Q2：`NodeVisitor` 的 `generic_visit` 不调用会怎样？

<details>
<summary>查看答案</summary>

不调 `generic_visit` 不会遍历子节点，只看顶层。例如 `visit_FunctionDef` 不调 `generic_visit`，函数体里的代码不会被检查。
</details>

### Q3：Hook 的退出码有什么意义？

<details>
<summary>查看答案</summary>

- 退出码 0：通过，Claude 继续工作
- 退出码非 0：失败，stderr 反馈给 Claude，Claude 会尝试修复
</details>

### Q4：如何让 Hook 只在修改特定文件时跑测试？

<details>
<summary>查看答案</summary>

从 stdin 读取 Claude 传入的 JSON，解析 `.files[].path`，判断是否包含 `app/` 或 `tests/`，是才跑测试。
</details>

---

## 12. 小结

| 概念 | 关键点 |
|------|--------|
| Claude Code Hook | 编辑后自动执行校验 |
| PostEdit | 编辑文件后触发 |
| PreCommit | git commit 前触发 |
| `ast.parse` | 源码解析成 AST |
| `NodeVisitor` | 访问者模式遍历 AST |
| `visit_XXX` | 处理特定类型节点 |
| `generic_visit` | 继续遍历子节点 |
| AST vs grep | AST 零误报，能跨节点分析 |

**Hook 价值**：
- ✅ 自动强制规范
- ✅ 比 review 快
- ✅ 比单测早
- ✅ 比通用 lint 针对性强

---

## 🎉 系列完结

恭喜你读完 10 篇文章！现在你已经掌握：

| 阶段 | 技能 |
|------|------|
| 基础 | Python 类型注解、FastAPI、Pydantic v2 |
| 数据 | SQLAlchemy 2.0、Alembic 迁移 |
| 架构 | 四层架构、密码安全、事务、异常处理、日志 |
| 部署 | Docker、CI/CD、Claude Hook、AST 分析 |

**下一步建议**：
1. 对照源码通读项目，验证理解
2. 自己动手扩展功能（加 email 字段、加订单模块）
3. 写单元测试，提升覆盖率
4. 部署到云服务器，实战验证

祝你写出更好的生产级项目！

---

**延伸阅读**：
- [Python ast 模块文档](https://docs.python.org/3/library/ast.html)
- [Green Tree Snakes - Python AST 指南](https://greentreesnakes.readthedocs.io/)
- [Claude Code Hook 文档](https://docs.claude.com/en/docs/claude-code/hooks)
- [访问者模式](https://refactoring.guru/design-patterns/visitor)
