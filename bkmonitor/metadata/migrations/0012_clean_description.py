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
import re

from django.db import migrations
from django.db.models import Q

from metadata import config

logger = logging.getLogger("metadata")

models = {"ResultTableField": None}


def clean_description(apps, schema_editor):

    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 找到所有带有括号的描述内容
    for field in models["ResultTableField"].objects.filter(Q(description__contains="(") | Q(description__contains=")")):

        # 将括号及后面内容去掉，然后重新保存
        start_index = field.description.index("(")
        field.description = field.description[:start_index]
        field.save()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0011_add_cmd_datasource"),
    ]

    operations = [migrations.RunPython(clean_description)]
