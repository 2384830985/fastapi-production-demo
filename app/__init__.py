"""应用包：FastAPI 用户管理项目根包。

四层架构：
- API 层 (app.api)        — 路由、HTTP 异常映射
- Schema 层 (app.schema)  — Pydantic v2 数据校验模型
- Service 层 (app.service)— 业务逻辑、密码哈希
- Repository 层 (app.repository) — SQLAlchemy ORM 数据访问

辅助模块：
- app.db     — 数据库引擎、Session、Base
- app.models — ORM 模型（对应数据库表）
"""
