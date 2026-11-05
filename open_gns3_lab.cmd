@echo off
setlocal
cd /d "%~dp0"
call create_lab.cmd --open %*
exit /b %errorlevel%
