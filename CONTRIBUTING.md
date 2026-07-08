# 贡献指南

感谢你对本项目的关注！本文档指导你如何参与贡献。

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourname/fastapi-user-demo.git
cd fastapi-user-demo
```

### 2. 创建虚拟环境

```bash
python3 -m venv env
source env/bin/activate
```

### 3. 安装依赖

```bash
# 运行时依赖
pip install -r requirements.txt

# 开发依赖（测试、lint、类型检查）
pip install -r requirements-dev.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填写真实密码和 SECRET_KEY
```

### 5. 启动开发服务

```bash
make dev
# 或
python -m uvicorn main:app --reload
```

访问 http://127.0.0.1:8000/docs

---

## 🛠️ 开发流程

### 1. 创建分支

```bash
git checkout -b feat/your-feature
# 或
git checkout -b fix/your-bugfix
```

### 2. 写代码

遵循项目规范：
- 阅读 [CLAUDE.md](CLAUDE.md) 了解架构约定
- 代码注释用中文
- 每个函数有 docstring
- 类型注解完整

### 3. 本地检查

提交前跑检查：

```bash
make check
# 等价于：make lint typecheck test
```

或单独跑：
```bash
make lint       # flake8 代码风格
make typecheck  # mypy 类型检查
make test       # pytest 单元测试
make test-cov   # 测试 + 覆盖率
```

### 4. 提交

提交前 `pre-commit` 会自动检查（安装后）：

```bash
# 首次安装 pre-commit
pre-commit install

# 之后每次 commit 自动检查
git add .
git commit -m "feat: 添加邮箱字段"
```

#### 提交信息规范

格式：`<类型>: <描述>`

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | bug 修复 |
| `refactor` | 重构（不改功能） |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |
| `perf` | 性能优化 |
| `style` | 代码风格（不影响功能） |

示例：
```
feat: 添加用户邮箱字段和迁移
fix: 修复分页查询漏 count 的问题
docs: 补充 Alembic 迁移文档
```

### 5. 推送 + PR

```bash
git push origin feat/your-feature
```

在 GitHub 上创建 PR，描述清楚改了什么、为什么改。

---

## 📐 代码规范

### 架构约定

严格遵守四层架构（详见 [CLAUDE.md](CLAUDE.md)）：

```
API → Schema → Service → Repository → ORM
```

**禁止**：
- ❌ Service 层 import `HTTPException`
- ❌ Repository 层调 `db.commit()`
- ❌ `UserInDB` 作 `response_model`
- ❌ 用 `@app.on_event`（已弃用）
- ❌ 用 passlib（与 bcrypt 4.x+ 不兼容）

### 代码风格

- Python 3.9+ 兼容
- 用 `Optional[X]` 不用 `X | None`（兼容 3.9）
- 每行 ≤ 120 字符
- 4 空格缩进
- 中文注释和 docstring
- import 顺序：标准库 → 第三方 → 本项目

### 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `UserService` |
| 函数/变量 | snake_case | `create_user` |
| 常量 | UPPER_SNAKE | `MAX_RETRIES` |
| 私有 | _前缀 | `self._repo` |
| Schema 模型 | `UserCreate`/`UserOut`/`UserInDB` | |
| ORM 模型 | 单数 `User`，表名复数 `users` | |

### 加新字段流程

```bash
# 1. 改 ORM 模型 app/models/user.py
# 2. 改 Schema app/schema/user.py
# 3. 生成迁移
make migrate-new MSG="add email column"

# 4. 检查迁移脚本
cat alembic/versions/*_add_email_column.py

# 5. 执行迁移
make migrate

# 6. 改 Repository / Service / API
# 7. 加测试
# 8. make check
```

---

## 🧪 测试规范

### 测试分层

| 层 | 工具 | 说明 |
|----|------|------|
| 单元测试 | pytest | mock Repository 测 Service |
| 集成测试 | pytest + TestClient | 打完整 API |
| 端到端测试 | curl / httpx | 真实环境 |

### 测试覆盖率

- 目标：核心业务逻辑 ≥ 80%
- 工具：`pytest-cov`
- 命令：`make test-cov`

### 测试文件位置

```
tests/
├── conftest.py          # 公共 fixture
├── test_api.py          # 集成测试
├── test_user_service.py # Service 单元测试
└── test_user_repo.py    # Repository 单元测试
```

### 命名

- 文件：`test_<被测模块>.py`
- 函数：`test_<被测函数>_<场景>`
- 示例：`test_create_user_duplicate_username_raises()`

---

## 🐛 报 Bug

### 提 Issue 前

1. 搜 [已有 issue](https://github.com/yourname/fastapi-user-demo/issues) 避免重复
2. 用最新版本测试，可能已修复
3. 收集信息：复现步骤、期望、实际、环境

### Issue 模板

```markdown
**描述**
简短描述 bug

**复现步骤**
1. 调用 '...'
2. 输入 '...'
3. 看到错误

**期望行为**
应该 ...

**实际行为**
报错 ...

**环境**
- Python: 3.9.x
- MySQL: 8.4
- 项目版本: 1.0.0
- 是否 Docker: 是/否
```

---

## 💡 提建议

新功能建议欢迎提 Issue，描述：
- 使用场景
- 期望接口
- 替代方案

---

## 📚 文档

- [README.md](README.md) — 项目概览
- [CLAUDE.md](CLAUDE.md) — 架构约定
- [DETAIL.md](DETAIL.md) — 精细代码讲解
- [docs/](docs/) — 详细文档
- [docs/learning/](docs/learning/) — 学习系列文章

---

## 🤝 行为准则

- 友善对待所有贡献者
- 接受建设性批评
- 关注项目目标，不偏离主题

---

感谢你的贡献！🎉
