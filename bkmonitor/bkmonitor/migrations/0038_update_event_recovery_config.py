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
from django.conf import settings
from django.db import migrations
from django_mysql.models.functions import JSONSet


def update_event_recovery_config(apps, *args, **kwargs):
    """
    1. 系统重启
    2. corefile
    3. GSE进程托管事件
    4. 自定义字符型告警
    5. OOM
    针对以上5个告警事件，对告警恢复状态设置为关闭
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    DetectModel = apps.get_model("bkmonitor", "DetectModel")
    for s_id in settings.CLOSE_EVNET_METRIC_IDS:
        target_strategy_ids = QueryConfigModel.objects.filter(metric_id=s_id).values_list("strategy_id", flat=1)
        DetectModel.objects.filter(strategy_id__in=target_strategy_ids).update(
            recovery_config=JSONSet("recovery_config", {"$.status": "close"})
        )


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0037_fix_uptime_check_strategy"),
    ]

    operations = [
        migrations.RunPython(update_event_recovery_config),
    ]
