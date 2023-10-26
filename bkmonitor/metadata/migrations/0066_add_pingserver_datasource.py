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
    add_datasource_option,
    models,
)

logger = logging.getLogger("metadata")


def add_pingserver_datasource(apps, *args, **kwargs):
    """初始化数据"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    bk_biz_id = 0
    # 数据库记录的操作员
    user = "system"
    # 数据id，用于整个链路的数据流转标识
    data_id = 1100005
    # data_id对应的名称
    data_name = "pingserver"
    # 结果表id
    table_id = "pingserver.base"
    # 结果表名称
    table_name_zh = "PING_SERVER上报数据"
    # 数据清洗类型
    etl_config = "bk_standard_v2_time_series"
    # 来源标签
    source_label = "bk_monitor"
    # 数据上报形式，这里指以时序形式上报
    type_label = "time_series"
    # 结果表标签，指监控对象，这里定义为"主机-操作系统"
    label = "os"
    # 默认存储介质
    default_storage = "influxdb"
    # 是否是用户自定义
    is_custom_table = 0
    is_custom_source = False
    # 固定格式
    schema_type = "free"
    # 实际influxdb对应的数据库名
    database = "pingserver"
    # 实际influxdb对应的表名
    real_table_name = "base"
    # rp过期时间
    source_duration_time = "30d"

    datasource_option = [
        {"name": "flat_batch_key", "value": "data", "value_type": "string"},  # 打散数据
        {"name": "timestamp_precision", "value": "ms", "value_type": "string"},  # 时间精度
        {"name": "disable_metric_cutter", "value": "true", "value_type": "string"},  # 上报influxdb的时候不打散metric field
    ]

    field_item_list = [
        {"field_name": "bk_biz_id", "field_type": "int", "unit": "", "tag": "dimension", "description": "业务ID"},
        {"field_name": "bk_target_ip", "field_type": "string", "unit": "", "tag": "dimension", "description": "目标IP"},
        {
            "field_name": "bk_target_cloud_id",
            "field_type": "int",
            "unit": "",
            "tag": "dimension",
            "description": "目标云区域ID",
        },
        {"field_name": "ip", "field_type": "string", "unit": "", "tag": "dimension", "description": "采集器IP"},
        {"field_name": "bk_cloud_id", "field_type": "int", "unit": "", "tag": "dimension", "description": "采集器云区域ID"},
        {"field_name": "loss_percent", "field_type": "double", "unit": "", "tag": "metric", "description": "丢包率"},
        {"field_name": "max_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "最大时延"},
        {"field_name": "min_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "最小时延"},
        {"field_name": "avg_rtt", "field_type": "double", "unit": "ms", "tag": "metric", "description": "平均时延"},
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

    # pingserver是采用的bk_standard_v2_time_series，需要增加一个datasourceoption
    add_datasource_option(models, data_id, user, datasource_option)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0065_merge_20200617_1730"),
    ]

    operations = [migrations.RunPython(add_pingserver_datasource)]
