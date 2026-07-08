"""启动时配置校验：fail-fast，敏感变量缺失立即退出。

应用启动时调用 validate_config()，确保所有必需环境变量已设置。
避免运行时才发现配置缺失（如首次签发 JWT 时）。

注意：本模块在 logger 初始化后调用，但为避免日志系统未就绪时丢失输出，
启动期错误信息直接写 sys.stderr（用 print），不走 logger。
"""
from __future__ import annotations

import os
import sys

# 必需环境变量列表（缺失就退出）
REQUIRED_ENV_VARS = [
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "SECRET_KEY",  # JWT 签发必须
]

# 敏感变量（缺失或为弱默认值时报警）
SENSITIVE_DEFAULTS = {
    "SECRET_KEY": [
        "please_change_me_to_a_long_random_string",
        "please_change_me",
        "changeme",
        "secret",
    ],
    "DB_PASSWORD": ["123456", "password", "root", ""],
}


def validate_config() -> None:
    """启动时校验配置，缺失敏感变量立即退出。

    - 必需变量缺失：sys.exit(1)
    - 敏感变量是弱默认值：警告但不退出（开发环境友好）
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. 必需变量必须存在
    for var in REQUIRED_ENV_VARS:
        value = os.getenv(var)
        if not value:
            errors.append(f"  ❌ 缺少环境变量: {var}")

    # 2. 敏感变量不能是弱默认值
    for var, weak_values in SENSITIVE_DEFAULTS.items():
        value = os.getenv(var, "")
        if value in weak_values:
            warnings.append(f"  ⚠️  {var} 使用了弱默认值，生产环境必须修改")

    # 3. DB_PORT 必须是数字
    db_port = os.getenv("DB_PORT", "3306")
    try:
        int(db_port)
    except ValueError:
        errors.append(f"  ❌ DB_PORT 不是合法数字: {db_port}")

    # 4. LOG_LEVEL 必须是合法级别
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        errors.append(f"  ❌ LOG_LEVEL 不是合法级别: {log_level}")

    # 5. APP_ENV 必须是合法值
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env not in {"development", "staging", "production", "prod"}:
        errors.append(f"  ❌ APP_ENV 不是合法值: {app_env}")

    # 打印警告（启动期输出，不走 logger）
    if warnings:
        print("⚠️  配置警告：", file=sys.stderr)  # noqa: T201
        for w in warnings:
            print(w, file=sys.stderr)  # noqa: T201

    # 有错误直接退出
    if errors:
        print("❌ 配置校验失败，请检查环境变量：", file=sys.stderr)  # noqa: T201
        for e in errors:
            print(e, file=sys.stderr)  # noqa: T201
        print("\n请参考 .env.example 配置 .env 文件", file=sys.stderr)  # noqa: T201
        sys.exit(1)
