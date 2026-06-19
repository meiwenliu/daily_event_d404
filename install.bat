@echo off
chcp 65001 >nul
title D404 值日看板 - 安装
cd /d "%~dp0"

echo ============================================
echo    D404 实验室值日看板 - 安装依赖
echo    （仅 Flask，无需微信/wxauto）
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 python，请先安装 Python 3.10+ 并加入 PATH。
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/3] 正在创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 已存在虚拟环境 .venv，跳过创建。
)

echo [2/3] 激活虚拟环境并升级 pip ...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip

echo [3/3] 安装依赖 Flask ...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络。
    pause
    exit /b 1
)

echo.
echo ============================================
echo    安装完成！请双击运行 start.bat 启动
echo ============================================
pause
