@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto missing
"%~dp0.venv\Scripts\python.exe" -m device_monitor.dashboard %*
exit /b %errorlevel%
:missing
echo Run .\setup_windows.cmd --install-only first.
exit /b 2
