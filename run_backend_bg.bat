@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

if not exist "%ROOT%logs" mkdir "%ROOT%logs"

REM Background-friendly backend runner (no pause).
REM Used for Apache/HTTPS proxy or scheduled task.

%ROOT%.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1,::1 >> "%ROOT%logs\backend_bg.log" 2>&1
