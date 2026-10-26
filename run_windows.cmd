@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto missing_venv
"%~dp0.venv\Scripts\python.exe" "%~dp0monitor_ssh.py" --env-file "%~dp0.env" %*
exit /b %errorlevel%
:missing_venv
echo Run .\setup_windows.cmd first.
exit /b 2
