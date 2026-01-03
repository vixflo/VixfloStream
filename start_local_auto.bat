@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Starting backend in a new window...
start "VixfloStream Backend (Local)" "%ROOT%run_local.bat"

echo Opening browser...
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000/"

echo Done.
echo.
echo If the browser opens but shows errors, check the backend window output.
pause
