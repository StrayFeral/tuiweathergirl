@echo off
set "CURRENT_DIR=%~dp0"
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

set "VBS_SCRIPT=%TEMP%\make_shortcut.vbs"

rem Create temporary VBScript using double-quotes escaped via VBS chr(34)
echo Set ws = CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo Set s = ws.CreateShortcut("%CURRENT_DIR%\TUI Weather Girl.lnk") >> "%VBS_SCRIPT%"
echo s.TargetPath = "wt.exe" >> "%VBS_SCRIPT%"
echo s.Arguments = "-M python " ^& chr(34) ^& "%CURRENT_DIR%\tuiweathergirl.py" ^& chr(34) >> "%VBS_SCRIPT%"
echo s.WorkingDirectory = "%CURRENT_DIR%" >> "%VBS_SCRIPT%"
echo s.WindowStyle = 3 >> "%VBS_SCRIPT%"
echo s.Save >> "%VBS_SCRIPT%"

rem Execute the VBScript
cscript //nologo "%VBS_SCRIPT%"

rem Delete temporary VBScript
del "%VBS_SCRIPT%"

echo Shortcut created!
pause
