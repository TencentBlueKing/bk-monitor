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
import uuid

from bkcrypto.contrib.django.fields import SymmetricTextField
from django.db import migrations, models

import bkmonitor.utils.db.fields


def translate_field(apps, schema_editor):
    # 各个存储集群的配置
    cluster_info_model = apps.get_model("metadata", "ClusterInfo")
    for cluster in cluster_info_model.objects.all():
        cluster.save()

    # influxdb各个主机的配置
    influxdb_host_model = apps.get_model("metadata", "InfluxDBHostInfo")
    for host in influxdb_host_model.objects.all():
        host.save()


def add_datasource_token(apps, schema_editor):
    datasource_model = apps.get_model("metadata", "DataSource")

    for datasource in datasource_model.objects.all():
        datasource.token = uuid.uuid4().hex
        datasource.save()


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0051_change_proc_port_field_name"),
    ]

    operations = [
        # 修改事件model相关内容
        migrations.CreateModel(
            name="Event",
            fields=[
                ("event_id", models.AutoField(serialize=False, verbose_name="\u4e8b\u4ef6ID", primary_key=True)),
                ("event_group_id", models.IntegerField(verbose_name="\u4e8b\u4ef6\u6240\u5c5e\u5206\u7ec4ID")),
                ("event_name", models.CharField(max_length=255, verbose_name="\u4e8b\u4ef6\u540d\u79f0")),
                (
                    "dimension_list",
                    bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="\u7ef4\u5ea6\u5217\u8868"),
                ),
                (
                    "last_modify_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u66f4\u65b0\u65f6\u95f4"),
                ),
            ],
            options={
                "verbose_name": "\u4e8b\u4ef6\u63cf\u8ff0\u8bb0\u5f55",
                "verbose_name_plural": "\u4e8b\u4ef6\u63cf\u8ff0\u8bb0\u5f55\u8868",
            },
        ),
        migrations.DeleteModel(
            name="CustomEvent",
        ),
        migrations.DeleteModel(
            name="CustomEventDimension",
        ),
        # 清空原有的自定义事件上报配置数据
        migrations.RunSQL("DELETE FROM metadata_eventgroup;"),
        migrations.RenameField(
            model_name="eventgroup",
            old_name="bk_event_group_id",
            new_name="event_group_id",
        ),
        migrations.AddField(
            model_name="eventgroup",
            name="table_id",
            field=models.CharField(default="", max_length=128, verbose_name="\u7ed3\u679c\u8868ID"),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="event",
            unique_together={("event_group_id", "event_name")},
        ),
        # 修改datasoruce增加token
        migrations.AddField(
            model_name="datasource",
            name="token",
            field=models.CharField(default="", max_length=32, verbose_name="\u4e0a\u62a5\u6821\u9a8ctoken"),
        ),
        migrations.RunPython(add_datasource_token),
        # 需要对已有的字段先做好加密处理，然后再转换为加密字段
        migrations.RunPython(translate_field),
        migrations.AlterField(
            model_name="clusterinfo",
            name="password",
            field=SymmetricTextField(default="", max_length=128, verbose_name="\u5bc6\u7801"),
        ),
        migrations.AlterField(
            model_name="influxdbhostinfo",
            name="password",
            field=SymmetricTextField(default="", verbose_name="\u5bc6\u7801"),
        ),
    ]
