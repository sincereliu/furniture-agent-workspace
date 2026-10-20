@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" "domain\stages\layout-plan\scripts\open_last_project.py"
if errorlevel 1 pause
