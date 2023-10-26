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
import os
import uuid

from django.db import migrations

from metadata import config

logger = logging.getLogger("metadata")

models = {
    "DataSource": None,
    "DataSourceOption": None,
    "DataSourceResultTable": None,
    "ResultTable": None,
    "ResultTableField": None,
    "ClusterInfo": None,
    "KafkaTopicInfo": None,
    "InfluxDBStorage": None,
    "TimeSeriesGroup": None,
}


def add_datasource(models, data_id, data_name, etl_config, source_label, type_label, user):
    kafka_cluster = models["ClusterInfo"].objects.get(cluster_type="kafka", is_default_cluster=True)

    data_object = models["DataSource"].objects.create(
        bk_data_id=data_id,
        data_name=data_name,
        etl_config=etl_config,
        source_label=source_label,
        type_label=type_label,
        creator=user,
        mq_cluster_id=kafka_cluster.cluster_id,
        is_custom_source=False,
        data_description="init data_source for %s" % data_name,
        # 由于mq_config和data_source两者相互指向对方，所以只能先提供占位符，先创建data_source
        mq_config_id=0,
        last_modify_user=user,
    )

    # 获取这个数据源对应的配置记录model，并创建一个新的配置记录
    mq_config = models["KafkaTopicInfo"].objects.create(
        bk_data_id=data_object.bk_data_id,
        topic="{}{}0".format(config.KAFKA_TOPIC_PREFIX, data_object.bk_data_id),
        partition=1,
    )
    data_object.mq_config_id = mq_config.id
    data_object.save()


def add_datasourceresulttable(models, data_id, table_id, user):
    models["DataSourceResultTable"].objects.create(bk_data_id=data_id, table_id=table_id, creator=user)


def add_resulttable(models, table_id, table_name_zh, label, default_storage, is_custom_table, schema_type, user):
    models["ResultTable"].objects.create(
        table_id=table_id,
        table_name_zh=table_name_zh,
        is_custom_table=is_custom_table,
        schema_type=schema_type,
        default_storage=default_storage,
        creator=user,
        last_modify_user=user,
        bk_biz_id=0,
        label=label,
        is_enable=1,
    )


def add_resulttablefield(models, table_id, field_item_list, user):
    for item in field_item_list:
        models["ResultTableField"].objects.create(
            table_id=table_id,
            field_name=item["field_name"],
            field_type=item["field_type"],
            unit=item["unit"],
            tag=item["tag"],
            is_config_by_user=1,
            creator=user,
            description=item["description"],
        )


def add_influxdbstorage(table_id, database, real_table_name, source_duration_time):
    influx_cluster = models["ClusterInfo"].objects.get(cluster_type="influxdb", is_default_cluster=True)
    models["InfluxDBStorage"].objects.create(
        table_id=table_id,
        storage_cluster_id=influx_cluster.cluster_id,
        database=database,
        real_table_name=real_table_name,
        source_duration_time=source_duration_time,
    )


def add_datasource_token(models, data_id):
    datasource_model = models["DataSource"]
    datasource = datasource_model.objects.get(bk_data_id=data_id)
    datasource.token = uuid.uuid4().hex
    datasource.save()


def add_datasource_option(models, data_id, user, items):
    for item in items:
        models["DataSourceOption"].objects.create(
            bk_data_id=data_id,
            name=item["name"],
            value_type=item["value_type"],
            value=item["value"],
            creator=user,
        )


def add_bkunifylogbeat_common_datasource(apps, *args, **kwargs):

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 数据库记录的操作员
    user = "system"
    # 数据id，用于整个链路的数据流转标识
    data_id = 1100006
    # data_id对应的名称
    data_name = "bkunifylogbeat common metrics"
    # 结果表id
    table_id = "bkunifylogbeat_common.base"
    # 结果表名称
    table_name_zh = "bkunifylogbeat公共指标"
    # 数据清洗类型
    etl_config = "bk_standard_v2_time_series"
    # 来源标签
    source_label = "bk_monitor"
    # 数据上报形式，这里指以时序形式上报
    type_label = "time_series"
    # 结果表标签，指监控对象，这里定义为"主机-操作系统"
    label = "service_process"
    # 默认存储介质
    default_storage = "influxdb"
    # 是否是用户自定义
    is_custom_table = 0
    # 固定格式
    schema_type = "free"
    # 实际influxdb对应的数据库名
    database = "bkunifylogbeat_common"
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
        {"field_name": "time", "field_type": "timestamp", "unit": "", "tag": "timestamp", "description": "上报时间"},
    ]

    add_datasource(models, data_id, data_name, etl_config, source_label, type_label, user)
    add_datasourceresulttable(models, data_id, table_id, user)
    add_resulttable(models, table_id, table_name_zh, label, default_storage, is_custom_table, schema_type, user)
    add_resulttablefield(models, table_id, field_item_list, user)
    add_influxdbstorage(table_id, database, real_table_name, source_duration_time)
    # 给datasource增加token
    add_datasource_token(models, data_id)

    # 采用的bk_standard_v2_time_series，需要增加一个datasourceoption
    add_datasource_option(models, data_id, user, datasource_option)

    # 增加一个自定义时序的配置，以期可以自动发现新的指标和维度能力
    models["TimeSeriesGroup"].objects.create(
        bk_data_id=data_id,
        bk_biz_id=0,
        label="service_process",
        creator=user,
        last_modify_user=user,
        is_delete=False,
        is_enable=True,
        table_id=table_id,
        time_series_group_name="bkunifylogbeat common metrics",
    )


def add_bkunifylogbeat_task_datasource(apps, *args, **kwargs):

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 数据库记录的操作员
    user = "system"
    # 数据id，用于整个链路的数据流转标识
    data_id = 1100007
    # data_id对应的名称
    data_name = "bkunifylogbeat task metrics"
    # 结果表id
    table_id = "bkunifylogbeat_task.base"
    # 结果表名称
    table_name_zh = "bkunifylogbeat任务指标"
    # 数据清洗类型
    etl_config = "bk_standard_v2_time_series"
    # 来源标签
    source_label = "bk_monitor"
    # 数据上报形式，这里指以时序形式上报
    type_label = "time_series"
    # 结果表标签，指监控对象，这里定义为"主机-操作系统"
    label = "service_process"
    # 默认存储介质
    default_storage = "influxdb"
    # 是否是用户自定义
    is_custom_table = 0
    # 固定格式
    schema_type = "free"
    # 实际influxdb对应的数据库名
    database = "bkunifylogbeat_task"
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
        {"field_name": "time", "field_type": "timestamp", "unit": "", "tag": "timestamp", "description": "上报时间"},
    ]

    add_datasource(models, data_id, data_name, etl_config, source_label, type_label, user)
    add_datasourceresulttable(models, data_id, table_id, user)
    add_resulttable(models, table_id, table_name_zh, label, default_storage, is_custom_table, schema_type, user)
    add_resulttablefield(models, table_id, field_item_list, user)
    add_influxdbstorage(table_id, database, real_table_name, source_duration_time)
    # 给datasource增加token
    add_datasource_token(models, data_id)

    # 采用的bk_standard_v2_time_series，需要增加一个datasourceoption
    add_datasource_option(models, data_id, user, datasource_option)

    # 增加一个自定义时序的配置，以期可以自动发现新的指标和维度能力
    models["TimeSeriesGroup"].objects.create(
        bk_data_id=data_id,
        bk_biz_id=0,
        label="service_process",
        creator=user,
        last_modify_user=user,
        is_delete=False,
        is_enable=True,
        table_id=table_id,
        time_series_group_name="bkunifylogbeat task metrics",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0078_auto_20201214_1753"),
    ]

    operations = [
        migrations.RunPython(add_bkunifylogbeat_common_datasource),
        migrations.RunPython(add_bkunifylogbeat_task_datasource),
    ]
