@echo off
cd /d "%~dp0"

echo ==========================================
echo   D404 Duty Assistant
echo ==========================================
echo.
echo Starting...
echo.
echo Local: http://127.0.0.1:8848
echo Admin: http://127.0.0.1:8848/admin
echo Password: d404admin
echo.
echo Close this window to stop service
echo ==========================================
echo.

call .venv\Scripts\activate.bat
python app.py

echo.
echo Server stopped.
pause
