# 变更日志 (Changelog)
> 📦 **GitHub 仓库**：[https://github.com/2384830985/fastapi-production-demo](https://github.com/2384830985/fastapi-production-demo)


本项目所有重要变更记录于此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## 版本号规则

- **MAJOR**：不兼容的 API 变更
- **MINOR**：向下兼容的新功能
- **PATCH**：向下兼容的 bug 修复

## [Unreleased]

### Added
- 待发布内容写在这里

## [1.0.0] - 2026-07-08

### Added
- ✅ 四层架构：API / Schema / Service / Repository
- ✅ MySQL 持久化（SQLAlchemy 2.0 + PyMySQL）
- ✅ JWT 鉴权（登录 / token 刷新）
- ✅ bcrypt 密码哈希（rounds=12）
- ✅ Pydantic v2 数据校验
- ✅ Alembic 数据库迁移
- ✅ 结构化日志（python logging）
- ✅ 全局异常处理器
- ✅ 分页查询（泛型 `Page[T]`）
- ✅ 健康检查接口（`/` 和 `/health`）
- ✅ 事务边界设计（Repository 不 commit）
- ✅ `lifespan` 生命周期钩子
- ✅ 环境变量配置管理（`.env` + `python-dotenv`）
- ✅ Docker 多阶段构建
- ✅ docker-compose 编排（app + mysql）
- ✅ GitHub Actions CI/CD 流水线
- ✅ Claude Code Hook + AST 静态校验
- ✅ Makefile 统一命令
- ✅ `.editorconfig` 编辑器统一
- ✅ mypy 类型检查
- ✅ pre-commit git hook
- ✅ pytest + pytest-cov 单元测试
- ✅ 依赖锁文件（requirements.lock）
- ✅ 启动时环境变量校验（fail-fast）
- ✅ CORS 配置
- ✅ 限流（slowapi）
- ✅ 完整文档（README / DETAIL / CLAUDE / docs/ / learning/）

### Security
- 密码用 bcrypt 哈希，不存明文
- `UserOut` 响应模型不含密码字段
- 500 错误不暴露内部细节
- 生产环境关闭 `/docs` `/redoc` `/openapi.json`
- `${VAR:?}` 强制要求敏感环境变量
- 非 root 用户运行容器

## 变更类型说明

- **Added**：新增功能
- **Changed**：现有功能变更
- **Deprecated**：即将移除的功能
- **Removed**：已移除的功能
- **Fixed**：bug 修复
- **Security**：安全相关变更

## 链接

[Unreleased]: https://github.com/yourname/fastapi-user-demo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourname/fastapi-user-demo/releases/tag/v1.0.0
