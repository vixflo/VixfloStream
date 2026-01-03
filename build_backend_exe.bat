@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Building Windows backend EXE (PyInstaller)...

%ROOT%.venv\Scripts\python.exe -m pip install --upgrade pip
%ROOT%.venv\Scripts\python.exe -m pip install -r requirements.txt
%ROOT%.venv\Scripts\python.exe -m pip install pyinstaller

REM Server-only EXE used by Electron (no browser auto-open).
REM Include templates/static/ffmpeg so UI + MP3 conversion works.
%ROOT%.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --noconsole --name VixfloStreamBackend ^
  --icon "assets\\app-icon.ico" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "assets;assets" ^
  --add-data "ffmpeg;ffmpeg" ^
  server_launcher.py

echo.
echo Done. EXE is in: dist\VixfloStreamBackend.exe
pause
