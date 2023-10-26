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

models = {
    "ClusterInfo": None,
    "DataSource": None,
    "ResultTableField": None,
    "ResultTable": None,
    "DataSourceResultTable": None,
    "KafkaTopicInfo": None,
    "InfluxDBStorage": None,
}


def init_data(apps, schema_editor):
    """增加采集器心跳上报的元数据信息"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 读取初始化配置信息
    init_data_path = os.path.join(settings.BASE_DIR, "metadata/data/heartbeat_data.json")
    with open(init_data_path, "r", encoding="utf-8") as init_file:
        init_data = json.load(init_file)

    # 写入到数据库
    # 2. 写入datasource信息
    kafka_cluster = models["ClusterInfo"].objects.get(cluster_type="kafka")
    influx_cluster = models["ClusterInfo"].objects.get(cluster_type="influxdb")

    data_source_list = init_data["datasource_list"]
    for data_source in data_source_list:

        data_object = models["DataSource"].objects.create(
            bk_data_id=data_source["data_id"],
            data_name=data_source["data_id"],
            etl_config=data_source["etl"],
            creator="system",
            mq_cluster_id=kafka_cluster.cluster_id,
            is_custom_source=False,
            data_description="init data_source for %s" % data_source["data_id"],
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

    # 3. 写入结果表信息
    result_table_list = init_data["result_table_list"]

    for result_table in result_table_list:
        # 创建字段准备
        field_list = []
        for field in result_table["field_list"]:
            field_type = field["field_type"] if field["field_type"] != "long" else "int"

            # 判断字段的类型： dimension, metric, timestamp
            if field["is_dimension"]:
                field_tag = "dimension"

            # 如果不是维度，是否可能是时间字段
            elif field["field_name"] == "timestamp":
                field_tag = "timestamp"

            else:
                field_tag = "metric"

            field_list.append(
                {
                    "field_name": field["field_name"],
                    "field_type": field_type,
                    "operator": "system",
                    "is_config_by_user": True,
                    "tag": field_tag,
                    "unit": field["unit"],
                    "description": field["description"],
                }
            )

        # 追加时间、bk_biz_id和供应商的字段
        field_list.append(
            {
                "field_name": "bk_biz_id",
                "field_type": "int",
                "operator": "system",
                "is_config_by_user": True,
                "tag": "dimension",
                "unit": "",
                "description": "业务ID",
            }
        )

        field_list.append(
            {
                "field_name": "bk_supplier_id",
                "field_type": "int",
                "operator": "system",
                "is_config_by_user": True,
                "tag": "dimension",
                "unit": "",
                "description": "开发商ID",
            }
        )

        field_list.append(
            {
                "field_name": "bk_cloud_id",
                "field_type": "int",
                "operator": "system",
                "is_config_by_user": True,
                "tag": "dimension",
                "unit": "",
                "description": "云区域ID",
            }
        )

        field_list.append(
            {
                "field_name": "time",
                "field_type": "timestamp",
                "operator": "system",
                "is_config_by_user": True,
                "tag": "",
                "unit": "",
                "description": "数据上报时间",
            }
        )

        field_list.append(
            {
                "field_name": "ip",
                "field_type": "string",
                "operator": "system",
                "is_config_by_user": True,
                "tag": "dimension",
                "unit": "",
                "description": "采集器IP地址",
            }
        )

        # 创建结果表
        database, table_name = result_table["table_id"].split(".")
        result_table_object = models["ResultTable"].objects.create(
            table_id=result_table["table_id"],
            table_name_zh=result_table["table_name_zh"],
            is_custom_table=False,
            schema_type="fixed",
            default_storage=result_table["default_storage"],
            creator="system",
            last_modify_user="system",
        )

        # 3. 创建新的字段信息，同时追加默认的字段
        for field_info in field_list:
            models["ResultTableField"].objects.create(
                table_id=result_table_object.table_id,
                field_name=field_info["field_name"],
                field_type=field_info["field_type"],
                unit=field_info["unit"],
                tag=field_info["tag"],
                is_config_by_user=True,
                default_value=None,
                creator="system",
                description=field_info["description"],
            )

        # 4. 创建data_id和该结果表的关系
        models["DataSourceResultTable"].objects.create(
            bk_data_id=result_table["data_id"], table_id=result_table_object.table_id, creator="system"
        )

        # 5. 创建实际结果表记录
        models["InfluxDBStorage"].objects.create(
            table_id=result_table_object.table_id,
            storage_cluster_id=influx_cluster.cluster_id,
            database=database,
            real_table_name=table_name,
            source_duration_time="90d",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0013_fix_system_disk_schema"),
    ]

    operations = [migrations.RunPython(init_data)]
