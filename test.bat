@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python try_pipeline.py
pause
