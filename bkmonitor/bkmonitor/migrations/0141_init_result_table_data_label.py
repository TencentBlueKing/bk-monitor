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
import re

from django.conf import settings
from django.db import migrations

from bkmonitor.data_source import is_build_in_process_data_source
from monitor_web.plugin.constant import PluginType


def init_result_table_data_label(apps, *args, **kwargs):
    if settings.ROLE != "web":
        return
    ResultTable = apps.get_model("metadata", "ResultTable")
    TimeSeriesGroup = apps.get_model("metadata", "TimeSeriesGroup")
    CustomTSTable = apps.get_model("monitor_web", "CustomTSTable")

    plugin_type_list = [
        f"{getattr(PluginType, attr).lower()}_"
        for attr in dir(PluginType)
        if not callable(getattr(PluginType, attr))
        and not attr.startswith("__")
        and getattr(PluginType, attr) not in [PluginType.SNMP_TRAP, PluginType.LOG, PluginType.PROCESS]
    ]
    re_plugin_time_series = re.compile(r'^(' + '|'.join(plugin_type_list) + r').*$')
    re_custom_time_series = re.compile(r"\b\w*bkmonitor_time_series_\w*\b")

    custom_time_series_ids = list(TimeSeriesGroup.objects.all().values_list("table_id", flat=1))
    apm_table_regex = re.compile(r"(?:.*_)?bkapm_(?:.*)?metric_.*")
    # 过滤APM结果表
    custom_time_series_ids = [
        custom_time_series_id
        for custom_time_series_id in custom_time_series_ids
        if not apm_table_regex.match(custom_time_series_id)
    ]
    result_tables = ResultTable.objects.all()
    for result_table in result_tables:
        data_label = ""
        result_table_id = result_table.table_id
        if is_build_in_process_data_source(result_table_id):
            print(f"{result_table_id}为系统内置表，不支持data_label")
        elif re_plugin_time_series.match(result_table_id):
            data_label = result_table_id.split(".")[0]
        # 自定义时序型指标
        elif result_table_id in custom_time_series_ids:
            try:
                data_label = CustomTSTable.objects.get(table_id=result_table_id).data_label
            except CustomTSTable.DoesNotExist:
                if not re_custom_time_series.match(result_table_id):
                    data_label = result_table_id.split(".")[0]
                    print(f"自定义时序结果表{result_table_id}的data_label不存在，取前缀{data_label}")

        if data_label:
            result_table.data_label = data_label
            result_table.save()
            print(f"[result_table_id] {result_table_id} -> [data_label] {data_label}")
        else:
            print(f"[result_table_id] {result_table_id} -> 暂不支持data_label")


DEPENDENCIES = [
    ("bkmonitor", "0140_merge_0139_auto_20230613_1211_0139_auto_20230619_1048"),
    ("metadata", "0171_resulttable_data_label"),
]

if settings.ROLE == "web":
    DEPENDENCIES.append(("monitor_web", "0063_update_custom_ts_item_label"))


class Migration(migrations.Migration):
    dependencies = DEPENDENCIES

    operations = [
        migrations.RunPython(init_result_table_data_label),
    ]
