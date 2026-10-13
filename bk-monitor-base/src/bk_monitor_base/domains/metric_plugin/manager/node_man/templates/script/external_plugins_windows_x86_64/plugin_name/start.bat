@echo off
setlocal enabledelayedexpansion

set script_path=%~dp0
for /f "tokens=1,* delims= " %%i in ('type %script_path%etc\env.yaml^| findstr ": "') do (
  set add_path_key=%%i
  set add_path_key=!add_path_key::=!
  set add_path_value=%%j
  set !add_path_key!=!add_path_value!
)

cd %script_path%

{% if collector_json.windows.type == "python" %}
python {{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% elif collector_json.windows.type == "powershell" %}
powershell  -file {{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% elif collector_json.windows.type == "perl" %}
perl {{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% elif collector_json.windows.type == "vbs" %}
cscript {{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% elif collector_json.windows.type == "shell" %}
bash {{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% else %}
{{ collector_json.windows.filename }} %BK_CMD_ARGS%
{% endif %}
