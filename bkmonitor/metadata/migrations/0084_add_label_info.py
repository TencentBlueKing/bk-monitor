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

logger = logging.getLogger("metadata")


def add_label_info(apps, schema_editor):
    """追加默认的label信息"""

    # 获取APP models
    Label = apps.get_model("metadata", "Label")

    Label.objects.filter(
        label_id="others",
        label_type="result_table_label",
    ).update(index=5)

    # 创建结果表标签
    # 一级标签

    Label.objects.create(
        label_id="data_center",
        label_name="数据中心",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label=None,
        level=1,
        index=4,
    )

    # 二级标签
    # 硬件设备
    Label.objects.create(
        label_id="hardware_device",
        label_name="硬件设备",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label="data_center",
        level=2,
        index=1,
    )

    # 主机 - 主机设备
    Label.objects.create(
        label_id="host_device",
        label_name="主机设备",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label="hosts",
        level=2,
        index=3,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0083_bkdatastorage"),
    ]

    operations = [
        migrations.RunPython(add_label_info),
    ]
