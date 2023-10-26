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

from django.db import migrations

from metadata import config

logger = logging.getLogger("metadata")

models = {
    "KafkaStorage": None,
    "ClusterInfo": None,
    "Label": None,
}


def append_system_load_kafka_storage(apps, *args, **kwargs):
    """为system.load表追加kafka结果表"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    KafkaStorage = models["KafkaStorage"]
    ClusterInfo = models["ClusterInfo"]

    kafka_cluster = ClusterInfo.objects.get(cluster_type="kafka")

    table_id = "system.load"
    # 默认增加上kafka_topic的前缀
    topic = "_".join([config.KAFKA_TOPIC_PREFIX_STORAGE, table_id])

    if not KafkaStorage.objects.filter(table_id=table_id).exists():
        KafkaStorage.objects.create(
            table_id=table_id, storage_cluster_id=kafka_cluster.cluster_id, topic=topic, partition=1
        )


def fix_label_config(apps, *args, **kwargs):
    """修复label配置的问题及增加结果表other的标记"""

    Label = models["Label"]

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 修改is_admin_only配置错误的内容
    bad_label_list = ["application_check", "service_module", "component", "host_process", "os"]

    for label_id in bad_label_list:
        label = Label.objects.get(label_id=label_id)
        label.is_admin_only = False
        label.save()

    # 增加结果表的other
    Label.objects.create(
        label_id="other_rt",
        label_name="其他",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label="others",
        level=2,
        index=2,
    )

    # 删除service_process的label
    Label.objects.filter(label_id="service_process").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0030_kafkastorage_retention"),
    ]

    operations = [
        migrations.RunPython(append_system_load_kafka_storage),
        migrations.RunPython(fix_label_config),
    ]
