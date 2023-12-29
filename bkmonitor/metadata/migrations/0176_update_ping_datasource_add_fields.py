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

from metadata.migration_util import add_resulttablefield, models

logger = logging.getLogger("metadata")


def update_ping_datasource_add_fields(apps, *args, **kwargs):
    """追加ping的初始化数据"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 数据库记录的操作员
    user = "system"

    # 结果表id
    table_id = "uptimecheck.icmp"

    field_item_list = [
        {"field_name": "bkm_up_code", "field_type": "string", "unit": "", "tag": "dimension", "description": "采集状态码"},
        {"field_name": "bkm_gather_up", "field_type": "double", "unit": "", "tag": "metric", "description": "采集心跳"},
    ]

    add_resulttablefield(models, table_id, field_item_list, user)


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0175_auto_20231102_1742"),
    ]

    operations = [migrations.RunPython(update_ping_datasource_add_fields)]
