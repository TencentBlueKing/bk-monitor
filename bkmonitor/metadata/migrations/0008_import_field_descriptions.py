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

from django.db import migrations

logger = logging.getLogger("metadata")

models = {"ResultTableField": None, "ResultTable": None, "DataSource": None}


def import_description(apps, schema_editor):

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    with open("./metadata/data/description_unit.json", "r", encoding="utf-8") as unit_file:
        field_list = json.load(unit_file)

    # 遍历获取所有的字段
    for field_info in field_list:
        # 转换结果表ID
        old_table_id = field_info["result_table_id"]
        first_index = old_table_id.index("_")

        table_id = ".".join([old_table_id[:first_index], old_table_id[first_index + 1 :]])
        field_name = field_info["item"]

        # 更新信息
        try:
            field_object = models["ResultTableField"].objects.get(table_id=table_id, field_name=field_name)
        except models["ResultTableField"].DoesNotExist:
            print("table->[{}] field->[{}] is missing".format(table_id, field_name))
            continue

        field_object.description = field_info["item_display"]
        field_object.unit = field_info["conversion_unit"]
        field_object.save()


def add_ip_field(apps, schema_editor):
    """所有的结果表增加IP字段"""

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    for result_table in models["ResultTable"].objects.all():

        try:
            # 已经存在的，更新之
            ip_field = models["ResultTableField"].objects.get(table_id=result_table.table_id, field_name="ip")
            ip_field.description = "采集器IP地址"
            ip_field.save()

        except models["ResultTableField"].DoesNotExist:

            models["ResultTableField"].objects.create(
                table_id=result_table.table_id,
                field_name="ip",
                field_type="string",
                unit="",
                tag="dimension",
                is_config_by_user=True,
                default_value=None,
                creator="system",
                description="采集器IP地址",
            )


def update_field_info(apps, schema_editor):
    """更新已经存在的字段信息"""
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 更新字段拼写问题
    usage_field = models["ResultTableField"].objects.get(table_id="system.proc", field_name="mem_useage_pct")
    usage_field.field_name = "mem_usage_pct"
    usage_field.save()

    usage_field = models["ResultTableField"].objects.get(table_id="uptimecheck.http", field_name="chartset")
    usage_field.field_name = "charset"
    usage_field.save()

    # 增加mysql.innodb的pg_read_cnt字段
    models["ResultTableField"].objects.create(
        table_id="mysql.innodb",
        field_name="pg_read_cnt",
        field_type="float",
        unit="",
        tag="metric",
        is_config_by_user=True,
        default_value=None,
        creator="system",
    )

    # 更新mysql.rep的slave_running字段类型
    running_field = models["ResultTableField"].objects.get(table_id="mysql.rep", field_name="slave_running")
    running_field.field_type = "string"
    running_field.save()

    # 更新所有的bk_biz_id，bk_cloud_id，bk_supplier_id 和 time的描述
    models["ResultTableField"].objects.filter(field_name="bk_biz_id").update(description="业务ID")
    models["ResultTableField"].objects.filter(field_name="bk_supplier_id").update(description="开发商ID")
    models["ResultTableField"].objects.filter(field_name="bk_cloud_id").update(description="云区域ID")
    models["ResultTableField"].objects.filter(field_name="time").update(description="数据上报时间")

    # 更新hostname的字段描述
    models["ResultTableField"].objects.filter(field_name="hostname").update(description="主机名")
    models["ResultTableField"].objects.filter(field_name="device_name").update(description="设备名")

    # instance_id统一更新
    models["ResultTableField"].objects.filter(field_name="instance_id").update(description="instance_id")


def import_system_load(apps, schema_editor):
    """增加system_load的结果表"""

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 创建结果表
    result_table_object = models["ResultTable"].objects.create(
        table_id="system.load",
        table_name_zh="system.load",
        is_custom_table=False,
        schema_type="fixed",
        default_storage="influxdb",
        creator="system",
        last_modify_user="system",
    )

    # 创建字段
    field_list = [
        {
            "field_name": "load1",
            "field_type": "float",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "metric",
        },
        {
            "field_name": "load5",
            "field_type": "float",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "metric",
        },
        {
            "field_name": "load15",
            "field_type": "float",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "metric",
        },
        {
            "field_name": "bk_biz_id",
            "field_type": "int",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "dimension",
        },
        {
            "field_name": "bk_supplier_id",
            "field_type": "int",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "dimension",
        },
        {
            "field_name": "bk_cloud_id",
            "field_type": "int",
            "operator": "system",
            "is_config_by_user": True,
            "tag": "dimension",
        },
        {"field_name": "time", "field_type": "timestamp", "operator": "system", "is_config_by_user": True, "tag": ""},
    ]

    for field_info in field_list:
        models["ResultTableField"].objects.create(
            table_id=result_table_object.table_id,
            field_name=field_info["field_name"],
            field_type=field_info["field_type"],
            unit="",
            tag=field_info["tag"],
            is_config_by_user=True,
            default_value=None,
            creator="system",
        )


def update_etl_config(apps, schema_editor):
    """更新etl配置问题"""

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    models["DataSource"].objects.filter(etl_config="bk_exportor").update(etl_config="bk_exporter")


def total_run(apps, schema_editor):

    import_system_load(apps, schema_editor)
    add_ip_field(apps, schema_editor)
    update_field_info(apps, schema_editor)
    import_description(apps, schema_editor)
    update_etl_config(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0007_import_datasource"),
    ]

    operations = [migrations.RunPython(total_run)]
