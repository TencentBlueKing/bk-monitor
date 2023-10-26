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
import logging

from django.db import migrations

from metadata import config

logger = logging.getLogger("metadata")

models = {"InfluxDBStorage": None, "ClusterInfo": None}


def add_datasource_record(apps, schema_editor):

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    influx_cluster = models["ClusterInfo"].objects.get(cluster_type="influxdb")

    models["InfluxDBStorage"].objects.create(
        table_id="system.load",
        storage_cluster_id=influx_cluster.cluster_id,
        database="system",
        real_table_name="load",
        source_duration_time="90d",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0009_add_load_datasource"),
    ]

    operations = [migrations.RunPython(add_datasource_record)]
