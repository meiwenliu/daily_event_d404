@echo off
cd /d "%~dp0"

echo ==========================================
echo   D404 Duty Assistant - Local
echo ==========================================
echo.

echo [1/5] Checking app.py...
if not exist "app.py" (
    echo [ERROR] app.py not found!
    pause
    exit /b 1
)
echo [OK] app.py found
echo.

echo [2/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    echo [OK] Python found
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        echo [OK] Python found (py launcher)
    ) else (
        echo [ERROR] Python not found!
        pause
        exit /b 1
    )
)
echo.

echo [3/5] Checking virtual environment...
if not exist ".venv" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)
echo.

echo [4/5] Activating virtual environment...
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

echo [5/5] Installing dependencies...
if not exist "requirements.txt" (
    echo Flask>=2.3 > requirements.txt
)
pip install -r requirements.txt -q
echo [OK] Dependencies ready
echo.

echo ==========================================
echo   Starting server...
echo.
echo   Local: http://127.0.0.1:8848
echo   Admin: http://127.0.0.1:8848/admin
echo   Password: d404admin
echo.
echo   Close this window to stop service
echo ==========================================
echo.

%PYTHON_CMD% app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server failed to start!
    echo.
)
pause
