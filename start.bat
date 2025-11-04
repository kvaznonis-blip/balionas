@echo off
cd /d "%~dp0"
echo 
start "" http://127.0.0.1:8000/static/index.html
start "" cmd /c "python -m uvicorn main:app --reload"
