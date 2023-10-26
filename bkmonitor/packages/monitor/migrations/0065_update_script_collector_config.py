# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import base64
import copy
import hashlib

from django.db import migrations

bat_pro_metric = r"""@echo off
setlocal EnableDelayedExpansion

cd /d %~dp0
set temp_path=%~dp0
set M_File1=!temp_path!\INSERT_METRIC.txt
set D_File1=!temp_path!\INSERT_DIMENSION_Temp.txt
set D_File2=!temp_path!\INSERT_DIMENSION.txt

CALL :INIT

{script_content}

goto :eof

:INIT
if exist !M_File1! ( del /Q !M_File1! ) else ( goto :eof )
if exist !D_File1! ( del /Q !D_File1! ) else ( goto :eof )
if exist !D_File2! ( del /Q !D_File2! ) else ( goto :eof )
goto :eof

:INSERT_METRIC
echo %1 %2 >> !M_File1!
goto :eof

:INSERT_DIMENSION
echo %1 %2 >> !D_File1!
for /f "delims=" %%i in (%1 %2) do @(set /p="%1++%2,"<nul) >> !D_File2!
goto :eof

:INSERT_TIMESTAMP_TEMP
setlocal
for /f "skip=1 tokens=1-9" %%a in ('wmic path win32_utctime ^| findstr .') do set /a m=%%e+9,m%%=12,y=%%i-m/10,t=365*y+y/4-y/100+y/400+(m*306+5)/10+%%a-719469,t=t*86400+%%c*3600+%%d*60+%%g
endlocal & set %1=%t%
goto :eof

:INSERT_TIMESTAMP
if "%1"=="bk_now_time" (
    CALL :INSERT_TIMESTAMP_TEMP bk_now_time
    set "%bk_now_time%"=="%t%"
    goto :eof
) else (
    set bk_now_time="%1"
    goto :eof
)

:COMMIT
for /f "tokens=*" %%i in (!M_File1!) do (
set array=%%i
set /a index=0
    for /F "tokens=1,2,3*" %%a in ('echo(!array!') do (
    set METRIC_1[!index!]=%%a
    set METRIC_2[!index!]=%%b
    set /a index=!index!+1
        if exist !D_File2! (
            for /f "tokens=*" %%j in (!D_File2!) do (
            set new_data=%%a{%%j} %%b %bk_now_time%
            set new_data=!new_data:,}="}!
            set new_data=!new_data:"=!
            set new_data=!new_data:,=",!
            set new_data=!new_data:}="}!
            set new_data=!new_data:++=^="!
            )
        ) else (
            set new_data=%%a %%b %bk_now_time%
            set new_data=!new_data:"=!
        )
        echo !new_data!
        )
    )
)

CALL :INIT
goto :eof
"""
shell_pro_metric = r"""#!/bin/bash

METRIC_N=()
DIMENSION_N=()
BK_TIMESTAMP=()

INSERT_METRIC() {
    METRIC_N=("${METRIC_N[@]}" $1 $2)
}

INSERT_DIMENSION() {
    D2=`echo $2 | sed 's/"/\\\\"/g'`
    DIMENSION_N=("${DIMENSION_N[@]}" $1 $D2)
    echo ${DIMENSION_N[@]}
}

INSERT_TIMESTAMP() {
    if [[ $1 == "" ]] ; then
        BK_TIMESTAMP=`date "+%s"`
    else
        BK_TIMESTAMP=$1
    fi
}

COMMIT() {
    DIMENSION_X=()
    for i in $(seq 0 $[${#METRIC_N[@]}/2-1])
        do
            if [[ ${#DIMENSION_N[@]} == 0 ]] ; then
                COMMIT_X=$(echo ${METRIC_N[i*2]} ${METRIC_N[i*2+1]} $BK_TIMESTAMP)
                echo $COMMIT_X
            else
                unset DIMENSION_X    
                for j in $(seq 0 $[${#DIMENSION_N[@]}/2-1])
                    do
                        DIMENSION_X=("${DIMENSION_X[@]}" ${DIMENSION_N[j*2]}=\"${DIMENSION_N[j*2+1]}\",)
                    done
                COMMIT_TEMP=$(echo ${METRIC_N[i*2]}{${DIMENSION_X[@]} ${METRIC_N[i*2+1]} $BK_TIMESTAMP)
                COMMIT_X=`echo $COMMIT_TEMP|sed 's/\(.*\),\(.*\)/\1}\2/'`
                echo $COMMIT_X
             fi
        done
    unset METRIC_N DIMENSION_N DIMENSION_X
    BK_TIMESTAMP=()
}

{script_content}
"""


def update_script_collector_config(apps, schema_editor):
    ShellCollectorConfig = apps.get_model("monitor", "ShellCollectorConfig")
    ScriptCollectorConfig = apps.get_model("monitor", "ScriptCollectorConfig")
    ScriptCollectorInstance = apps.get_model("monitor", "ScriptCollectorInstance")
    GlobalConfig = apps.get_model("monitor", "GlobalConfig")
    operate_record_field_list = ["create_time", "create_user", "update_time", "update_user", "is_deleted"]
    shell_collector_config_list = ShellCollectorConfig.objects.all()
    old_script_filename = {}
    for old_config in shell_collector_config_list:
        new_config_field_list = [field.name for field in ScriptCollectorConfig._meta.fields]
        new_config = dict()
        script_instance_template = dict()

        # 判断脚本类型
        if old_config.shell_content:
            try:
                decode_result = base64.b64decode(old_config.shell_content)
                if ":COMMIT" in decode_result:
                    new_config["script_run_cmd"] = "${bk_script_name}"
                    new_config["script_ext"] = "bat"
                    script_content = bat_pro_metric.replace("{script_content}", decode_result)
                    new_config["script_content_base64"] = base64.b64encode(script_content.encode("utf-8"))

                else:
                    new_config["script_run_cmd"] = "${bk_script_name}"
                    new_config["script_ext"] = "shell"
                    script_content = shell_pro_metric.replace("{script_content}", decode_result)
                    new_config["script_content_base64"] = base64.b64encode(script_content.encode("utf-8"))

            except Exception as e:
                continue

        for new_field_name in new_config_field_list:
            if new_field_name in operate_record_field_list:
                script_instance_template[new_field_name] = getattr(old_config, new_field_name, None)

            if getattr(old_config, new_field_name, None) and new_field_name != "id":
                new_config[new_field_name] = getattr(old_config, new_field_name, None)

        new_config["name"] = old_config.table_name
        new_config["bk_biz_id"] = old_config.biz_id
        new_config["description"] = old_config.table_desc
        new_config["status"] = "saved" if old_config.status == "saved" else "draft"
        new_config["script_type"] = "file"
        new_config["params_schema"] = []
        config = ScriptCollectorConfig.objects.create(**new_config)

        if old_config.shell_content:
            # 获取旧数据下发脚本文件名
            hash_val = hashlib.md5(old_config.shell_content).hexdigest()
            shell_name = "{biz_id}_{table_name}_{hash_val}".format(
                biz_id=old_config.biz_id, table_name=old_config.table_name, hash_val=hash_val
            )
            old_script_filename[config.id] = shell_name

        if not old_config.ip_list:
            continue

        for host in old_config.ip_list:
            script_instance = copy.deepcopy(script_instance_template)
            script_instance["bk_biz_id"] = old_config.biz_id
            script_instance["type"] = "host"
            script_instance["ip"] = host.get("ip")
            script_instance["bk_cloud_id"] = host.get("plat_id")
            script_instance["config_id"] = config.id
            script_instance["params"] = {}
            ScriptCollectorInstance.objects.create(**script_instance)

    global_config = {"key": "old_script_filename", "value": old_script_filename}

    GlobalConfig.objects.create(**global_config)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0064_auto_20190221_1141"),
    ]

    operations = [
        migrations.RunPython(update_script_collector_config),
    ]
