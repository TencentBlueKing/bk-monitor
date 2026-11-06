@echo off
set script_path=%~dp0
call %script_path%stop.bat
call %script_path%start.bat
if %ERRORLEVEL% NEQ 0 EXIT 1