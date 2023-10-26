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

"""
更新exporter的datasoruce及resulttabe option配置，防止由于数据重复拆分和补充导致transfer性能下降严重
"""


def update_datasource_option(apps, schema_editor):

    DataSource = apps.get_model("metadata", "DataSource")
    DataSourceOption = apps.get_model("metadata", "DataSourceOption")
    ResultTableOption = apps.get_model("metadata", "ResultTableOption")
    DataSourceResultTable = apps.get_model("metadata", "DataSourceResultTable")

    # 获取所有受到影响的datasource
    for data_source in DataSource.objects.filter(etl_config="bk_exporter"):

        # 判断datasource是否已经增加了配置
        if not DataSourceOption.objects.filter(
            bk_data_id=data_source.bk_data_id, name="allow_dimensions_missing"
        ).exists():
            logger.info(
                "data_id->[%s] does not has option->[allow_dimensions_missing] will create one.", data_source.bk_data_id
            )

            # 如果没有增加，则需要追加
            DataSourceOption.objects.create(
                value_type="bool",
                value="true",
                creator="system",
                bk_data_id=data_source.bk_data_id,
                name="allow_dimensions_missing",
            )
            logger.info("data_id->[%s] added option->[allow_dimensions_missing] success.", data_source.bk_data_id)

        # 获取这个datasource相关的结果表列表
        for result_table in DataSourceResultTable.objects.filter(bk_data_id=data_source.bk_data_id):

            # 判断结果表是否已经增加了配置
            if not ResultTableOption.objects.filter(
                table_id=result_table.table_id, name="enable_default_value"
            ).exists():
                logger.info(
                    "data_id->[%s] rt->[%s] does not has option->[enable_default_value] will create one.",
                    data_source.bk_data_id,
                    result_table.table_id,
                )

                # 如果没有增加，则需要追加
                ResultTableOption.objects.create(
                    value_type="bool",
                    value="false",
                    creator="system",
                    table_id=result_table.table_id,
                    name="enable_default_value",
                )
                logger.info(
                    "data_id->[%s] rt->[%s] added option->[allow_dimensions_missing] success.",
                    data_source.bk_data_id,
                    result_table.table_id,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0067_datasource_consul_prefix"),
    ]

    operations = [migrations.RunPython(update_datasource_option)]
