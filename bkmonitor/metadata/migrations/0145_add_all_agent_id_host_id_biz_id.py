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

from itertools import product
from typing import List

from django.db import migrations
from django.db.models.base import ModelBase

from metadata.migration_util import (
    filter_apm_log_table_ids,
    filter_table_id_es_versions,
    get_log_field_options,
)
from metadata.models import ResultTableField, ResultTableFieldOption

models = {
    "ResultTableField": None,
    "DataSource": None,
    "DataSourceResultTable": None,
    "ResultTableFieldOption": None,
    "ClusterInfo": None,
    "ESStorage": None,
}

DEFAULT_CREATOR = "system"
BULK_CREATE_SIZE = 500


def add_all_agent_id_host_id_biz_id(apps, schema_editor):
    """结果表增加字段agent_id,host_id,biz_id

    NOTE:
    - 忽略自定义时序、自定义事件、APM 对应的结果表
    - 针对日志结果表仅添加 [bk_host_id] 字段，并添加字段对应的 option
    """
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    fields = [
        ResultTableField.FIELD_DEF_BK_AGENT_ID,
        ResultTableField.FIELD_DEF_BK_HOST_ID,
        ResultTableField.FIELD_DEF_BK_TARGET_HOST_ID,
    ]

    # 非自定义数据源关联table_id列表
    not_custom_table_ids = filter_table_ids(models["DataSource"], models["DataSourceResultTable"])
    apm_log_table_ids = filter_apm_log_table_ids(models["DataSource"], models["DataSourceResultTable"])
    apm_table_ids, log_table_ids = apm_log_table_ids["apm"], apm_log_table_ids["log"]
    exclude_table_ids = []
    # apm 也需要忽略
    exclude_table_ids.extend(apm_table_ids)
    # 日志需要单独处理，仅添加 bk_host_id
    exclude_table_ids.extend(log_table_ids)

    print("not_custom_table_ids", not_custom_table_ids)
    exist_field_table_ids = (
        models["ResultTableField"]
        .objects.filter(field_name__in=[field["field_name"] for field in fields])
        .values_list("table_id", flat=True)
        .distinct()
    )
    print("exist_field_table_ids", exist_field_table_ids)

    # 为剩下的表添加字段
    added_field_table_ids = set(not_custom_table_ids) - set(exclude_table_ids) - set(exist_field_table_ids)
    field_objs = compose_rt_field_objs(models["ResultTableField"], list(added_field_table_ids), fields)
    models["ResultTableField"].objects.bulk_create(field_objs, batch_size=BULK_CREATE_SIZE)

    # 为日志添加字段及对应的 option
    # 日志需要添加的字段及 option
    fields_for_log = [ResultTableField.FIELD_DEF_BK_HOST_ID]
    option_names_for_log = [
        ResultTableFieldOption.OPTION_ES_FIELD_TYPE,
        ResultTableFieldOption.OPTION_ES_INCLUDE_IN_ALL,
    ]
    # 组装相应的数据
    table_id_es_version = filter_table_id_es_versions(models["ESStorage"], models["ClusterInfo"], log_table_ids)
    exist_field_table_ids_for_log = (
        models["ResultTableField"]
        .objects.filter(field_name__in=[field["field_name"] for field in fields_for_log])
        .values_list("table_id", flat=True)
        .distinct()
    )
    print("exist_field_table_ids_for_log", exist_field_table_ids_for_log)

    # 获取需要添加的字段的结果表
    added_field_table_ids_for_log = set(log_table_ids) - set(exist_field_table_ids_for_log)
    log_field_objs = compose_rt_field_objs(
        models["ResultTableField"], list(added_field_table_ids_for_log), fields_for_log
    )

    # 获取需要添加 option 的结果表
    exist_option_table_ids_for_log = (
        models["ResultTableFieldOption"]
        .objects.filter(field_name__in=[field["field_name"] for field in fields_for_log], name__in=option_names_for_log)
        .values_list("table_id", flat=True)
        .distinct()
    )
    print("exist_option_table_ids_for_log", exist_option_table_ids_for_log)

    added_option_table_ids_for_log = set(log_table_ids) - set(exist_option_table_ids_for_log)

    # 组装日志对应字段选项的对象
    log_field_option_objs = []
    for table_id in added_option_table_ids_for_log:
        # NOTE: 获取 es 版本
        es_version = table_id_es_version.get(table_id, "")
        # 获取 option，然后进行组装数据
        field_options = get_log_field_options(
            ResultTableField, ResultTableFieldOption, table_id, es_version, DEFAULT_CREATOR
        )
        for option in field_options:
            log_field_option_objs.append(models["ResultTableFieldOption"](**option))
    # 批量创建
    models["ResultTableField"].objects.bulk_create(log_field_objs, batch_size=BULK_CREATE_SIZE)
    models["ResultTableFieldOption"].objects.bulk_create(log_field_option_objs, batch_size=BULK_CREATE_SIZE)


def filter_table_ids(data_source_model: ModelBase, ds_rt_model: ModelBase) -> List:
    """根据 etl_config 过滤到对应的数据源"""
    exclude_etl_config_list = [
        "bk_standard_v2_time_series",
        "bk_standard_v2_event",
    ]
    data_ids = data_source_model.objects.exclude(etl_config__in=exclude_etl_config_list).values_list(
        "bk_data_id", flat=True
    )
    return list(ds_rt_model.objects.filter(bk_data_id__in=data_ids).values_list("table_id", flat=True))


def compose_rt_field_objs(rt_field_model: ModelBase, table_ids: List, fields: List) -> List:
    """组装结果表对应字段对象"""
    field_objs = []
    for table_id, field in product(table_ids, fields):
        field_objs.append(
            rt_field_model(
                table_id=table_id,
                field_name=field["field_name"],
                field_type=field["field_type"],
                unit=field["unit"],
                tag=field["tag"],
                is_config_by_user=True,
                creator=DEFAULT_CREATOR,
                description=field["description"],
            )
        )

    return field_objs


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0144_add_uptime_check_field_resolved_ip"),
    ]

    operations = [migrations.RunPython(add_all_agent_id_host_id_biz_id)]
