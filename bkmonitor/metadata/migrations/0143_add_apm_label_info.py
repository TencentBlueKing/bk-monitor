# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from __future__ import unicode_literals

from django.db import migrations


def add_apm_label(apps, schema_editor):
    Label = apps.get_model("metadata", "Label")

    # 用户体验 - APM
    Label.objects.create(
        label_id="apm",
        label_name="APM",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label="applications",
        level=2,
        index=3,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0142_merge_20230105_1108"),
    ]

    operations = [
        migrations.RunPython(add_apm_label),
    ]
