@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto missing_venv
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\windows_tap_bridge.py" %*
exit /b %errorlevel%
:missing_venv
echo Run .\setup_windows.cmd --with-tap --install-only first.
exit /b 2
