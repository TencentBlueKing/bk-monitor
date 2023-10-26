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


class Migration(migrations.Migration):

    dependencies = [
        ("weixin_core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bkweixinuser",
            name="email",
            field=models.CharField(max_length=128, verbose_name="\\u90ae\\u7bb1", blank=True),
        ),
        migrations.AddField(
            model_name="bkweixinuser",
            name="mobile",
            field=models.CharField(max_length=11, verbose_name="\\u624b\\u673a\\u53f7", blank=True),
        ),
        migrations.AddField(
            model_name="bkweixinuser",
            name="qr_code",
            field=models.CharField(max_length=128, verbose_name="\\u4e8c\\u7ef4\\u7801\\u94fe\\u63a5", blank=True),
        ),
        migrations.AddField(
            model_name="bkweixinuser",
            name="userid",
            field=models.CharField(
                max_length=128,
                null=True,
                verbose_name="\\u4f01\\u4e1a\\u5fae\\u4fe1\\u7528\\u6237\\u5e94\\u7528\\u552f\\u4e00\\u6807\\u8bc6",
            ),
        ),
        migrations.AlterField(
            model_name="bkweixinuser",
            name="openid",
            field=models.CharField(
                max_length=128,
                null=True,
                verbose_name="\\u5fae\\u4fe1\\u7528\\u6237\\u5e94\\u7528\\u552f\\u4e00\\u6807\\u8bc6",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="bkweixinuser",
            unique_together={("openid", "userid")},
        ),
    ]
