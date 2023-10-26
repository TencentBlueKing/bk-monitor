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
import os

from django.conf import settings
from django.db import migrations

from metadata import config

logger = logging.getLogger("metadata")

models = {"KafkaStorage": None, "ClusterInfo": None}


def append_kafka_storage(apps, *args, **kwargs):
    """为所有的内建结果表追加kafka结果表"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    KafkaStorage = models["KafkaStorage"]
    ClusterInfo = models["ClusterInfo"]

    kafka_cluster = ClusterInfo.objects.get(cluster_type="kafka")

    # 读取初始化配置信息
    init_data_path = os.path.join(settings.BASE_DIR, "metadata/data/init_data.json")
    with open(init_data_path) as init_file:
        init_data = json.load(init_file)

    # 遍历所有的内建结果表，创建kafka存储
    for result_table_info in init_data["result_table_list"]:

        table_id = result_table_info["table_id"]
        # 默认增加上kafka_topic的前缀
        topic = "_".join([config.KAFKA_TOPIC_PREFIX_STORAGE, table_id])

        # 如果这个结果表已经配置过kafka存储配置了，可以直接跳过
        if KafkaStorage.objects.filter(table_id=table_id).exists():
            continue

        KafkaStorage.objects.create(
            table_id=table_id, storage_cluster_id=kafka_cluster.cluster_id, topic=topic, partition=1
        )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0028_init_datasource_label"),
    ]

    operations = [
        migrations.RunPython(append_kafka_storage),
    ]
