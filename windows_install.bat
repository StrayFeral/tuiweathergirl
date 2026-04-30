@echo off
echo .
echo "Installing TUIWEATHERGIRL..."
echo .

pip install windows-curses Babel tzdata requests

echo @python "%%LOCALAPPDATA%%\Microsoft\WindowsApps\tuiweathergirl.py" %%* > "%LOCALAPPDATA%\Microsoft\WindowsApps\tuiweathergirl.bat"
copy tuiweathergirl.py "%LOCALAPPDATA%\Microsoft\WindowsApps\tuiweathergirl.py"

echo .
echo "DONE."

