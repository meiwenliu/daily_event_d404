@echo off
cd /d "%~dp0"

echo ==========================================
echo   D404 Duty Assistant - Public Access
echo ==========================================
echo.
echo Starting Flask and cpolar...
echo.
echo This will open 2 windows:
echo   1. Flask service
echo   2. cpolar tunnel
echo.
echo ==========================================
echo.

REM Start Flask in new window
start "Flask Service" cmd /k "simple-start.bat"

REM Wait a bit
timeout /t 3 /nobreak >nul

REM Start cpolar in new window
start "cpolar Tunnel" cmd /k ""D:\copolar\cpolar-stable-windows-amd64-setup\cpolar.exe" http 8848"

echo.
echo Two windows should be open now.
echo.
echo In the cpolar window, find the Forwarding URL.
echo It will look like: https://xxxx.cpolar.top
echo.
echo Copy that URL and save it in Admin - Deployment.
echo.
echo Press any key to close this window...
pause
