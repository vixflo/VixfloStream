@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Starting backend for Apache reverse-proxy (https://vixflodev.ro/VixfloStream/)
echo Backend listens on http://127.0.0.1:8000
echo (Close this window to stop)

if not exist "%ROOT%logs" mkdir "%ROOT%logs"
echo Logging to %ROOT%logs\backend_apache.log

%ROOT%.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1,::1 >> "%ROOT%logs\backend_apache.log" 2>&1

echo.
echo Backend stopped. See logs\backend_apache.log
pause
