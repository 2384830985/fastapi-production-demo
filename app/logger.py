"""日志配置：统一格式、级别、输出目标。

设计原则：
- 业务代码用 logging.getLogger(__name__) 拿 logger，不直接配置
- 配置集中在本文件，启动时调用 setup_logging() 一次
- 日志格式包含时间、级别、模块、行号、消息，便于排查
- 级别可由环境变量 LOG_LEVEL 控制（DEBUG/INFO/WARNING/ERROR）
"""
from __future__ import annotations

import logging
import os
import sys

# 日志格式：时间 | 级别 | 模块名:行号 | 消息
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """初始化全局日志配置。应在应用启动时调用一次。

    日志级别由环境变量 LOG_LEVEL 控制，默认 INFO。
    输出到 stdout，便于容器收集（docker logs / kubectl logs）。
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # 配置 root logger
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,  # 容器化部署推荐 stdout，由 docker/k8s 收集
        force=True,         # Python 3.8+，覆盖已有配置
    )

    # 降低第三方库的日志级别（避免 SQLAlchemy/uvicorn 刷屏）
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # 测试一下
    logging.getLogger(__name__).info("📝 日志系统已初始化（级别=%s）", level_name)


def get_logger(name: str) -> logging.Logger:
    """业务代码获取 logger 的统一入口。

    用法：
        from app.logger import get_logger
        logger = get_logger(__name__)
        logger.info("用户创建成功 user_id=%s", user_id)
    """
    return logging.getLogger(name)
