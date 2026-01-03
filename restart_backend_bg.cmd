@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

set PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe

"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%restart_backend_bg.ps1"
