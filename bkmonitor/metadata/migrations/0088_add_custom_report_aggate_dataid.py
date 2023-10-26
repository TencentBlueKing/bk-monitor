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

from django.conf import settings
from django.db import migrations

from metadata import config
from metadata.migration_util import (
    add_datasource,
    add_datasource_option,
    add_datasource_token,
    add_datasourceresulttable,
    add_influxdbstorage,
    add_resulttable,
    add_resulttablefield,
    models,
)

logger = logging.getLogger("metadata")


def add_gse_custom_report_aggregation_datasource(apps, *args, **kwargs):

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    bk_biz_id = 0
    # 数据库记录的操作员
    user = "system"
    # 数据id，用于整个链路的数据流转标识
    data_id = 1100011
    # data_id对应的名称
    data_name = f"{settings.AGGREGATION_BIZ_ID}_custom_report_aggate_dataid"
    # 结果表id
    table_id = "custom_report_aggate.base"
    # 结果表名称
    table_name_zh = "自定义上报聚合结果表"
    # 数据清洗类型
    etl_config = "bk_standard_v2_time_series"
    # 来源标签
    source_label = "bk_monitor"
    # 数据上报形式，这里指以时序形式上报
    type_label = "time_series"
    # 结果表标签，指监控对象，这里定义为其他
    label = "other_rt"
    # 默认存储介质
    default_storage = "influxdb"
    # 是否是用户自定义
    is_custom_table = 1
    is_custom_source = True
    # 固定格式
    schema_type = "free"
    # 实际influxdb对应的数据库名
    database = "custom_report_aggate"
    # 实际influxdb对应的表名
    real_table_name = "base"
    # rp过期时间
    source_duration_time = "30d"

    datasource_option = [
        {"name": "flat_batch_key", "value": "data", "value_type": "string"},  # 打散数据
        {"name": "timestamp_precision", "value": "ms", "value_type": "string"},  # 时间精度
        {"name": "disable_metric_cutter", "value": "true", "value_type": "string"},  # 上报influxdb的时候不打散metric field
        {
            "name": "metrics_report_path",
            "value": "{}/influxdb_metrics/{}/time_series_metric".format(config.CONSUL_PATH, data_id),
            "value_type": "string",
        },
    ]

    field_item_list = [
        {"field_name": "dimensions", "field_type": "object", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "metrics", "field_type": "object", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "target", "field_type": "string", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "time", "field_type": "timestamp", "unit": "", "tag": "timestamp", "description": "数据上报时间"},
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

    # 需要增加一个datasourceoption
    add_datasource_option(models, data_id, user, datasource_option)

    # 增加一个自定义时序的配置，以期可以自动发现新的指标和维度能力
    models["TimeSeriesGroup"].objects.create(
        bk_data_id=data_id,
        bk_biz_id=bk_biz_id,
        label=label,
        creator=user,
        last_modify_user=user,
        is_delete=False,
        is_enable=True,
        table_id=table_id,
        time_series_group_name="custom_report_aggate",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0087_merge_20210419_1853"),
    ]

    operations = [
        migrations.RunPython(add_gse_custom_report_aggregation_datasource),
    ]
