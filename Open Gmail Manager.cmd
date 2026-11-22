@echo off
where pythonw.exe >nul 2>nul
if not errorlevel 1 (
  start "" pythonw.exe "%~dp0account_manager.py"
  exit /b
)
echo Python 3.10 or later with Tkinter is required.
pause
