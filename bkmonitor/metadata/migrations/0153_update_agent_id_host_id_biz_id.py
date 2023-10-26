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


def delete_fields_and_add_log_options(apps, schema_editor):
    """删除指定字段并针对日志添加对应的字段选项

    - 删除 0145_add_all_agent_id_host_id_biz_id 创建的指定类型的结果表字段
        - bk_standard_v2_event、apm 删除指定的三个字段，具体参照逻辑
        - log 删除指定的两个字段，具体参照逻辑
    - 检查针对日志的是否添加 option，如果不存在，则需要创建
    """
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 列举需要的字段
    deleted_fields = [
        ResultTableField.FIELD_DEF_BK_AGENT_ID,
        ResultTableField.FIELD_DEF_BK_HOST_ID,
        ResultTableField.FIELD_DEF_BK_TARGET_HOST_ID,
    ]
    deleted_fields_for_log = [ResultTableField.FIELD_DEF_BK_AGENT_ID, ResultTableField.FIELD_DEF_BK_TARGET_HOST_ID]
    added_option_fields_for_log = [ResultTableField.FIELD_DEF_BK_HOST_ID]
    option_names_for_log = [
        ResultTableFieldOption.OPTION_ES_FIELD_TYPE,
        ResultTableFieldOption.OPTION_ES_INCLUDE_IN_ALL,
    ]
    # 过滤 bk_standard_v2_event、apm, 然后进行删除对应的字段
    custom_table_ids = filter_table_ids(models["DataSource"], models["DataSourceResultTable"])
    apm_log_table_ids = filter_apm_log_table_ids(models["DataSource"], models["DataSourceResultTable"])
    apm_table_ids, log_table_ids = apm_log_table_ids["apm"], apm_log_table_ids["log"]
    custom_table_ids.extend(apm_table_ids)
    # 删除字段
    deleted_field_names = [field["field_name"] for field in deleted_fields]
    models["ResultTableField"].objects.filter(
        table_id__in=custom_table_ids, field_name__in=deleted_field_names
    ).delete()
    # 删除日志对应的字段
    models["ResultTableField"].objects.filter(
        table_id__in=log_table_ids, field_name__in=deleted_fields_for_log
    ).delete()

    # 添加字段对应的 option
    exist_option_table_ids_for_log = (
        models["ResultTableFieldOption"]
        .objects.filter(
            field_name__in=[field["field_name"] for field in added_option_fields_for_log], name__in=option_names_for_log
        )
        .values_list("table_id", flat=True)
        .distinct()
    )
    print("exist_option_table_ids_for_log", exist_option_table_ids_for_log)

    added_option_table_ids_for_log = set(log_table_ids) - set(exist_option_table_ids_for_log)

    # 组装日志对应字段选项的对象
    table_id_es_version = filter_table_id_es_versions(models["ESStorage"], models["ClusterInfo"], log_table_ids)
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
    models["ResultTableFieldOption"].objects.bulk_create(log_field_option_objs, batch_size=BULK_CREATE_SIZE)


def filter_table_ids(data_source_model: ModelBase, ds_rt_model: ModelBase) -> List:
    """根据 etl_config 过滤到对应的数据源"""
    exclude_etl_config_list = [
        "bk_standard_v2_time_series",
        "bk_standard_v2_event",
    ]
    data_ids = data_source_model.objects.filter(etl_config__in=exclude_etl_config_list).values_list(
        "bk_data_id", flat=True
    )
    return list(ds_rt_model.objects.filter(bk_data_id__in=data_ids).values_list("table_id", flat=True))


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0152_merge_20230504_1522"),
    ]

    operations = [migrations.RunPython(delete_fields_and_add_log_options)]
