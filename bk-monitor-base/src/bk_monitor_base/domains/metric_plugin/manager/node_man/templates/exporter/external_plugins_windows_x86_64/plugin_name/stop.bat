@echo off
setlocal enabledelayedexpansion

set script_path=%~dp0

for /f "tokens=1,* delims= " %%i in ('type %script_path%etc\env.yaml^| findstr ": "') do (
  set add_path_key=%%i
  set add_path_key=!add_path_key::=!
  set add_path_value=%%j
  set !add_path_key!=!add_path_value!
)


for /f "tokens=1,* delims= " %%j in ('type !BK_PLUGIN_PID_PATH!') do (set pid=%%j)
taskkill /F /PID !pid!