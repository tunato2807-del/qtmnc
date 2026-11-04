@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-netwatch\Scripts\python.exe" (
    echo Hay chay setup.cmd truoc.
    exit /b 1
)
".venv-netwatch\Scripts\python.exe" -m netwatch %*
exit /b %errorlevel%
