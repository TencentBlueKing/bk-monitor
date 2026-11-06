@echo off
setlocal enabledelayedexpansion

set script_path=%~dp0
for /f "tokens=1,* delims= " %%i in ('type %script_path%etc\env.yaml^| findstr ": "') do (
  set add_path_key=%%i
  set add_path_key=!add_path_key::=!
  set add_path_value=%%j
  set !add_path_key!=!add_path_value!
)

if not exist %BK_PLUGIN_LOG_PATH% md %BK_PLUGIN_LOG_PATH%
for %%F in (%BK_PLUGIN_PID_PATH%) do set bk_plugin_pid_dir=%%~dpF
if not exist %bk_plugin_pid_dir% md %bk_plugin_pid_dir%

set log_filepath=%BK_PLUGIN_LOG_PATH%\{{ plugin_id }}.log
set pid_path=%BK_PLUGIN_PID_PATH%

start /B %script_path%{{ plugin_id }}.exe %BK_CMD_ARGS% >%log_filepath% 2>&1

ping -n 2 127.0.0.1>nul

echo process tried to start
echo checking process status...

set "escape_script_path=!script_path:\=\\!"
wmic process where name="{{ plugin_id }}.exe" get name,executablepath,processid | findstr "%escape_script_path%">nul

if %ERRORLEVEL% NEQ 0 (
  echo process exited too quickly
  echo process log:
  type %log_filepath%
  exit 1
)
for /f "tokens=1,2,* delims= " %%a in ('wmic process where "name='{{ plugin_id }}.exe'" get Name^,executablepath^,processid ^| findstr "%escape_script_path%"') do (
  echo process started successfully, pid:%%c
  echo %%c >%pid_path%)

