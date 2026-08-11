@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python_fallback
py -3 main.py %*
exit /b %errorlevel%

:python_fallback
python main.py %*
exit /b %errorlevel%
