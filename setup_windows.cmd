@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 "%~dp0setup_project.py" %*
exit /b %errorlevel%
:use_python
where python >nul 2>&1
if errorlevel 1 goto missing_python
python "%~dp0setup_project.py" %*
exit /b %errorlevel%
:missing_python
echo Install Python 3.10+ from https://www.python.org/downloads/windows/ and reopen VS Code.
exit /b 2
