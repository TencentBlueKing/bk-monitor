@echo off
setlocal enabledelayedexpansion

set script_path=%~dp0
for /f "tokens=1,* delims= " %%i in ('type %script_path%etc\env.yaml^| findstr ": "') do (
  set add_path_key=%%i
  set add_path_key=!add_path_key::=!
  set add_path_value=%%j
  set !add_path_key!=!add_path_value!
)

if not exist %script_path%pid md %script_path%pid
if not exist %script_path%log md %script_path%log

call %script_path%start.bat
cd %GSE_AGENT_HOME%\plugins\bin\
bkmonitorbeat.exe -c %script_path%etc\bkmonitorbeat_debug.yaml