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
# Generated by Django 1.11.23 on 2021-06-28 12:18
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0047_auto_20210626_1119"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="actioninstance",
            name="matched_dimension_md5",
        ),
        migrations.AddField(
            model_name="actioninstance",
            name="dimension_hash",
            field=models.CharField(default="", max_length=64, verbose_name="匹配策略的维度哈希"),
        ),
        migrations.AlterField(
            model_name="actioninstance",
            name="dimensions",
            field=bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="关联的维度信息"),
        ),
        migrations.AlterField(
            model_name="actioninstance",
            name="failure_type",
            field=models.CharField(
                choices=[
                    ("unknown", "处理出错（未分类）"),
                    ("framework_code_failure", "自愈系统异常"),
                    ("timeout", "超时"),
                    ("execute_failure", "事件执行出错"),
                    ("create_failure", "任务创建失败"),
                    ("callback_failure", "任务回调失败"),
                    ("user_abort", "用户终止流程"),
                ],
                help_text="失败的时候标志失败类型",
                max_length=64,
                null=True,
                verbose_name="失败类型",
            ),
        ),
        migrations.AlterField(
            model_name="actioninstance",
            name="signal",
            field=models.CharField(
                choices=[
                    ("manual", "手动"),
                    ("abnormal", "告警产生时"),
                    ("recovered", "告警恢复时"),
                    ("closed", "告警关闭时"),
                    ("no_data", "无数据时"),
                    ("collect", "汇总"),
                ],
                help_text="触发该事件的告警信号，如告警异常，告警恢复，告警关闭等",
                max_length=64,
                verbose_name="触发信号",
            ),
        ),
        migrations.AlterField(
            model_name="strategyactionconfigrelation",
            name="signal",
            field=models.CharField(
                choices=[
                    ("manual", "手动"),
                    ("abnormal", "告警产生时"),
                    ("recovered", "告警恢复时"),
                    ("closed", "告警关闭时"),
                    ("no_data", "无数据时"),
                    ("collect", "汇总"),
                ],
                max_length=64,
                null=True,
            ),
        ),
    ]
