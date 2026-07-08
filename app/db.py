"""数据库连接配置：引擎、会话工厂、Base。

使用 SQLAlchemy 2.0 同步 API，驱动用 PyMySQL（兼容 MySQL 9.x 的 caching_sha2_password）。
所有敏感配置（密码等）通过环境变量读取，不硬编码在代码里。
"""
from __future__ import annotations

import os
# Generator 用于 yield 函数的返回类型注解（get_db 用）
from typing import Generator

# python-dotenv：从 .env 文件加载环境变量到 os.environ
# load_dotenv() 会在当前目录及父目录查找 .env 文件
from dotenv import load_dotenv

# SQLAlchemy 2.0 推荐的导入方式
# - create_engine: 创建数据库引擎（连接池）
# - sessionmaker: 会话工厂，每次调用返回一个 Session
# - DeclarativeBase: 所有 ORM 模型的基类
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

# 加载 .env 文件中的环境变量
load_dotenv()

# 数据库连接配置（从环境变量读取，提供默认值仅用于本地开发）
# os.getenv(name, default) 不存在时返回 default
# 生产环境应在系统环境变量里设置，不要依赖 .env
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "testdb")

# 数据库连接 URL
# mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
# - pymysql 是 Python 的纯 Python MySQL 驱动
# - charset=utf8mb4 支持完整的 emoji 和中文
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# 创建引擎
# - pool_pre_ping=True: 每次借出连接前先 ping 一下，避免拿到失效连接
# - pool_recycle=3600: 连接每小时回收一次（MySQL 默认 8 小时超时，提前回收更稳）
# - echo=False: True 时打印所有 SQL，调试可用
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

# 会话工厂
# - autocommit=False: 不自动提交，需要手动 commit
# - autoflush=False: 不自动 flush，避免意外的 SQL 执行
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，继承后通过 metadata 管理表结构。"""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：每个请求获得一个独立的数据库 Session。

    用法：
        @app.get("/")
        def index(db: Session = Depends(get_db)):
            db.query(User).all()

    用 yield 写法保证请求结束自动关闭连接。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
