@echo off
setlocal enabledelayedexpansion

set script_path=%~dp0
for /f "tokens=1,* delims= " %%i in ('type %script_path%etc\env.yaml^| findstr ": "') do (
  set add_path_key=%%i
  set add_path_key=!add_path_key::=!
  set add_path_value=%%j
  set !add_path_key!=!add_path_value!
)

for %%F in (%BK_PLUGIN_PID_PATH%) do set plugin_dir_path=%%~dpF
if not exist %plugin_dir_path% md %plugin_dir_path%

cd %GSE_AGENT_HOME%\plugins\bin\
bkmonitorbeat.exe -c %script_path%etc\bkmonitorbeat_debug.yaml