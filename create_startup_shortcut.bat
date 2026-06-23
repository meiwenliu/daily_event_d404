@echo off
chcp 65001 >nul
title 创建 D404 值日助手开机自启快捷方式

echo ==========================================
echo   D404 值日助手 - 开机自启设置
echo ==========================================
echo.

cd /d "%~dp0"

:: 获取启动文件夹路径
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=D404值日助手"
set "TARGET_FILE=%~dp0start_public_cpolar.bat"

echo 启动文件夹: %STARTUP_FOLDER%
echo.

:: 检查目标文件是否存在
if not exist "%TARGET_FILE%" (
    echo [错误] 未找到 %TARGET_FILE%
    pause
    exit /b 1
)

:: 使用 PowerShell 创建快捷方式
echo 正在创建快捷方式...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_FOLDER%\%SHORTCUT_NAME%.lnk'); $s.TargetPath = '%TARGET_FILE%'; $s.WorkingDirectory = '%~dp0'; $s.Save()"

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo   ✓ 快捷方式创建成功！
    echo.
    echo   快捷方式位置: %STARTUP_FOLDER%\%SHORTCUT_NAME%.lnk
    echo.
    echo   ⚠  重要提示：
    echo   1. 请确保电脑设置为"从不"休眠或睡眠
    echo   2. 否则公网链接会在电脑休眠后失效
    echo   3. 如要取消开机自启，删除启动文件夹中的快捷方式即可
    echo ==========================================
) else (
    echo.
    echo [错误] 快捷方式创建失败！
    echo.
    echo 请手动操作：
    echo 1. 按 Win+R，输入 shell:startup 打开启动文件夹
    echo 2. 右键点击 start_public_cpolar.bat，选择"创建快捷方式"
    echo 3. 将快捷方式移动到打开的启动文件夹中
    echo.
    echo 取消开机自启：
    echo 1. 按 Win+R，输入 shell:startup
    echo 2. 删除 D404值日助手.lnk
)

echo.
pause
