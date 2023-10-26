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
        ("monitor", "0039_auto_20180503_1310"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exporterdeposittask",
            name="process",
            field=models.CharField(
                default=b"READY",
                max_length=50,
                verbose_name="\u4efb\u52a1\u5f53\u524d\u6d41\u7a0b",
                choices=[
                    (b"READY", "\u4efb\u52a1\u5c31\u7eea"),
                    (b"CREATE_RT", "\u68c0\u67e5\u5e76\u521b\u5efa\u7ed3\u679c\u8868"),
                    (b"CREATE_DATASET", "\u68c0\u67e5\u5e76\u521b\u5efaDataSet"),
                    (b"SET_ETL_TEMPLATE", "\u68c0\u67e5\u5e76\u751f\u6210\u6e05\u6d17\u914d\u7f6e"),
                    (b"DEPLOY_TSDB", "\u68c0\u67e5\u5e76\u521b\u5efaTSDB"),
                    (b"START_DISPATCH", "\u542f\u52a8\u5165\u5e93\u7a0b\u5e8f"),
                    (b"START_DEPOSIT_TASK", "\u6b63\u5728\u6258\u7ba1exporter"),
                    (b"STOP_OLD_DEPOSIT_TASK", "\u53d6\u6d88\u8001\u7248\u672c\u914d\u7f6e\u7684IP\u6258\u7ba1"),
                    (b"FINISHED", "\u4efb\u52a1\u6d41\u7a0b\u5b8c\u6210"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="shellcollectordeposittask",
            name="process",
            field=models.CharField(
                default=b"ready",
                max_length=50,
                verbose_name="\u4efb\u52a1\u5f53\u524d\u6d41\u7a0b",
                choices=[
                    (b"ready", "\u4efb\u52a1\u5c31\u7eea"),
                    (b"create rt", "\u68c0\u67e5\u5e76\u521b\u5efa\u7ed3\u679c\u8868"),
                    (b"create dataset", "\u68c0\u67e5\u5e76\u521b\u5efaDataSet"),
                    (b"set etl template", "\u68c0\u67e5\u5e76\u751f\u6210\u6e05\u6d17\u914d\u7f6e"),
                    (b"deploy_tsdb", "\u68c0\u67e5\u5e76\u521b\u5efaTSDB"),
                    (b"start dispatch", "\u542f\u52a8\u5165\u5e93\u7a0b\u5e8f"),
                    (b"start deposit task", "\u6b63\u5728\u542f\u52a8\u811a\u672c\u6258\u7ba1\u7a0b\u5e8f"),
                    (b"stop old deposit task", "\u53d6\u6d88\u8001\u7248\u672c\u914d\u7f6e\u7684IP\u6258\u7ba1"),
                    (b"finished", "\u4efb\u52a1\u6d41\u7a0b\u5b8c\u6210"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="uptimechecktask",
            name="status",
            field=models.CharField(
                default=b"new_draft",
                max_length=20,
                verbose_name="\u5f53\u524d\u72b6\u6001",
                choices=[
                    (b"new_draft", "\u672a\u4fdd\u5b58"),
                    (b"running", "\u8fd0\u884c\u4e2d"),
                    (b"stoped", "\u672a\u6267\u884c"),
                    (b"starting", "\u542f\u52a8\u4e2d"),
                    (b"stoping", "\u505c\u6b62\u4e2d"),
                    (b"start_failed", "\u542f\u52a8\u5931\u8d25"),
                    (b"stop_failed", "\u505c\u6b62\u5931\u8d25"),
                ],
            ),
        ),
    ]
