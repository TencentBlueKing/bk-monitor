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

from metadata.migration_util import (
    add_datasource,
    add_datasource_option,
    add_datasource_token,
    add_datasourceresulttable,
    add_es_resulttableoption,
    add_esstorage,
    add_resulttable,
    add_resulttablefield,
    add_resulttablefieldoption,
    models,
)

logger = logging.getLogger("metadata")


def add_gse_system_event_data_source(apps, *args, **kwargs):
    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)
    print(f"add {1100000} gse_custom_string to es storage")
    add_event_data_source(models, 1100000, "gse_custom_string", "gse自定义字符串上报", "bk_gse_custom_string")
    print(f"add {1000} bk_gse_system_event to es storage")
    add_event_data_source(models, 1000, "gse_system_event", "gse系统事件上报", "bk_gse_system_event")


def add_event_data_source(models, data_id, table_id, table_name, etl_config):
    bk_biz_id = 0
    # 数据库记录的操作员
    user = "system"
    # 结果表标签，指监控对象
    label = "os"
    # 默认存储介质
    default_storage = "elasticsearch"
    # 是否是用户自定义
    is_custom_table = 1
    # 固定格式
    schema_type = "free"

    datasource_option = [
        {"name": "inject_local_time", "value": "true", "value_type": "bool"},
        {"name": "timestamp_precision", "value": "ms", "value_type": "string"},
        {"name": "flat_batch_key", "value": "data", "value_type": "string"},
    ]

    field_item_list = [
        {"field_name": "dimensions", "field_type": "object", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "event", "field_type": "object", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "event_name", "field_type": "string", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "target", "field_type": "string", "unit": "", "tag": "dimension", "description": ""},
        {"field_name": "time", "field_type": "timestamp", "unit": "", "tag": "timestamp", "description": "数据上报时间"},
    ]
    result_table_field_options = [
        {
            "value_type": "string",
            "value": "date_nanos",
            "creator": user,
            "table_id": table_id,
            "field_name": "time",
            "name": "es_type",
        },
        {
            "value_type": "string",
            "value": "epoch_millis",
            "creator": user,
            "table_id": table_id,
            "field_name": "time",
            "name": "es_format",
        },
        {
            "value_type": "string",
            "value": "object",
            "creator": user,
            "table_id": table_id,
            "field_name": "event",
            "name": "es_type",
        },
        {
            "value_type": "dict",
            "value": json.dumps({"content": {"type": "text"}, "count": {"type": "integer"}}),
            "creator": user,
            "table_id": table_id,
            "field_name": "event",
            "name": "es_properties",
        },
        {
            "value_type": "string",
            "value": "keyword",
            "creator": user,
            "table_id": table_id,
            "field_name": "target",
            "name": "es_type",
        },
        {
            "value_type": "string",
            "value": "object",
            "creator": user,
            "table_id": table_id,
            "field_name": "dimensions",
            "name": "es_type",
        },
        {
            "value_type": "bool",
            "value": "true",
            "creator": user,
            "table_id": table_id,
            "field_name": "dimensions",
            "name": "es_dynamic",
        },
        {
            "value_type": "string",
            "value": "keyword",
            "creator": user,
            "table_id": table_id,
            "field_name": "event_name",
            "name": "es_type",
        },
    ]

    models["DataSource"].objects.filter(bk_data_id=data_id).update(etl_config=etl_config)
    add_datasourceresulttable(models, data_id, table_id, user)
    add_datasource_option(models, data_id, user, datasource_option)

    add_resulttable(models, table_id, table_name, label, default_storage, is_custom_table, schema_type, user, bk_biz_id)
    add_es_resulttableoption(table_id, user)
    add_resulttablefield(models, table_id, field_item_list, user)
    add_resulttablefieldoption(result_table_field_options)

    add_esstorage(table_id)
    # 给datasource增加token
    add_datasource_token(models, data_id)


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0175_auto_20231102_1742"),
    ]

    operations = [
        migrations.RunPython(add_gse_system_event_data_source),
    ]
