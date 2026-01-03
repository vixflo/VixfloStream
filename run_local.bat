@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Starting LOCAL server on http://127.0.0.1:8000
echo (Close this window to stop)

if not exist "%ROOT%logs" mkdir "%ROOT%logs"
echo Logging to %ROOT%logs\backend_local.log

%ROOT%.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "%ROOT%logs\backend_local.log" 2>&1

echo.
echo Backend stopped. See logs\backend_local.log
pause
