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


def add_cmdb_level_field(apps, schema_editor):
    """增加采集器心跳上报的元数据信息"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTable = models["ResultTable"]
    ResultTableField = models["ResultTableField"]

    # 1. 获取所有的结果表内容
    for result_table in ResultTable.objects.all():

        # 如果已经通过某些渠道添加了，跳过
        if ResultTableField.objects.filter(table_id=result_table.table_id, field_name="bk_cmdb_level"):
            continue

        # 2. 对每个结果表增加一个CMDB_LEVEL的字段
        ResultTableField.objects.create(
            table_id=result_table.table_id,
            field_name="bk_cmdb_level",
            field_type="string",
            unit="",
            tag="dimension",
            is_config_by_user=True,
            default_value=None,
            creator="system",
            description="CMDB层级信息",
        )
        logger.info("table->[{}] now has create cmdb_level".format(result_table.table_id))


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0022_auto_20190822_2017"),
    ]

    operations = [migrations.RunPython(add_cmdb_level_field)]
