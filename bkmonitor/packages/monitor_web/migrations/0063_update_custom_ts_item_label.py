"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
from collections import defaultdict

from django.db import migrations, models


def update_custom_ts_item_label(apps, *args, **kwargs):
    """
    更新自定义指标分组类型
    """
    # 获取APP models
    CustomTSTable = apps.get_model("monitor_web", "CustomTSTable")
    CustomTSItem = apps.get_model("monitor_web", "CustomTSItem")
    CustomTSGroupingRule = apps.get_model("monitor_web", "CustomTSGroupingRule")
    all_metrics = CustomTSItem.objects.all()

    group_ids = CustomTSTable.objects.all().values_list("time_series_group_id", flat=True)
    CustomTSGroupingRule.objects.all().delete()

    for group_id in group_ids:
        metrics = all_metrics.filter(table_id=group_id)
        group_map = defaultdict(set)
        for metric in metrics:
            group_map[metric.label].add(metric.metric_name)

        CustomTSGroupingRule.objects.bulk_create(
            (
                CustomTSGroupingRule(time_series_group_id=group_id, name=name, manual_list=manual_list)
                for name, manual_list in group_map.items()
                if name
            ),
            batch_size=200,
        )

        for name, manual_list in group_map.items():
            new_label = json.dumps([name] if name else [])
            CustomTSItem.objects.filter(table_id=group_id, label=name).update(label=new_label)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor_web", "0062_auto_20220921_2033"),
    ]

    operations = [
        migrations.AlterField(
            model_name='customtsitem',
            name='label',
            field=models.TextField(blank=True, default='', verbose_name='分组标签'),
        ),
        migrations.RunPython(update_custom_ts_item_label),
    ]
