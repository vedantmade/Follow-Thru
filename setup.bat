@echo off
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python seed.py --reset
echo.
echo Setup done. Now double-click run.bat
pause
