@echo off
rem Subtitle Generator - Windows setup
cd /d "%~dp0"
set PY=
for %%v in (3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%v -c "" >nul 2>&1 && set PY=py -%%v
  )
)
if not defined PY python -c "import sys; sys.exit(not (3,10)<=sys.version_info[:2]<=(3,13))" >nul 2>&1 && set PY=python
if not defined PY (
  echo Python 3.10-3.13 not found. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
echo Using: %PY%
%PY% -m venv --clear .venv || goto :fail
.venv\Scripts\python -m pip install --upgrade pip || goto :fail
.venv\Scripts\python -m pip install -r requirements.txt || goto :fail
echo.
echo Done. GUI: generator.bat    Command line: generator-cli.bat --help
pause
exit /b 0

:fail
echo Setup failed.
pause
exit /b 1
