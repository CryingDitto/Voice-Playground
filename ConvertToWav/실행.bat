@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check_dependency
python -m venv .venv
if errorlevel 1 goto failed
:check_dependency
".venv\Scripts\python.exe" -c "import imageio_ffmpeg; imageio_ffmpeg.get_ffmpeg_exe()" >nul 2>&1
if not errorlevel 1 goto launch
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" gui.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Unable to start. Check Python installation and internet connection.
pause
exit /b 1
