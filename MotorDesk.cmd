@echo off
"%~dp0.venv\Scripts\python.exe" -I "%~dp0backend\local_entry.py" serve %*
if errorlevel 1 pause
