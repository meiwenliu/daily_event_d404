@echo off
chcp 65001 >nul
title 调试 D404 值日助手

set DEBUG_LOG=debug_start.log
cd /d "%~dp0"

:: 清空并初始化日志
echo 开始调试 - %date% %time% > %DEBUG_LOG%
echo ========================================== >> %DEBUG_LOG%

echo ==========================================
echo   D404 值日助手 - 调试模式
echo   日志同时输出到: %DEBUG_LOG%
echo ==========================================
echo.

:: 1. 打印当前目录
echo [1/10] 当前目录:
echo %cd%
echo %cd% >> %DEBUG_LOG%
echo.

:: 2. 打印目录内容
echo [2/10] 目录内容:
dir
dir >> %DEBUG_LOG%
echo.

:: 3. 打印 .bat 文件
echo [3/10] .bat 文件列表:
dir *.bat
dir *.bat >> %DEBUG_LOG%
echo.

:: 4. 打印 Python 版本
echo [4/10] Python 版本:
python --version 2>>&1 >> %DEBUG_LOG%
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    python --version
) else (
    py --version 2>>&1 >> %DEBUG_LOG%
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        py --version
    ) else (
        echo 未找到 Python！
        echo 未找到 Python！ >> %DEBUG_LOG%
        pause
        exit /b 1
    )
)
echo.

:: 5. 打印 pip 版本
echo [5/10] pip 版本:
%PYTHON_CMD% -m pip --version
%PYTHON_CMD% -m pip --version >> %DEBUG_LOG%
echo.

:: 6. 检查 app.py
echo [6/10] 检查 app.py:
if exist "app.py" (
    echo ✓ app.py 存在
    echo ✓ app.py 存在 >> %DEBUG_LOG%
) else (
    echo ✗ app.py 不存在！
    echo ✗ app.py 不存在！ >> %DEBUG_LOG%
    pause
    exit /b 1
)
echo.

:: 7. 检查 requirements.txt
echo [7/10] 检查 requirements.txt:
if exist "requirements.txt" (
    echo ✓ requirements.txt 存在
    echo ✓ requirements.txt 存在 >> %DEBUG_LOG%
    echo 内容:
    type requirements.txt
    type requirements.txt >> %DEBUG_LOG%
) else (
    echo ⚠ requirements.txt 不存在，将创建默认版本
    echo ⚠ requirements.txt 不存在，将创建默认版本 >> %DEBUG_LOG%
    echo Flask>=2.3 > requirements.txt
)
echo.

:: 8. 检查端口 8848
echo [8/10] 检查端口 8848:
netstat -ano | findstr ":8848"
netstat -ano | findstr ":8848" >> %DEBUG_LOG% 2>&1
echo.

:: 9. 激活虚拟环境
echo [9/10] 激活虚拟环境:
if not exist ".venv" (
    echo 创建虚拟环境...
    %PYTHON_CMD% -m venv .venv
    echo 创建虚拟环境... >> %DEBUG_LOG%
)
call .venv\Scripts\activate.bat
echo ✓ 虚拟环境已激活
echo ✓ 虚拟环境已激活 >> %DEBUG_LOG%
echo.

:: 10. 运行 app.py
echo [10/10] 启动 Flask 应用...
echo ==========================================
echo 本机访问：    http://127.0.0.1:8848
echo 管理后台：    http://127.0.0.1:8848/admin
echo 默认密码：    d404admin
echo ==========================================
echo.
echo 启动日志同时写入 %DEBUG_LOG%
echo.

:: 同时输出到屏幕和日志
%PYTHON_CMD% -u app.py 2>&1 | tee -a %DEBUG_LOG%

echo.
echo 应用已退出，按任意键关闭...
pause
