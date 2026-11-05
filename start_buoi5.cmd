@echo off
setlocal
cd /d "%~dp0"
call start.cmd --inventory inventory.buoi5.json %*
exit /b %errorlevel%
