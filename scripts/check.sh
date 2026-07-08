#!/usr/bin/env bash
# Claude Code PostEdit/PreCommit hook：编辑 Python 文件后自动校验
#
# 校验内容：
# 1. AST 语法检查
# 2. Repository 层不能调 db.commit()
# 3. 不能用 @on_event（已弃用）
# 4. 不能用 passlib
# 5. Service 层必须有 bcrypt
# 6. 业务代码不能直接 print()
# 7. 修改了 app/ 或 tests/ 时跑测试
#
# 退出码：0 通过，非 0 失败

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -f "env/bin/activate" ]; then
    source env/bin/activate
fi

# 读取 stdin（Claude 传入的 JSON，包含修改的文件信息）
INPUT=$(cat)
echo "🔍 Claude PostEdit 校验启动..." >&2

# ── 1. AST 校验（精确，无误报） ────────────────────────
if ! python scripts/check.py; then
    exit 1
fi

# ── 2. 决定是否跑测试 ─────────────────────────────────
# 从 JSON 提取修改的文件路径
NEED_TEST=false
if command -v jq &> /dev/null && [ -n "$INPUT" ]; then
    FILES=$(echo "$INPUT" | jq -r '.files[]?.path // empty' 2>/dev/null || echo "")
    for f in $FILES; do
        if [[ "$f" == app/* ]] || [[ "$f" == tests/* ]]; then
            NEED_TEST=true
            break
        fi
    done
fi

# 如果没有 jq，保守地假设需要测试
if ! command -v jq &> /dev/null; then
    NEED_TEST=true
fi

if [ "$NEED_TEST" = true ] && [ -f "tests/test_api.py" ]; then
    echo "🧪 跑测试..." >&2
    # 清空旧数据避免冲突
    if command -v mysql &> /dev/null; then
        mysql -u root -p123456 -e "USE testdb; TRUNCATE TABLE users;" 2>/dev/null || true
    fi
    if ! python tests/test_api.py > /tmp/claude-test.log 2>&1; then
        echo "❌ 测试失败：" >&2
        tail -20 /tmp/claude-test.log >&2
        exit 1
    fi
fi

echo "✅ 全部校验通过" >&2
exit 0
