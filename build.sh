#!/usr/bin/env bash
# ============================================================
#  POMATO PyInstaller 打包脚本 — Linux
#  生成单个可执行文件于 dist/ 目录
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# 检查 venv 是否存在
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[错误] 未找到虚拟环境 .venv"
    echo "请先运行："
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    echo "  .venv/bin/pip install pyinstaller"
    exit 1
fi

echo "[1/3] 安装 PyInstaller..."
"$VENV_PYTHON" -m pip install pyinstaller -q

echo "[2/3] 清理旧的构建文件..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"

echo "[3/3] 开始打包..."
cd "$SCRIPT_DIR"
"$VENV_PYTHON" -m PyInstaller POMATO.spec --clean --noconfirm

if [ $? -eq 0 ]; then
    echo
    echo "============================================================"
    echo "  打包完成！输出位置：$SCRIPT_DIR/dist/POMATO"
    echo "============================================================"
else
    echo
    echo "[错误] 打包失败，请检查 PyInstaller 日志。"
    exit 1
fi
