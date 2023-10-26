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

from bkmonitor.utils.common_utils import host_key, parse_host_id


def init_log_task_upgrade(apps, schema_editor):
    LogCollectorHost = apps.get_model("monitor", "LogCollectorHost")
    GlobalConfig = apps.get_model("monitor", "GlobalConfig")
    log_collector_host = LogCollectorHost.objects.filter(is_deleted=False)

    # 整合主机host_id
    host_set = set()
    for item in log_collector_host:
        host_set.add(item.ip)

    result = {}
    for host_id in host_set:
        host_log_set = [x for x in log_collector_host if x.ip == host_id]
        biz_id = host_log_set[0].log_collector.biz_id

        # 从单个主机获取其所有日志采集任务
        tasks = []
        for host in host_log_set:
            tasks.append(
                {
                    "id": host.log_collector.pk,
                    "title": host.log_collector.data_set,
                    "desc": host.log_collector.data_desc,
                }
            )

        # 以业务ID为key传入GlobalConfig
        ip, bk_cloud_id = parse_host_id(host_id)
        result.update(
            {
                host_key(ip=ip, bk_cloud_id=bk_cloud_id): {
                    "ip": ip,
                    "bk_cloud_id": int(bk_cloud_id),
                    "bk_biz_id": biz_id,
                    "tasks": tasks,
                    "upgrade_status": "pending",
                }
            }
        )

    GlobalConfig.objects.create(key="log_task_upgrade", value=result)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0069_init_uploadedfile_data"),
    ]

    operations = [migrations.RunPython(init_log_task_upgrade)]
