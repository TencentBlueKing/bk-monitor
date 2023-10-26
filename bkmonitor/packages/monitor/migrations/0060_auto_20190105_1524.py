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


from django.db import migrations, models


def change_ip_to_host_id(apps, schema_editor):
    ip_dot = "|"
    LogCollectorHost = apps.get_model("monitor", "LogCollectorHost")

    for collector_host in LogCollectorHost.objects.all():
        if len(collector_host.ip.split(ip_dot)) > 1:
            continue
        collector_host.ip = ip_dot.join([collector_host.ip, str(collector_host.plat_id)])
        collector_host.save()


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0059_merge"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="uptimecheckgroup",
            options={"verbose_name": "\u62e8\u6d4b\u5206\u7ec4", "verbose_name_plural": "\u62e8\u6d4b\u5206\u7ec4"},
        ),
        migrations.AlterField(
            model_name="logcollectorhost",
            name="plat_id",
            field=models.IntegerField(default=0, verbose_name="\u5e73\u53f0ID"),
        ),
        migrations.RunPython(change_ip_to_host_id),
    ]
