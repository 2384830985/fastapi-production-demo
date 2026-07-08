# Makefile：统一常用命令，省去记长命令的麻烦
# 用法：make <target>，例如 make dev / make test / make migrate

# Python 解释器（优先用 venv 里的）
PYTHON ?= python
PIP ?= pip
VENV ?= env

# 默认目标（make 不带参数时显示帮助）
.DEFAULT_GOAL := help

# ── 环境 ────────────────────────────────────────────────
.PHONY: venv activate install lock

venv:  ## 创建虚拟环境
	$(PYTHON) -m venv $(VENV)

activate:  ## 激活虚拟环境（提示，无法在 make 里持久激活）
	@echo "请在 shell 里执行: source $(VENV)/bin/activate"

install:  ## 安装依赖
	@command -v $(VENV)/bin/python >/dev/null || $(MAKE) venv
	$(VENV)/bin/$(PIP) install --upgrade pip
	$(VENV)/bin/$(PIP) install -r requirements.txt
	$(VENV)/bin/$(PIP) install -r requirements-dev.txt

lock:  ## 生成依赖锁文件（pip-compile）
	$(VENV)/bin/pip-compile --output-file=requirements.lock requirements.txt
	$(VENV)/bin/pip-compile --output-file=requirements-dev.lock requirements-dev.txt

# ── 开发 ────────────────────────────────────────────────
.PHONY: dev run prod

dev:  ## 启动开发服务（热重载）
	$(VENV)/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

run:  ## 启动生产服务（gunicorn 多 worker）
	$(VENV)/bin/gunicorn main:app \
		-w 4 \
		-k uvicorn.workers.UvicornWorker \
		-b 0.0.0.0:8000 \
		--access-logfile - \
		--error-logfile -

prod: APP_ENV=production
prod:  ## 生产模式启动（设置 APP_ENV=production）
	APP_ENV=production $(MAKE) run

# ── 测试与检查 ──────────────────────────────────────────
.PHONY: test test-cov lint typecheck check

test:  ## 跑单元测试（pytest）
	$(VENV)/bin/pytest tests/ -v

test-cov:  ## 跑测试 + 覆盖率报告
	$(VENV)/bin/pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

lint:  ## 代码风格检查（flake8）
	$(VENV)/bin/flake8 app/ tests/ main.py \
		--max-line-length=120 \
		--extend-ignore=E501,W503 \
		--exclude=env,alembic

typecheck:  ## 类型检查（mypy）
	$(VENV)/bin/mypy app/ main.py --config-file mypy.ini

check: lint typecheck test  ## 一键检查：lint + typecheck + test

# ── 数据库 ──────────────────────────────────────────────
.PHONY: migrate migrate-new downgrade db-shell

migrate:  ## 执行数据库迁移到最新
	$(VENV)/bin/alembic upgrade head

migrate-new:  ## 生成新迁移脚本，用法：make migrate-new MSG="add email"
	@test -n "$(MSG)" || (echo "用法: make migrate-new MSG=\"描述\"" && exit 1)
	$(VENV)/bin/alembic revision --autogenerate -m "$(MSG)"

downgrade:  ## 回滚一个迁移版本
	$(VENV)/bin/alembic downgrade -1

db-shell:  ## 进入 MySQL shell（需要 mysql 客户端）
	mysql -u root -p$$DB_PASSWORD testdb

# ── Docker ──────────────────────────────────────────────
.PHONY: docker-up docker-down docker-logs docker-build

docker-up:  ## Docker Compose 启动（app + mysql）
	docker compose up -d --build

docker-down:  ## 停止 Docker 容器
	docker compose down

docker-logs:  ## 看 Docker 日志
	docker compose logs -f app

docker-build:  ## 只构建镜像（不启动）
	docker compose build app

# ── 清理 ────────────────────────────────────────────────
.PHONY: clean clean-pyc clean-test

clean: clean-pyc clean-test  ## 清理所有缓存

clean-pyc:  ## 清理 Python 缓存
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-test:  ## 清理测试产物
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache

# ── 帮助 ────────────────────────────────────────────────
.PHONY: help

help:  ## 显示这个帮助
	@echo "FastAPI 用户管理项目 - 常用命令"
	@echo ""
	@echo "用法: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
