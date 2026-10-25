@echo off
cd /d "%~dp0"
set GEMINI_API_KEY=
set GOOGLE_API_KEY=
if exist "%LOCALAPPDATA%\agy\bin\agy.exe" (
  "%LOCALAPPDATA%\agy\bin\agy.exe"
) else (
  agy
)
pause
