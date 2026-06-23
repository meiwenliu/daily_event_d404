@echo off
chcp 65001 >nul
title D404 网络与端口检查
cd /d "%~dp0"

echo ============================================
echo    D404 值日看板 - 网络检查
echo ============================================
echo.

echo ===== 本机 IPv4 地址（ipconfig）=====
ipconfig | findstr /C:"IPv4"
echo.

echo ===== Flask 本地地址 =====
echo   http://127.0.0.1:8848
echo.

echo ===== 局域网地址（自动探测）=====
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print('  http://'+s.getsockname()[0]+':8848');s.close()"
) else (
  echo   （需先 install.bat 安装 Python 环境后才能自动探测）
)
echo.

echo ===== 端口 8848 占用情况 =====
netstat -ano | findstr ":8848"
if errorlevel 1 (
  echo   端口 8848 当前未被占用（服务未运行）。
) else (
  echo   上面若列出 LISTENING，说明服务已在运行。
)
echo.

echo 提示：手机访问请确认手机与电脑连同一个 WiFi，且用 http://（非 https）。
pause
