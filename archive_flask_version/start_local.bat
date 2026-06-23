@echo off
chcp 65001 >nul
title D404 值日看板（本地/局域网）
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境 .venv，请先运行 install.bat。
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
echo.
echo ============================================
echo    D404 值日看板 - 本地/局域网模式
echo    本机：   http://127.0.0.1:8848
echo    局域网： http://本机IP:8848 （手机同 WiFi）
echo    管理后台：http://127.0.0.1:8848/admin
echo    关闭本窗口即停止。
echo ============================================
echo.

python app.py

echo.
echo 服务已停止。
pause
