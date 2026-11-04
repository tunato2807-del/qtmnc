@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-netwatch\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv-netwatch
    ) else (
        py -3 -m venv .venv-netwatch
    )
    if errorlevel 1 exit /b 1
)
".venv-netwatch\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo.
echo Cai dat xong. Xem giao dien mau: start.cmd --demo
echo Cai lab that theo docs\01_GNS3.md, sau do nhap secret: configure.cmd
endlocal
