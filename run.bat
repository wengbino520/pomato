@echo off
REM POMATO 启动脚本 —— 隔离 Anaconda DLL 冲突
REM 激活 venv，并从 PATH 中移除 Anaconda 的 Qt/Library 目录

SET "PROJ_DIR=%~dp0"
SET "VENV_PYTHON=%PROJ_DIR%.venv\Scripts\python.exe"

REM 检查 venv 是否存在
IF NOT EXIST "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境，请先运行：
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM 用 venv Python 启动，并告诉 Qt 从包内加载 DLL（Qt 6.8+ 特性）
SET "QT_QPA_PLATFORM_PLUGIN_PATH=%PROJ_DIR%.venv\Lib\site-packages\PyQt6\Qt6\plugins\platforms"

cd /d "%PROJ_DIR%"
"%VENV_PYTHON%" main.py %*
