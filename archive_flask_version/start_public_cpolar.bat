@echo off
chcp 65001 >nul
title D404 值日看板 - 公网（cpolar）
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境 .venv，请先运行 install.bat。
    pause
    exit /b 1
)

echo ============================================
echo    D404 值日看板 - 公网访问模式（cpolar）
echo ============================================
echo.

REM 1) 在新窗口启动 Flask（监听 0.0.0.0:8848）
echo [1/2] 启动 Flask 服务（新窗口）...
start "D404 Flask" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && python app.py"

REM 2) 检测 cpolar
where cpolar >nul 2>nul
if errorlevel 1 (
    echo.
    echo [!] 未检测到 cpolar 命令。
    echo.
    echo     请先安装 cpolar： https://www.cpolar.com/download
    echo     安装后只需执行一次（把控制台里的 authtoken 粘进来）：
    echo         cpolar authtoken 你的token
    echo     token 在 cpolar 控制台 https://dashboard.cpolar.com/get-started/ 获取。
    echo     然后重新运行本脚本。
    echo.
    echo     当前仅本地/局域网可用： http://127.0.0.1:8848
    echo.
    pause
    exit /b 0
)

echo [2/2] 检测到 cpolar，3 秒后启动隧道...
echo.
echo >>> 隧道启动后，在输出里找到形如下面这一行：
echo     Forwarding   https://xxxx.r6.cpolar.top -> http://localhost:8848
echo >>> 把那个 https:// 公网地址复制下来，粘进后台「部署」标签保存。
echo.
timeout /t 3 >nul

REM 直接启动隧道；cpolar 使用其本地已保存的 authtoken，本脚本不读写任何 token。
cpolar http 8848

pause
