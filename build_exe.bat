@echo off
setlocal

set ROOT=%~dp0
cd /d %ROOT%

echo Building Windows EXE (PyInstaller)...

%ROOT%.venv\Scripts\python.exe -m pip install --upgrade pip
%ROOT%.venv\Scripts\python.exe -m pip install -r requirements.txt
%ROOT%.venv\Scripts\python.exe -m pip install pyinstaller

REM One-file EXE that starts the local server and opens the UI automatically.
REM Include templates/static/ffmpeg so the UI + MP3 conversion works when frozen.
%ROOT%.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --noconsole --name VixfloStreamDownloader ^
	--icon "assets\\app-icon.ico" ^
	--add-data "templates;templates" ^
	--add-data "static;static" ^
	--add-data "assets;assets" ^
	--add-data "ffmpeg;ffmpeg" ^
	desktop_launcher.py

echo.
echo Done. EXE is in: dist\VixfloStreamDownloader.exe
pause
