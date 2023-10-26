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

from metadata.migration_util import (
    add_datasource,
    add_datasourceresulttable,
    add_resulttable,
    add_resulttablefield,
    add_influxdbstorage,
    add_datasource_token,
    models,
)

logger = logging.getLogger("metadata")


def add_ping_datasource(apps, *args, **kwargs):
    """追加ping的初始化数据"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    bk_biz_id = 0
    # 数据库记录的操作员
    user = "system"
    # 数据id，用于整个链路的数据流转标识
    data_id = 1100003
    # data_id对应的名称
    data_name = "uptimecheck_icmp"
    # 结果表id
    table_id = "uptimecheck.icmp"
    # 结果表名称
    table_name_zh = "ICMP"
    # 数据清洗类型
    etl_config = "bk_standard"
    # 来源标签
    source_label = "bk_monitor"
    # 数据上报形式，这里指以时序形式上报
    type_label = "time_series"
    # 数据业务标签，这里指拨测类数据
    label = "uptimecheck"
    # 默认存储介质
    default_storage = "influxdb"
    # 是否是用户自定义
    is_custom_table = 0
    is_custom_source = False
    # 固定格式
    schema_type = "fixed"
    # 实际influxdb对应的数据库名
    database = "uptimecheck"
    # 实际influxdb对应的表名
    real_table_name = "icmp"
    # rp过期时间
    source_duration_time = "30d"

    field_item_list = [
        {"field_name": "ip", "field_type": "string", "unit": "", "tag": "dimension", "description": "采集器ip"},
        {"field_name": "bk_cloud_id", "field_type": "int", "unit": "", "tag": "dimension", "description": "采集器云区域id"},
        {"field_name": "bk_biz_id", "field_type": "int", "unit": "", "tag": "dimension", "description": "业务id"},
        {"field_name": "task_id", "field_type": "int", "unit": "", "tag": "dimension", "description": "任务id"},
        {"field_name": "target", "field_type": "string", "unit": "", "tag": "dimension", "description": "目标地址"},
        {"field_name": "target_type", "field_type": "string", "unit": "", "tag": "dimension", "description": "目标地址类型"},
        {"field_name": "error_code", "field_type": "int", "unit": "", "tag": "dimension", "description": "错误码"},
        {"field_name": "loss_percent", "field_type": "double", "unit": "", "tag": "metric", "description": "丢包率"},
        {"field_name": "max_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "最大时延"},
        {"field_name": "min_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "最大时延"},
        {"field_name": "avg_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "最大时延"},
        {"field_name": "time", "field_type": "timestamp", "unit": "", "tag": "timestamp", "description": "上报时间"},
    ]

    add_datasource(models, data_id, data_name, etl_config, source_label, type_label, user, is_custom_source)
    add_datasourceresulttable(models, data_id, table_id, user)
    add_resulttable(
        models, table_id, table_name_zh, label, default_storage, is_custom_table, schema_type, user, bk_biz_id
    )
    add_resulttablefield(models, table_id, field_item_list, user)
    add_influxdbstorage(table_id, database, real_table_name, source_duration_time)
    # 给datasource增加token
    add_datasource_token(models, data_id)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0059_merge_20200416_1159"),
    ]

    operations = [migrations.RunPython(add_ping_datasource)]
