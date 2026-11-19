@echo off
setlocal
cd /d "%~dp0"
if exist "manual\.env.evaluation" set /p "ANTHROPIC_API_KEY=" < "manual\.env.evaluation"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -X utf8 app.py %*
) else (
  python -X utf8 app.py %*
)
if errorlevel 1 pause

