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

from django.db import migrations


def intelligent_alarm_config_add_model_id(apps, *args, **kwargs):
    ReportItems = apps.get_model("bkmonitor", "ReportItems")
    for item in ReportItems.objects.filter(frequency__type=2):
        old_week_list = item.frequency["week_list"]
        # 判断week_list中是否已经存在1，若存在说明已经添加过[1,2,3,4,5]，避免重复添加
        if 1 not in old_week_list:
            old_week_list.extend([1, 2, 3, 4, 5])
            old_week_list.sort()
            item.save()


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0078_merge_20211231_1058"),
    ]

    operations = [
        migrations.RunPython(intelligent_alarm_config_add_model_id),
    ]
