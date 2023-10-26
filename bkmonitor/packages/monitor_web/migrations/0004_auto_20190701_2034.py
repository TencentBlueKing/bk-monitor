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

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0003_update_built-in_plugins"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectConfigMeta",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("bk_biz_id", models.IntegerField(verbose_name="\u4e1a\u52a1ID")),
                ("name", models.CharField(max_length=128, verbose_name="\u914d\u7f6e\u540d\u79f0")),
                (
                    "status",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u91c7\u96c6\u72b6\u6001",
                        choices=[
                            (b"STARTING", "\u542f\u7528\u4e2d"),
                            (b"STARTED", "\u5df2\u542f\u7528"),
                            (b"STOPPING", "\u505c\u7528\u4e2d"),
                            (b"STOPPED", "\u5df2\u505c\u7528"),
                            (b"DEPLOYING", "\u4e0b\u53d1\u4e2d"),
                        ],
                    ),
                ),
                (
                    "collect_type",
                    models.CharField(
                        db_index=True,
                        max_length=32,
                        verbose_name="\u91c7\u96c6\u65b9\u5f0f",
                        choices=[
                            (b"Exporter", b"Exporter"),
                            (b"Script", b"Script"),
                            (b"JMX", b"JMX"),
                            (b"DataDog", b"DataDog"),
                            (b"Pushgateway", "BK-Pull"),
                            (b"Built-In", "BK-Monitor"),
                            ("Log", "\u65e5\u5fd7"),
                        ],
                    ),
                ),
                (
                    "target_object_type",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u91c7\u96c6\u5bf9\u8c61\u7c7b\u578b",
                        choices=[(b"SERVICE", "\u670d\u52a1"), (b"HOST", "\u4e3b\u673a")],
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DeploymentConfigVersion",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("create_user", models.CharField(max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True)),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="\u4fee\u6539\u65f6\u95f4")),
                ("update_user", models.CharField(max_length=32, verbose_name="\u4fee\u6539\u4eba", blank=True)),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                ("parent_id", models.IntegerField(default=None, null=True, verbose_name="\u7236\u914d\u7f6eID")),
                ("config_meta_id", models.IntegerField(verbose_name="\u6240\u5c5e\u91c7\u96c6\u914d\u7f6eID")),
                (
                    "subscription_id",
                    models.IntegerField(default=0, verbose_name="\u8282\u70b9\u7ba1\u7406\u8ba2\u9605ID"),
                ),
                (
                    "target_node_type",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u91c7\u96c6\u76ee\u6807\u7c7b\u578b",
                        choices=[(b"TOPO", "\u62d3\u6251"), (b"INSTANCE", "\u5b9e\u4f8b")],
                    ),
                ),
                (
                    "params",
                    bkmonitor.utils.db.fields.JsonField(
                        default=None, verbose_name="\u91c7\u96c6\u53c2\u6570\u914d\u7f6e"
                    ),
                ),
                (
                    "target_nodes",
                    bkmonitor.utils.db.fields.JsonField(
                        default=[], verbose_name="\u91c7\u96c6\u76ee\u6807\u8282\u70b9"
                    ),
                ),
                (
                    "remote_collecting_host",
                    bkmonitor.utils.db.fields.JsonField(
                        default=None, verbose_name="\u8fdc\u7a0b\u91c7\u96c6\u673a\u5668"
                    ),
                ),
                (
                    "plugin_version",
                    models.ForeignKey(
                        related_name="deployment_versions",
                        verbose_name="\u5173\u8054\u63d2\u4ef6\u7248\u672c",
                        to="monitor_web.PluginVersionHistory",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="collectconfigmeta",
            name="deployment_config",
            field=models.ForeignKey(
                verbose_name="\u5f53\u524d\u7684\u90e8\u7f72\u914d\u7f6e",
                to="monitor_web.DeploymentConfigVersion",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="collectconfigmeta",
            name="plugin",
            field=models.ForeignKey(
                related_name="collect_configs",
                verbose_name="\u5173\u8054\u63d2\u4ef6",
                to="monitor_web.CollectorPluginMeta",
                on_delete=models.CASCADE,
            ),
        ),
    ]
