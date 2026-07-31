@echo off
set "CURRENT_DIR=%~dp0"
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

set "VBS_SCRIPT=%TEMP%\make_shortcut.vbs"

:: Create a temporary VBScript file line-by-line using cmd
echo Set ws = CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo Set s = ws.CreateShortcut("%CURRENT_DIR%\TUI Weather Girl.lnk") >> "%VBS_SCRIPT%"
echo s.TargetPath = "python.exe" >> "%VBS_SCRIPT%"
echo s.Arguments = """%CURRENT_DIR%\tuiweathergirl.py""" >> "%VBS_SCRIPT%"
echo s.WorkingDirectory = "%CURRENT_DIR%" >> "%VBS_SCRIPT%"
echo s.Save >> "%VBS_SCRIPT%"

:: Execute the VBScript with standard built-in Windows Script Host
cscript //nologo "%VBS_SCRIPT%"

:: Delete temporary VBScript
del "%VBS_SCRIPT%"

echo Shortcut created!
pause
