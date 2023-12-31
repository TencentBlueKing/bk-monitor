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
# Generated by Django 1.11.23 on 2020-11-04 07:45


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0090_auto_20200810_1153"),
    ]

    operations = [
        migrations.CreateModel(
            name="UptimeCheckTaskSubscription",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("create_user", models.CharField(blank=True, max_length=32, verbose_name="创建人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="修改时间")),
                ("update_user", models.CharField(blank=True, max_length=32, verbose_name="修改人")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("uptimecheck_id", models.IntegerField(default=0, verbose_name="拨测任务id")),
                ("subscription_id", models.IntegerField(default=0, verbose_name="节点管理订阅ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="uptimechecktasksubscription",
            unique_together={("uptimecheck_id", "bk_biz_id")},
        ),
    ]
