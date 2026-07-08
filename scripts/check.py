#!/usr/bin/env python3
"""Claude Code PostEdit 校验：用 AST 做精确检查，避免注释误报。

检查项：
1. Repository 层不能调用 db.commit()（事务由 Service 控制）
2. 不能用 @app.on_event / @router.on_event（已弃用）
3. 不能用 passlib（与 bcrypt 4.x+ 不兼容）
4. Service 层必须有 bcrypt 导入
5. 业务代码不能直接 print()（用 logger）

退出码：0 通过，1 失败
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []


def load_ast(path: Path) -> ast.AST | None:
    """加载文件 AST，语法错误时返回 None 并记录错误。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        ERRORS.append(f"❌ 语法错误 {path}: {e}")
        return None


class ForbiddenCallChecker(ast.NodeVisitor):
    """检查禁止的函数调用。"""

    def __init__(self, forbidden: list[str], file_path: Path, message: str):
        self.forbidden = forbidden  # 例如 ["db.commit", "self._db.commit"]
        self.file_path = file_path
        self.message = message

    def visit_Call(self, node: ast.Call):
        # 把调用目标转成字符串，如 "db.commit" / "self._db.commit"
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
                    ERRORS.append(
                        f"❌ {self.file_path}:{node.lineno} {self.message}"
                    )
        self.generic_visit(node)


class DecoratorChecker(ast.NodeVisitor):
    """检查禁止的装饰器。"""

    def __init__(self, forbidden_pattern: str, file_path: Path, message: str):
        self.pattern = forbidden_pattern  # 例如 "on_event"
        self.file_path = file_path
        self.message = message

    def visit_AsyncFunctionDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def _check_decorators(self, node):
        for dec in node.decorator_list:
            # dec 可能是 Attribute(@app.on_event) 或 Name(@something)
            if isinstance(dec, ast.Attribute) and dec.attr == self.pattern:
                ERRORS.append(f"❌ {self.file_path}:{node.lineno} {self.message}")
            elif isinstance(dec, ast.Call):
                inner = dec.func
                if isinstance(inner, ast.Attribute) and inner.attr == self.pattern:
                    ERRORS.append(f"❌ {self.file_path}:{node.lineno} {self.message}")


class ImportChecker(ast.NodeVisitor):
    """检查是否导入了某个模块。"""

    def __init__(self, target: str, found: list[bool]):
        self.target = target  # 例如 "bcrypt"
        self.found = found

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == self.target:
                self.found[0] = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == self.target or (node.module and node.module.startswith(self.target + ".")):
            self.found[0] = True
        self.generic_visit(node)


class PrintChecker(ast.NodeVisitor):
    """检查业务代码是否直接调用了 print()。"""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "print":
            ERRORS.append(f"❌ {self.file_path}:{node.lineno} 业务代码不能直接 print()，请用 logger")
        self.generic_visit(node)


def check_repository_no_commit() -> None:
    """Repository 层不能调 db.commit()。"""
    repo_dir = PROJECT_ROOT / "app" / "repository"
    if not repo_dir.exists():
        return
    for py in repo_dir.glob("*.py"):
        if py.name == "__init__.py":
            continue
        tree = load_ast(py)
        if tree is None:
            continue
        # 匹配 db.commit / self._db.commit / self.db.commit 等
        ForbiddenCallChecker(
            forbidden=["db.commit", "self._db.commit", "self.db.commit"],
            file_path=py,
            message="Repository 不应调用 db.commit()（事务由 Service 控制）",
        ).visit(tree)


def check_no_on_event() -> None:
    """不能用 @app.on_event / @router.on_event。"""
    for py in (PROJECT_ROOT / "app").rglob("*.py"):
        tree = load_ast(py)
        if tree is None:
            continue
        DecoratorChecker(
            forbidden_pattern="on_event",
            file_path=py,
            message="检测到 @on_event，已弃用，请用 lifespan",
        ).visit(tree)
    # main.py 也要检查
    main_py = PROJECT_ROOT / "main.py"
    if main_py.exists():
        tree = load_ast(main_py)
        if tree:
            DecoratorChecker(
                forbidden_pattern="on_event",
                file_path=main_py,
                message="检测到 @on_event，已弃用，请用 lifespan",
            ).visit(tree)


def check_no_passlib() -> None:
    """不能 import passlib。"""
    for py in (PROJECT_ROOT / "app").rglob("*.py"):
        tree = load_ast(py)
        if tree is None:
            continue
        found = [False]
        ImportChecker(target="passlib", found=found).visit(tree)
        if found[0]:
            ERRORS.append(f"❌ {py} 检测到 passlib 导入，请直接用 bcrypt")


def check_service_has_bcrypt() -> None:
    """Service 层必须有 bcrypt 导入。"""
    svc = PROJECT_ROOT / "app" / "service" / "user_service.py"
    if not svc.exists():
        return
    tree = load_ast(svc)
    if tree is None:
        return
    found = [False]
    ImportChecker(target="bcrypt", found=found).visit(tree)
    if not found[0]:
        ERRORS.append(f"❌ {svc} 缺少 'import bcrypt'")


def check_no_print_in_app() -> None:
    """业务代码不能直接 print()。

    例外：app/config.py 在 logger 初始化前执行，启动期错误用 print 到 stderr。
    """
    EXEMPT = {"config.py"}  # 启动期配置校验，logger 还没就绪
    for py in (PROJECT_ROOT / "app").rglob("*.py"):
        if "test_" in py.name or py.name in EXEMPT:
            continue
        tree = load_ast(py)
        if tree is None:
            continue
        PrintChecker(file_path=py).visit(tree)
    main_py = PROJECT_ROOT / "main.py"
    if main_py.exists():
        tree = load_ast(main_py)
        if tree:
            PrintChecker(file_path=main_py).visit(tree)


def check_syntax_all() -> None:
    """所有 Python 文件语法检查。"""
    for py in (PROJECT_ROOT / "app").rglob("*.py"):
        load_ast(py)
    for py in (PROJECT_ROOT / "tests").glob("*.py"):
        load_ast(py)
    main_py = PROJECT_ROOT / "main.py"
    if main_py.exists():
        load_ast(main_py)


def main() -> int:
    """主入口：跑所有检查。"""
    print("🔍 Claude PostEdit 校验启动（AST 模式）...", file=sys.stderr)

    check_syntax_all()
    check_repository_no_commit()
    check_no_on_event()
    check_no_passlib()
    check_service_has_bcrypt()
    check_no_print_in_app()

    if ERRORS:
        print("=" * 40, file=sys.stderr)
        print("❌ 校验失败：", file=sys.stderr)
        for e in ERRORS:
            print(e, file=sys.stderr)
        print("=" * 40, file=sys.stderr)
        return 1

    print("✅ AST 校验通过", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
