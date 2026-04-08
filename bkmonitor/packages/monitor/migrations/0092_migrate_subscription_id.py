"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import api
from django.db import migrations


def migrate_subscription(apps, schema_editor):
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")
    UptimeCheckTaskSubscription = apps.get_model("monitor", "UptimeCheckTaskSubscription")
    tasks = UptimeCheckTask.objects.all()
    for task in tasks:
        bk_biz_id = task.bk_biz_id
        # 不为0说明有旧的订阅
        if task.subscription_id != 0:
            subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=task.pk, bk_biz_id=bk_biz_id)
            # 如果不为0，说明已经有订阅基于新方案生成，这时要删除老方案的订阅
            if len(subscriptions) != 0:
                # 先停再删
                api.node_man.switch_subscription(subscription_id=task.subscription_id, action="disable")
                api.node_man.delete_subscription(subscription_id=task.subscription_id)
            else:
                # 否则将该订阅直接写入到表中,对订阅本身不做操作
                UptimeCheckTaskSubscription.objects.create(
                    uptimecheck_id=task.pk, bk_biz_id=bk_biz_id, subscription_id=task.subscription_id
                )
        task.subscription_id = 0
        task.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0091_auto_20201104_1545"),
    ]

    operations = [
        migrations.RunPython(migrate_subscription),
    ]
