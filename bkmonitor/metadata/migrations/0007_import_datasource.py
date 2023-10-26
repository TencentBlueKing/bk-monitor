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
from django.db import models as django_model

logger = logging.getLogger("metadata")


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0006_auto_20190321_1443"),
    ]

    operations = [
        # 增加业务ID字段信息
        migrations.AddField(
            model_name="resulttable",
            name="bk_biz_id",
            field=django_model.IntegerField(default=0, verbose_name="\u7ed3\u679c\u8868\u6240\u5c5e\u4e1a\u52a1"),
        ),
    ]
