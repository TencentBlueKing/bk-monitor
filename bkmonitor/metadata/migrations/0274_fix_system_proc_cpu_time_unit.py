"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import migrations

CPU_TIME_FIELDS = ["cpu_system", "cpu_total_ticks", "cpu_user"]


def update_system_proc_cpu_time_unit(apps, *args, **kwargs):
    ResultTable = apps.get_model("metadata", "ResultTable")
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    table_ids = set(ResultTable.objects.filter(data_label="system.proc").values_list("table_id", flat=True))
    table_ids.add("system.proc")
    ResultTableField.objects.filter(
        table_id__in=table_ids,
        field_name__in=CPU_TIME_FIELDS,
        unit="s",
    ).update(unit="ms")


class Migration(migrations.Migration):
    dependencies = [("metadata", "0273_pingserversubscriptionconfig_bk_biz_id")]

    operations = [migrations.RunPython(update_system_proc_cpu_time_unit, migrations.RunPython.noop)]
