@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Starting backend in a new window (for Apache/HTTPS)...
start "VixfloStream Backend (Apache Proxy)" "%ROOT%run_apache_backend.bat"

echo Opening browser...
timeout /t 2 /nobreak >nul
start "" "https://vixflodev.ro/VixfloStream/"

echo Done.
echo.
echo If you get 503, the backend did not start or port 8000 is blocked.
pause
