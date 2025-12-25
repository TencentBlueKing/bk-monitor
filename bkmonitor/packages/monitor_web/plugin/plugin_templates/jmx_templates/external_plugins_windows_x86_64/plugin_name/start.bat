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

REM 设置 SSL_ENABLED 默认值为 false
if not defined SSL_ENABLED set SSL_ENABLED=false

REM 通用 JAR 启动参数
set JAR_ARGS=-jar jmx_exporter.jar %BK_LISTEN_HOST%:%BK_LISTEN_PORT% %BK_CONFIG_PATH%
set JAVA_BASE_CMD=java %JAR_ARGS%

REM 拼接完整 JAVA_CMD
if /i %SSL_ENABLED% == true (
  set JAVA_CMD=java -Djavax.net.ssl.trustStore=%SSL_TRUST_STORE% -Djavax.net.ssl.trustStorePassword=%SSL_TRUST_STORE_PASSWORD% -Djavax.net.ssl.keyStore=%SSL_KEY_STORE% -Djavax.net.ssl.keyStorePassword=%SSL_KEY_STORE_PASSWORD% %JAR_ARGS%
) else (
  set JAVA_CMD=%JAVA_BASE_CMD%
)

start /B %JAVA_CMD% >%BK_PLUGIN_LOG_PATH%\{{ plugin_id }}.log  2>&1

timeout /t 1 >nul
for /f "tokens=1,2,3,4,5,* delims= " %%a in ('netstat -ano^| findstr ":%BK_LISTEN_PORT%"') do (echo %%e >%BK_PLUGIN_PID_PATH%)