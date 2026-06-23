@echo off
chcp 65001 >nul
title 启动 D404 值日助手 - 公网访问 (cpolar)

echo ==========================================
echo   D404 值日助手 - 公网访问模式
echo ==========================================
echo.

cd /d "%~dp0"

:: 设置 cpolar 路径
set CPOLAR_PATH="D:\copolar\cpolar-stable-windows-amd64-setup\cpolar.exe"

:: 检查 cpolar
%CPOLAR_PATH% version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 cpolar！
    echo.
    echo 请先安装 cpolar:
    echo   1. 访问 https://www.cpolar.com/ 下载并安装
    echo   2. 注册账号并获取 authtoken
    echo   3. 运行: %CPOLAR_PATH% authtoken 你的token
    echo.
    pause
    exit /b 1
)

echo [提示] 确保已运行过: cpolar authtoken 你的token
echo.

:: 检查 app.py
if not exist "app.py" (
    echo [错误] 未找到 app.py！
    pause
    exit /b 1
)

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [错误] 未找到 Python！
        pause
        exit /b 1
    )
)

:: 激活虚拟环境
if not exist ".venv" (
    %PYTHON_CMD% -m venv .venv
)
call .venv\Scripts\activate.bat

:: 安装依赖（如果需要）
if not exist "requirements.txt" (
    echo Flask>=2.3 > requirements.txt
)
pip install -r requirements.txt -q

:: 打印信息
echo ==========================================
echo   正在启动服务...
echo.
echo   本机访问：    http://127.0.0.1:8848
echo   管理后台：    http://127.0.0.1:8848/admin
echo   默认密码：    d404admin
echo.
echo   提示：
echo   1. 两个新窗口将打开：Flask 服务和 cpolar 隧道
echo   2. 在 cpolar 窗口中找到 "Forwarding" 行
echo   3. 复制 https://... 链接即可公网访问
echo ==========================================
echo.

:: 启动 Flask 服务（新窗口）
start "D404 Flask 服务" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && %PYTHON_CMD% app.py"

:: 等待一下，确保 Flask 启动
timeout /t 3 /nobreak >nul

:: 启动 cpolar（新窗口）
start "D404 cpolar 隧道" cmd /k "%CPOLAR_PATH% http 8848"

echo ✓ 服务已启动！
echo   请查看新打开的窗口
echo.
pause
