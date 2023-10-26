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

from bkmonitor.utils.common_utils import host_key


def init_script_task_upgrade(apps, schema_editor):
    GlobalConfig = apps.get_model("monitor", "GlobalConfig")
    ScriptCollectorInstance = apps.get_model("monitor", "ScriptCollectorInstance")
    all_instance = ScriptCollectorInstance.objects.filter(is_deleted=False)
    stored_data = {}
    for instance in all_instance:
        host = host_key(ip=instance.ip, plat_id=instance.bk_cloud_id)

        stored_data.setdefault(
            host,
            {
                "bk_biz_id": instance.bk_biz_id,
                "ip": instance.ip,
                "bk_cloud_id": instance.bk_cloud_id,
                "upgrade_status": "pending",
                "tasks": [],
            },
        )
        stored_data[host]["tasks"].append(
            {
                "id": instance.config.id,
                "title": instance.config.name,
                "desc": instance.config.description,
            }
        )

    GlobalConfig.objects.create(key="script_task_upgrade", value=stored_data)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0069_init_uploadedfile_data"),
    ]

    operations = [migrations.RunPython(init_script_task_upgrade)]
