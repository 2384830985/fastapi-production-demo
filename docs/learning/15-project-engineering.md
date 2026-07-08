# 15 - 项目工程化指南
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


> 系列文章第 15 篇（附录 E）。本篇讲清楚项目从"能跑"到"生产级"补齐的工程基础设施，每个工具为什么需要、怎么配置、怎么用。

## 你将学到

- Makefile 统一命令
- .editorconfig 编辑器统一
- mypy 类型检查
- pre-commit git hook
- pytest + 覆盖率
- 依赖锁文件
- 启动时配置校验
- CORS 跨域
- 限流防爆破
- 开源项目标配（LICENSE/CHANGELOG/CONTRIBUTING）

---

## 1. Makefile：统一命令入口

### 1.1 为什么需要

没有 Makefile 时记长命令：

```bash
source env/bin/activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
alembic revision --autogenerate -m "msg"
pytest tests/ -v --cov=app
```

有 Makefile 后：

```bash
make dev
make migrate-new MSG="msg"
make test-cov
```

### 1.2 本项目的 Makefile

```makefile
dev:  ## 启动开发服务
	$(VENV)/bin/uvicorn main:app --reload

test:  ## 跑测试
	$(VENV)/bin/pytest tests/ -v

test-cov:  ## 测试 + 覆盖率
	$(VENV)/bin/pytest tests/ --cov=app --cov-report=term-missing

check: lint typecheck test  ## 一键检查

migrate:  ## 迁移到最新
	$(VENV)/bin/alembic upgrade head

migrate-new:  ## 生成迁移 make migrate-new MSG="..."
	$(VENV)/bin/alembic revision --autogenerate -m "$(MSG)"

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | ...
```

### 1.3 关键设计

- **`## 注释`**：`grep` 提取生成帮助
- **`$(VENV)/bin/`**：用 venv 里的命令，不依赖激活
- **`.PHONY`**：声明非文件目标，避免和同名文件冲突
- **`.DEFAULT_GOAL := help`**：`make` 不带参数时显示帮助

### 1.4 使用

```bash
make help          # 看所有命令
make install       # 装依赖
make dev           # 启动
make check         # 一键检查
make migrate-new MSG="add email"
```

---

## 2. .editorconfig：编辑器统一

### 2.1 为什么需要

不同编辑器默认缩进不同：
- VS Code 默认 4 空格
- Sublime 默认 tab
- 同事用不同编辑器，代码风格混乱

`.editorconfig` 让所有支持它的编辑器自动遵循统一配置。

### 2.2 本项目配置

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 4
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
max_line_length = 120

[*.{yml,yaml,json}]
indent_size = 2

[Makefile]
indent_style = tab  # Makefile 必须用 tab
```

### 2.3 编辑器支持

| 编辑器 | 支持 |
|--------|------|
| VS Code | 装 EditorConfig 扩展 |
| PyCharm | 内置 |
| Sublime | 装 EditorConfig 插件 |
| Vim | 装 editorconfig-vim |

---

## 3. mypy：类型检查

### 3.1 为什么需要

类型注解写了但没人检查，等于白写：

```python
def get_user(user_id: int) -> UserOut:
    return "not a user"  # 注解说返回 UserOut，实际返回 str，运行时不报错
```

mypy 在运行前检查类型，提前发现问题。

### 3.2 本项目配置（mypy.ini）

```ini
[mypy]
python_version = 3.9
strict = True                    # 严格模式
check_untyped_defs = True        # 检查未注解函数
warn_unused_ignores = True
warn_return_any = True
exclude = (?x)(^env/|^alembic/versions/)

[mypy-pymysql.*]
ignore_missing_imports = True    # 第三方库无类型存根

[mypy-tests.*]
strict = False                   # 测试代码放宽
```

### 3.3 使用

```bash
make typecheck
# 或
mypy app/ main.py --config-file mypy.ini
```

### 3.4 常见 mypy 错误

```python
# error: Missing return statement
def foo(x: int) -> int:  # 注解说返回 int，但没 return
    pass

# error: Argument 1 has incompatible type "str"; expected "int"
def add(x: int) -> int: ...
add("hello")  # 传错类型

# error: Item "None" of "Optional[int]" has no attribute "real"
def foo(x: Optional[int]):
    return x.real  # x 可能是 None
```

---

## 4. pre-commit：git hook

### 4.1 为什么需要

Claude Code Hook 在编辑后触发，但**git commit 前**也应该检查一次（防止绕过 Claude 直接 commit）。

pre-commit 是 Python 生态最流行的 git hook 管理工具。

### 4.2 本项目配置（.pre-commit-config.yaml）

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace    # 删行尾空格
      - id: end-of-file-fixer      # 文件末尾换行
      - id: check-yaml             # YAML 语法
      - id: check-merge-conflict   # 合并冲突标记
      - id: detect-private-key     # 阻止提交私钥

  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy

  - repo: local
    hooks:
      - id: project-ast-check
        name: 项目 AST 规范检查
        entry: python scripts/check.py
        language: system
```

### 4.3 安装使用

```bash
pip install pre-commit
pre-commit install   # 装 git hook（一次性）

# 之后每次 commit 自动检查
git add .
git commit -m "feat: ..."

# 手动跑全部
pre-commit run --all-files
```

### 4.4 与 Claude Hook 的关系

| 工具 | 触发时机 | 用途 |
|------|---------|------|
| Claude Hook | 编辑后 | AI 协作时实时反馈 |
| pre-commit | commit 前 | 兜底，防止绕过 Claude |

互补关系，都装最好。

---

## 5. pytest + 覆盖率

### 5.1 为什么需要

只有冒烟测试不够，要测各层独立：
- **单元测试**：mock Repository，测 Service 业务逻辑
- **集成测试**：打完整 API，验证端到端
- **覆盖率**：量化测试完整性

### 5.2 本项目测试结构

```
tests/
├── conftest.py              # 公共 fixture
├── test_api.py              # 集成测试
└── test_user_service.py     # Service 单元测试（19 个）
```

### 5.3 conftest.py：公共 fixture

```python
@pytest.fixture
def db_session():
    """每个测试函数独立的 in-memory SQLite session。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def client(db_session):
    """TestClient，db 依赖被替换为测试 session。"""
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**关键**：
- 用 SQLite in-memory，速度快（不连 MySQL）
- 每个测试函数独立 db，互不影响
- `dependency_overrides` 替换 db 依赖

### 5.4 单元测试示例

```python
class TestUserServiceCreate:
    def test_create_user_success(self):
        """正常创建用户。"""
        repo = MagicMock()
        repo.get_by_username.return_value = None
        repo.add.return_value = UserInDB(id=1, username="alice", hashed_password="x")

        svc = UserService(repo)
        result = svc.create_user(UserCreate(username="alice", password="secret123"))

        assert result.id == 1
        # 验证密码被哈希
        _, kwargs = repo.add.call_args
        assert kwargs["hashed_password"].startswith("$2b$12$")

    def test_create_user_duplicate_raises(self):
        """用户名重复抛 UserAlreadyExistsError。"""
        repo = MagicMock()
        repo.get_by_username.return_value = UserInDB(...)
        svc = UserService(repo)
        with pytest.raises(UserAlreadyExistsError):
            svc.create_user(UserCreate(username="alice", password="x"))
```

**关键**：
- `MagicMock` 模拟 Repository
- 只测 Service 业务逻辑，不连数据库
- 测正常路径 + 异常路径

### 5.5 覆盖率

```bash
make test-cov
# 输出：
# Name                          Stmts   Miss  Cover
# app/service/user_service.py      97     16    84%
```

目标：核心业务 ≥ 80%。

---

## 6. 依赖锁文件

### 6.1 为什么需要

`requirements.txt` 用 `>=`：

```
fastapi>=0.115.0
```

每次 `pip install` 装的版本可能不同，导致：
- 开发环境正常，生产报错（依赖版本变了）
- CI 和本地行为不一致
- 复现 bug 困难

### 6.2 锁文件方案

用 `pip-compile`（pip-tools）生成锁文件，固定所有依赖版本：

```bash
pip install pip-tools
pip-compile --output-file=requirements.lock requirements.txt
```

`requirements.lock` 内容：

```
fastapi==0.128.8
pydantic==2.13.4
sqlalchemy==2.0.51
...
```

所有依赖（包括传递依赖）都固定精确版本。

### 6.3 使用

```bash
# 生产部署
pip install -r requirements.lock  # 用锁文件，版本一致

# 开发加新依赖
vim requirements.txt  # 加 fastapi
make lock             # 重新生成锁文件
```

### 6.4 本项目的锁文件

```
requirements.lock       # 运行时依赖锁
requirements-dev.lock   # 开发依赖锁
```

---

## 7. 启动时配置校验

### 7.1 为什么需要

`SECRET_KEY` 没设置，应用能启动，但第一次签发 JWT 时才报错。用户登录时才发现问题，体验差。

**fail-fast 原则**：启动时就检查，配置缺失立即退出。

### 7.2 本项目实现（app/config.py）

```python
REQUIRED_ENV_VARS = ["DB_USER", "DB_PASSWORD", "DB_HOST", "SECRET_KEY", ...]

def validate_config():
    errors = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            errors.append(f"缺少环境变量: {var}")

    # 敏感变量弱默认值警告
    if os.getenv("SECRET_KEY") in ["please_change_me", ...]:
        print("⚠️ SECRET_KEY 使用弱默认值")

    if errors:
        print("❌ 配置校验失败：")
        for e in errors:
            print(e)
        sys.exit(1)
```

### 7.3 在 main.py 调用

```python
from app.config import validate_config

setup_logging()
validate_config()  # 启动时校验，失败立即退出
```

### 7.4 效果

```bash
$ unset SECRET_KEY
$ python -m uvicorn main:app
❌ 配置校验失败：
  ❌ 缺少环境变量: SECRET_KEY

请参考 .env.example 配置 .env 文件
```

启动即失败，不会带到运行时。

---

## 8. CORS：跨域配置

### 8.1 为什么需要

前端 `http://localhost:3000` 调后端 `http://localhost:8000`，浏览器会拦截（跨域）。

后端要显式允许前端域名。

### 8.2 本项目配置

```python
from fastapi.middleware.cors import CORSMiddleware

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 8.3 配置项

| 配置 | 作用 |
|------|------|
| `allow_origins` | 允许的前端域名列表 |
| `allow_credentials` | 是否允许带 cookie |
| `allow_methods` | 允许的 HTTP 方法 |
| `allow_headers` | 允许的请求头 |

### 8.4 生产环境注意

```bash
# ❌ 危险：允许所有域名
CORS_ORIGINS=*

# ✅ 安全：具体域名
CORS_ORIGINS=https://yourapp.com,https://www.yourapp.com
```

---

## 9. 限流：防暴力破解

### 9.1 为什么需要

没有限流，攻击者可以：
- 每秒发 10000 次登录请求，暴力破解密码
- DDoS 把服务打挂
- 爬虫抓走所有数据

### 9.2 本项目实现（slowapi）

```python
# app/ratelimit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)  # 按 IP 限流

def setup_ratelimit(app):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# 限流策略
RATE_LOGIN = "10/minute"   # 登录：每分钟 10 次
RATE_WRITE = "30/minute"   # 写操作：每分钟 30 次
RATE_READ = "60/minute"    # 读操作：每分钟 60 次
```

### 9.3 在路由上用

```python
from app.ratelimit import limiter, RATE_LOGIN

@router.post("/token")
@limiter.limit(RATE_LOGIN)  # 登录接口限流
def login(request: Request, ...):
    ...
```

### 9.4 超限响应

```
HTTP 429 Too Many Requests
```

### 9.5 限流策略选择

| 接口 | 限流 | 原因 |
|------|------|------|
| 登录 | 10/min | 防暴力破解 |
| 注册 | 5/min | 防批量注册 |
| 写操作 | 30/min | 防滥用 |
| 读操作 | 60/min | 防爬虫 |
| 公开接口 | 100/min | 平衡 |

---

## 10. 开源项目标配

### 10.1 LICENSE

```text
MIT License

Copyright (c) 2026 ...

Permission is hereby granted, free of charge, to any person obtaining a copy...
```

**选择协议**：
- **MIT**：最宽松，随便用
- **Apache 2.0**：宽松 + 专利保护
- **GPL**：传染性，衍生作品必须开源

本项目用 MIT。

### 10.2 CHANGELOG.md

记录版本变更，遵循 [Keep a Changelog](https://keepachangelog.com/) 格式：

```markdown
## [1.0.0] - 2026-07-08

### Added
- 四层架构
- JWT 鉴权
- ...

### Fixed
- 修复分页查询漏 count

### Security
- 密码用 bcrypt 哈希
```

变更类型：Added / Changed / Deprecated / Removed / Fixed / Security。

### 10.3 CONTRIBUTING.md

指导贡献者：
- 如何搭建开发环境
- 代码规范
- 提交规范
- PR 流程
- 测试要求

---

## 11. 工程化清单

部署前检查：

### 代码质量
- [x] Makefile 统一命令
- [x] .editorconfig 编辑器统一
- [x] mypy 类型检查
- [x] flake8 代码风格
- [x] pre-commit git hook
- [x] Claude Code Hook

### 测试
- [x] pytest 单元测试（19 个）
- [x] pytest-cov 覆盖率（84%）
- [x] 集成测试（端到端）
- [ ] 覆盖率 ≥ 80%（当前 84% ✅）

### 依赖管理
- [x] requirements.txt 运行时依赖
- [x] requirements-dev.txt 开发依赖
- [x] requirements.lock 锁文件
- [x] requirements-dev.lock 开发锁文件

### 安全
- [x] 启动时配置校验（fail-fast）
- [x] CORS 配置
- [x] 限流（slowapi）
- [x] JWT 鉴权
- [x] bcrypt 密码哈希
- [x] 生产关闭 /docs

### 文档
- [x] README.md 项目概览
- [x] DETAIL.md 精细讲解
- [x] CLAUDE.md 协作规范
- [x] CONTRIBUTING.md 贡献指南
- [x] CHANGELOG.md 变更日志
- [x] LICENSE 协议
- [x] docs/ 详细文档
- [x] docs/learning/ 学习系列

### 部署
- [x] Dockerfile 多阶段构建
- [x] docker-compose 编排
- [x] GitHub Actions CI/CD
- [x] 健康检查
- [x] 非 root 用户

---

## 12. 自测题

### Q1：为什么需要锁文件？

<details>
<summary>查看答案</summary>

`requirements.txt` 用 `>=`，每次安装版本可能不同，导致开发/生产环境不一致。锁文件固定所有依赖（含传递依赖）的精确版本，保证构建可复现。
</details>

### Q2：fail-fast 配置校验的好处？

<details>
<summary>查看答案</summary>

启动时就发现配置缺失，而不是运行时才报错。避免应用带病启动，用户第一次操作时才发现问题。
</details>

### Q3：Claude Hook vs pre-commit 区别？

<details>
<summary>查看答案</summary>

- Claude Hook：编辑后触发，AI 协作时实时反馈
- pre-commit：commit 前触发，兜底防止绕过 Claude

互补关系，都装最好。
</details>

### Q4：单元测试为什么用 SQLite in-memory 而不是 MySQL？

<details>
<summary>查看答案</summary>

- 速度快：in-memory 不需要网络和磁盘 I/O
- 隔离性好：每个测试函数独立 db
- 不依赖外部服务（CI 友好）
- 不影响真实数据
</details>

---

## 13. 小结

| 工具 | 解决问题 |
|------|---------|
| Makefile | 命令记不住 |
| .editorconfig | 编辑器风格不一 |
| mypy | 类型注解没人检查 |
| pre-commit | commit 前兜底 |
| pytest + cov | 测试覆盖率 |
| requirements.lock | 构建不可复现 |
| 配置校验 | 启动不 fail-fast |
| CORS | 跨域被拦截 |
| slowapi | 暴力破解 / DDoS |
| LICENSE/CHANGELOG/CONTRIBUTING | 开源标配 |

**核心原则**：
- ✅ 自动化（能自动的不手动）
- ✅ fail-fast（早失败早恢复）
- ✅ 可复现（锁文件 + 容器）
- ✅ 可观测（日志 + 监控 + 健康检查）
- ✅ 最小权限（非 root、限流、CORS 白名单）

---

## 🎉 系列完结

恭喜！你现在拥有一个**真正生产级**的 FastAPI 项目：

- 完整四层架构
- 完整工程基础设施
- 完整文档体系（14 篇正文 + 4 篇附录 + 本篇）
- 完整测试体系（单元 + 集成）
- 完整部署链路（Docker + CI/CD）

**回到 [总索引](README.md) 复习**，或开始你的下一个项目！🚀

---

**延伸阅读**：
- [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
- [Semantic Versioning](https://semver.org/lang/zh-CN/)
- [pre-commit 文档](https://pre-commit.com/)
- [pip-tools 文档](https://pip-tools.readthedocs.io/)
- [slowapi 文档](https://slowapi.readthedocs.io/)
- [EditorConfig](https://editorconfig.org/)
