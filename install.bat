@echo off
chcp 65001 >nul
title 安装 D404 值日助手依赖

echo ==========================================
echo   D404 值日助手 - 安装依赖
echo ==========================================
echo.

cd /d "%~dp0"

:: 检查 Python
echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    echo   ✓ 找到 Python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        echo   ✓ 找到 Python (py launcher)
    ) else (
        echo   ✗ 未找到 Python！请先安装 Python 3.8+
        pause
        exit /b 1
    )
)
%PYTHON_CMD% --version
echo.

:: 创建虚拟环境（如果不存在）
echo [2/4] 检查虚拟环境...
if not exist ".venv" (
    echo   - 创建虚拟环境 .venv...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo   ✗ 虚拟环境创建失败！
        pause
        exit /b 1
    )
    echo   ✓ 虚拟环境创建成功
) else (
    echo   ✓ 虚拟环境已存在
)
echo.

:: 激活虚拟环境
echo [3/4] 激活虚拟环境...
call .venv\Scripts\activate.bat
echo   ✓ 虚拟环境已激活
echo.

:: 检查 requirements.txt
echo [4/4] 安装依赖...
if not exist "requirements.txt" (
    echo   - 创建最小 requirements.txt...
    echo Flask>=2.3 > requirements.txt
)
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo   ✗ 依赖安装失败！
    pause
    exit /b 1
)
echo   ✓ 依赖安装成功
echo.

echo ==========================================
echo   ✓ 安装完成！
echo   现在可以运行 start.bat 或 start_local.bat 启动服务
echo ==========================================
echo.
pause
