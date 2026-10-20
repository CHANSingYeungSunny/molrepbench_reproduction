@echo off
cd /d "%~dp0"
py -3.12 start_here.py
if errorlevel 1 echo Setup failed. Read the error above and README.md. Python 3.12 64-bit is required.
pause
