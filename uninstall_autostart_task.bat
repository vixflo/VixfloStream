@echo off
setlocal

set TASKNAME=VixfloStreamBackend

echo Deleting Scheduled Task: %TASKNAME%
schtasks /Delete /F /TN "%TASKNAME%"
pause
