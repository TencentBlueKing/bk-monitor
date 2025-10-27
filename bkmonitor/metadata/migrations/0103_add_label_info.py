# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import logging

from django.db import migrations

logger = logging.getLogger("metadata")


def add_label_info(apps, schema_editor):
    """追加默认的label信息"""

    # 获取APP models
    Label = apps.get_model("metadata", "Label")

    # 服务 - kubernetes
    Label.objects.create(
        label_id="kubernetes",
        label_name="kubernetes",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label="services",
        level=2,
        index=5,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0102_merge_20211111_2316"),
    ]

    operations = [
        migrations.RunPython(add_label_info),
    ]
