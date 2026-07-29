@echo off
setlocal

echo .
echo Installing TUIWEATHERGIRL...
echo .

echo Testing for presence of Python...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not added to your PATH.
    echo Please install Python and try again.
    echo .
    echo You can install it from here:
    echo https://www.python.org/downloads/windows/
    echo .
    pause
    exit /b 1
)

echo Installing python components...
pip install windows-curses Babel tzdata requests

echo Installing app...
copy tuiweathergirl.py "%LOCALAPPDATA%\Microsoft\WindowsApps\tuiweathergirl.py"

echo .
echo DONE.
echo .

pause

