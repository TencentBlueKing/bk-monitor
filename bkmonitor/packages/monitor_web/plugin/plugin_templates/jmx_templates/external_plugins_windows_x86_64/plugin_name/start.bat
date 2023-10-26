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

start /B java -jar jmx_exporter.jar %BK_LISTEN_HOST%:%BK_LISTEN_PORT% %BK_CONFIG_PATH% >%BK_PLUGIN_LOG_PATH%\{{ plugin_id }}.log  2>&1
timeout /t 1 >nul
for /f "tokens=1,2,3,4,5,* delims= " %%a in ('netstat -ano^| findstr ":%BK_LISTEN_PORT%"') do (echo %%e >%BK_PLUGIN_PID_PATH%)