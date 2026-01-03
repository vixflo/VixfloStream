@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Starting server on http://127.0.0.1:8000
echo (Close this window to stop)

%ROOT%.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1,::1
