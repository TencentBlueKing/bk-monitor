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
from django.db import migrations, models

import metadata.models.constants


class Migration(migrations.Migration):
    dependencies = [
        ('metadata', '0182_datalinkresource_datalinkresourceconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventgroup',
            name='last_check_report_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='最后检查报告时间'),
        ),
        migrations.AddField(
            model_name='eventgroup',
            name='status',
            field=models.CharField(
                choices=[
                    (metadata.models.constants.EventGroupStatus['NORMAL'], '正常'),
                    (metadata.models.constants.EventGroupStatus['SLEEP'], '休眠'),
                ],
                default='normal',
                max_length=16,
                verbose_name='状态',
            ),
        ),
    ]
