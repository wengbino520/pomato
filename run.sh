#!/usr/bin/env bash
# POMATO 启动脚本 —— Linux / macOS
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[错误] 未找到虚拟环境，请先运行："
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    exit 1
fi

cd "$SCRIPT_DIR"
exec "$VENV_PYTHON" main.py "$@"
