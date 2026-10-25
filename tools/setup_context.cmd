@echo off
cd /d "%~dp0"
python -m pip install --target "%~dp0..\vendor" "pypdf==6.19.0"
pause
