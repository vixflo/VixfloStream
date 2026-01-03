@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

set TASKNAME=VixfloStreamBackend
set TARGET=%ROOT%run_backend_bg.bat

echo Creating Scheduled Task: %TASKNAME%
echo Target: %TARGET%

schtasks /Create /F /SC ONLOGON /RL LIMITED /TN "%TASKNAME%" /TR "\"%TARGET%\"" >nul
if errorlevel 1 (
  echo Failed to create task.
  echo Try running this .bat as Administrator.
  pause
  exit /b 1
)

echo Task created.
echo You can start it now with: schtasks /Run /TN "%TASKNAME%"
pause
