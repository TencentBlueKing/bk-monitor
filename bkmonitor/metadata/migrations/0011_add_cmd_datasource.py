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


import logging

from django.db import migrations

from metadata import config

logger = logging.getLogger("metadata")

models = {"DataSource": None, "ClusterInfo": None, "KafkaTopicInfo": None}


def add_datasource_record(apps, schema_editor):

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    kafka_cluster = models["ClusterInfo"].objects.get(cluster_type="kafka")

    data_object = models["DataSource"].objects.create(
        bk_data_id=1100000,
        data_name="cmd_report",
        etl_config="",
        creator="system",
        mq_cluster_id=kafka_cluster.cluster_id,
        is_custom_source=False,
        data_description="init data_source for cmd_report",
        # 由于mq_config和data_source两者相互指向对方，所以只能先提供占位符，先创建data_source
        mq_config_id=0,
        last_modify_user="system",
    )

    # 获取这个数据源对应的配置记录model，并创建一个新的配置记录
    mq_config = models["KafkaTopicInfo"].objects.create(
        bk_data_id=data_object.bk_data_id,
        topic="{}{}0".format(config.KAFKA_TOPIC_PREFIX, data_object.bk_data_id),
        partition=1,
    )
    data_object.mq_config_id = mq_config.id
    data_object.save()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0010_add_load_influxstorage"),
    ]

    operations = [migrations.RunPython(add_datasource_record)]
