@echo off
cd /d "%~dp0\.."
python -m uvicorn ems_api.main:app --port 8765 --host 0.0.0.0
