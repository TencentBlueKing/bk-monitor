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


import json

from django.db import connection, migrations, models


def query_sql(sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    columns = [col[0] for col in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(list(zip(columns, row))))
    return results


def migrate_log_collector(apps, schema_editor):
    """
    将旧版日志采集数据切换到新版的模型中
    """
    # We can't import the model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    LogCollector = apps.get_model("monitor", "LogCollector")
    LogCollectorHost = apps.get_model("monitor", "LogCollectorHost")

    try:
        old_configs = query_sql("SELECT * from monitor_datasource;")
        old_hosts = query_sql("SELECT * from monitor_agentstatus;")

        new_configs = []
        new_hosts = []
        for config in old_configs:
            extra_config = json.loads(config["data_json"])
            instance = LogCollector(
                id=config["id"],
                biz_id=config["cc_biz_id"],
                data_id=config["data_id"],
                result_table_id=config["result_table_id"],
                create_user=config["creator"],
                update_user=config["update_user"],
                create_time=config["create_time"],
                update_time=config["update_time"],
                data_set=config["data_set"],
                data_desc=config["data_desc"],
                data_encode=extra_config["data_encode"],
                sep=extra_config["sep"],
                log_path=extra_config["log_path"],
                fields=extra_config["fields"],
                ips=extra_config["ips"],
                conditions=extra_config["conditions"],
                file_frequency=extra_config["file_frequency"],
            )
            new_configs.append(instance)

        for host in old_hosts:
            instance = LogCollectorHost(
                id=host["id"],
                log_collector_id=host["ds_id"],
                ip=host["ip"],
                plat_id=0,
                status=host["status"] if host["status"] != "delete" else "stopped",
                create_user=host["creator"],
                update_user=host["creator"],
                create_time=host["create_time"],
                update_time=host["update_time"],
            )
            new_hosts.append(instance)

        LogCollector.objects.bulk_create(new_configs)
        LogCollectorHost.objects.bulk_create(new_hosts)

    except Exception as e:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0034_merge_migrations"),
    ]

    operations = [migrations.RunPython(migrate_log_collector)]
