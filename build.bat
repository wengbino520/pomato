@echo off
REM ============================================================
REM  POMATO PyInstaller 打包脚本
REM  生成单个 exe 文件于 dist/ 目录
REM ============================================================

SET "PROJ_DIR=%~dp0"
SET "VENV_PYTHON=%PROJ_DIR%.venv\Scripts\python.exe"

REM 检查 venv 是否存在
IF NOT EXIST "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境 .venv
    echo 请先运行：
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   .venv\Scripts\pip install pyinstaller
    pause
    exit /b 1
)

echo [1/3] 安装 PyInstaller...
"%VENV_PYTHON%" -m pip install pyinstaller -q

echo [2/3] 清理旧的构建文件...
if exist "%PROJ_DIR%build" rmdir /s /q "%PROJ_DIR%build"
if exist "%PROJ_DIR%dist" rmdir /s /q "%PROJ_DIR%dist"

echo [3/3] 开始打包...
cd /d "%PROJ_DIR%"
"%VENV_PYTHON%" -m PyInstaller POMATO.spec --clean --noconfirm

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo  打包完成！输出位置：%PROJ_DIR%dist\POMATO.exe
    echo ============================================================
) else (
    echo.
    echo [错误] 打包失败，请检查 PyInstaller 日志。
)

pause
