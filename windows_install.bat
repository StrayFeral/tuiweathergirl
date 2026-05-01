@echo off
setlocal

echo .
echo "Installing TUIWEATHERGIRL..."
echo .

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not added to your PATH.
    echo Please install Python and try again.
    exit /b 1
)

pip install windows-curses Babel tzdata requests

echo @python "%%LOCALAPPDATA%%\Microsoft\WindowsApps\tuiweathergirl.py" %%* > "%LOCALAPPDATA%\Microsoft\WindowsApps\tuiweathergirl.bat"
copy tuiweathergirl.py "%LOCALAPPDATA%\Microsoft\WindowsApps\tuiweathergirl.py"

echo .
echo "DONE."

