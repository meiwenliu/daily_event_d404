@echo off
chcp 65001 >nul
title 检查 D404 值日助手网络

set LOG_FILE=network_check.log
cd /d "%~dp0"

echo 网络检查 - %date% %time% > %LOG_FILE%
echo ========================================== >> %LOG_FILE%

echo ==========================================
echo   D404 值日助手 - 网络检查
echo   日志同时输出到: %LOG_FILE%
echo ==========================================
echo.

:: 获取本机 IPv4
echo [1/3] 获取本机 IPv4 地址...
for /f "tokens=14" %%i in ('ipconfig ^| findstr /i "IPv4"') do (
    set LOCAL_IP=%%i
)
echo       ✓ 本机 IP: %LOCAL_IP%
echo 本机 IP: %LOCAL_IP% >> %LOG_FILE%
echo.

:: 显示访问地址
echo [2/3] 访问地址信息：
echo       本地访问：   http://127.0.0.1:8848
echo       局域网访问： http://%LOCAL_IP%:8848
echo.
echo 本地访问：http://127.0.0.1:8848 >> %LOG_FILE%
echo 局域网访问：http://%LOCAL_IP%:8848 >> %LOG_FILE%
echo.

:: 检查端口占用
echo [3/3] 检查端口 8848...
netstat -ano | findstr ":8848" >nul
if %errorlevel% equ 0 (
    echo       ⚠ 端口 8848 已被占用！
    echo.
    echo       占用信息：
    netstat -ano | findstr ":8848"
    echo.
    echo 端口 8848 已被占用 >> %LOG_FILE%
    netstat -ano | findstr ":8848" >> %LOG_FILE%
    echo.
    echo       提示：请关闭占用端口的程序，或修改 app.py 中的端口号
) else (
    echo       ✓ 端口 8848 空闲
    echo 端口 8848 空闲 >> %LOG_FILE%
)
echo.

echo ==========================================
echo   提示：如果手机无法访问，请检查：
echo   1. Windows 防火墙是否允许 Python 访问网络
echo   2. 手机和电脑是否在同一局域网
echo   3. 电脑是否开启了热点
echo ==========================================
echo.
echo ========================================== >> %LOG_FILE%
echo 网络检查完成 >> %LOG_FILE%
pause
