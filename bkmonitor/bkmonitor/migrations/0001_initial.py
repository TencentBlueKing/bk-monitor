"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime

from django.db import migrations, models
from django.utils.timezone import utc

import bkmonitor.middlewares.source
import bkmonitor.utils.db.fields


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Action",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("action_type", models.CharField(max_length=256, verbose_name="\u52a8\u4f5c\u7c7b\u578b")),
                ("config", bkmonitor.utils.db.fields.JsonField(verbose_name="\u52a8\u4f5c\u914d\u7f6e")),
                ("strategy_id", models.IntegerField(verbose_name="\u5173\u8054\u7b56\u7565ID", db_index=True)),
            ],
            options={
                "db_table": "alarm_action",
                "verbose_name": "\u52a8\u4f5c\u914d\u7f6e",
                "verbose_name_plural": "\u52a8\u4f5c\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="ActionNoticeMapping",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("action_id", models.IntegerField(verbose_name="\u5173\u8054\u52a8\u4f5cID", db_index=True)),
                (
                    "notice_group_id",
                    models.IntegerField(verbose_name="\u5173\u8054\u901a\u77e5\u7ec4ID", db_index=True),
                ),
            ],
            options={
                "db_table": "alarm_action_notice_group_mapping",
            },
        ),
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("method", models.CharField(max_length=32, verbose_name="\u901a\u77e5\u65b9\u5f0f")),
                (
                    "username",
                    models.CharField(max_length=32, verbose_name="\u901a\u77e5\u63a5\u6536\u4eba", db_index=True),
                ),
                (
                    "role",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u901a\u77e5\u63a5\u6536\u4eba\u89d2\u8272", blank=True
                    ),
                ),
                (
                    "create_time",
                    models.DateTimeField(auto_now_add=True, verbose_name="\u901a\u77e5\u65f6\u95f4", db_index=True),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u72b6\u6001",
                        choices=[
                            ("RUNNING", "\u901a\u77e5\u4e2d"),
                            ("SUCCESS", "\u901a\u77e5\u6210\u529f"),
                            ("FAILED", "\u901a\u77e5\u5931\u8d25"),
                        ],
                    ),
                ),
                ("message", models.TextField(verbose_name="(\u5931\u8d25|\u5c4f\u853d)\u539f\u56e0")),
                ("action_id", models.IntegerField(verbose_name="\u52a8\u4f5cID", db_index=True)),
                (
                    "event_id",
                    models.CharField(max_length=255, verbose_name="\u5173\u8054\u4e8b\u4ef6ID", db_index=True),
                ),
                ("alert_collect_id", models.IntegerField(verbose_name="\u6c47\u603bID", db_index=True)),
            ],
            options={
                "db_table": "alarm_alert",
                "verbose_name": "\u901a\u77e5\u52a8\u4f5c",
                "verbose_name_plural": "\u901a\u77e5\u52a8\u4f5c",
            },
        ),
        migrations.CreateModel(
            name="AlertCollect",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("bk_biz_id", models.IntegerField(default=0, db_index=True, verbose_name="\u4e1a\u52a1ID", blank=True)),
                ("collect_key", models.CharField(max_length=128, verbose_name="\u6c47\u603bkey")),
                (
                    "collect_type",
                    models.CharField(
                        default="DIMENSION",
                        max_length=32,
                        verbose_name="\u6c47\u603b\u7c7b\u578b",
                        choices=[
                            ("DIMENSION", "\u540c\u7ef4\u5ea6\u6c47\u603b"),
                            ("STRATEGY", "\u540c\u7b56\u7565\u6c47\u603b"),
                            ("MULTI_STRATEGY", "\u540c\u4e1a\u52a1\u6c47\u603b"),
                        ],
                    ),
                ),
                ("message", models.CharField(max_length=512, verbose_name="\u6c47\u603b\u539f\u56e0")),
                ("collect_time", models.DateTimeField(auto_now_add=True, verbose_name="\u6c47\u603b\u65f6\u95f4")),
            ],
            options={
                "db_table": "alarm_alert_collect",
                "verbose_name": "\u6c47\u603b\u8bb0\u5f55",
                "verbose_name_plural": "\u6c47\u603b\u8bb0\u5f55",
            },
        ),
        migrations.CreateModel(
            name="AnomalyRecord",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "anomaly_id",
                    models.CharField(unique=True, max_length=255, verbose_name="\u5f02\u5e38ID", db_index=True),
                ),
                ("source_time", models.DateTimeField(verbose_name="\u5f02\u5e38\u65f6\u95f4", db_index=True)),
                (
                    "create_time",
                    models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4", db_index=True),
                ),
                ("strategy_id", models.IntegerField(verbose_name="\u5173\u8054\u7b56\u7565ID", db_index=True)),
                (
                    "origin_alarm",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u539f\u59cb\u7684\u5f02\u5e38\u5185\u5bb9"),
                ),
                (
                    "event_id",
                    models.CharField(
                        default="", max_length=255, verbose_name="\u5173\u8054\u4e8b\u4ef6ID", db_index=True, blank=True
                    ),
                ),
            ],
            options={
                "db_table": "alarm_anomaly_record",
                "verbose_name": "\u5f02\u5e38",
                "verbose_name_plural": "\u5f02\u5e38",
            },
        ),
        migrations.CreateModel(
            name="BaseAlarm",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("alarm_type", models.IntegerField(default=0, verbose_name="\u544a\u8b66\u6807\u8bc6", blank=True)),
                (
                    "title",
                    models.CharField(
                        default="", max_length=256, verbose_name="\u57fa\u7840\u544a\u8b66\u540d\u79f0", blank=True
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        default="", max_length=256, verbose_name="\u57fa\u7840\u544a\u8b66\u63cf\u8ff0", blank=True
                    ),
                ),
                ("is_enable", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528", null=True)),
            ],
            options={
                "db_table": "dict_base_alarm",
            },
        ),
        migrations.CreateModel(
            name="CustomEventQueryConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("bk_event_group_id", models.IntegerField(verbose_name="\u81ea\u5b9a\u4e49\u4e8b\u4ef6\u5206\u7ec4ID")),
                ("custom_event_id", models.IntegerField(verbose_name="\u81ea\u5b9a\u4e49\u4e8b\u4ef6ID")),
                ("agg_dimension", bkmonitor.utils.db.fields.JsonField(verbose_name="\u805a\u5408\u7ef4\u5ea6")),
                ("agg_condition", bkmonitor.utils.db.fields.JsonField(verbose_name="\u76d1\u63a7\u6761\u4ef6")),
                ("extend_fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u6269\u5c55\u5b57\u6bb5")),
            ],
            options={
                "db_table": "alarm_custom_event_group_config",
                "verbose_name": "\u81ea\u5b9a\u4e49\u4e8b\u4ef6\u67e5\u8be2\u914d\u7f6e",
                "verbose_name_plural": "\u81ea\u5b9a\u4e49\u4e8b\u4ef6\u67e5\u8be2\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="DetectAlgorithm",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                (
                    "algorithm_type",
                    models.CharField(
                        max_length=128,
                        verbose_name="\u7b97\u6cd5\u7c7b\u578b",
                        choices=[
                            ("Threshold", "\u9759\u6001\u9608\u503c\u7b97\u6cd5"),
                            ("SimpleRingRatio", "\u7b80\u6613\u73af\u6bd4\u7b97\u6cd5"),
                            ("AdvancedRingRatio", "\u9ad8\u7ea7\u73af\u6bd4\u7b97\u6cd5"),
                            ("SimpleYearRound", "\u7b80\u6613\u540c\u6bd4\u7b97\u6cd5"),
                            ("AdvancedYearRound", "\u9ad8\u7ea7\u540c\u6bd4\u7b97\u6cd5"),
                            ("PartialNodes", "\u90e8\u5206\u8282\u70b9\u6570\u7b97\u6cd5"),
                            ("OsRestart", "\u4e3b\u673a\u91cd\u542f\u7b97\u6cd5"),
                            ("ProcPort", "\u8fdb\u7a0b\u7aef\u53e3\u7b97\u6cd5"),
                            ("YearRoundAmplitude", "\u540c\u6bd4\u632f\u5e45\u7b97\u6cd5"),
                            ("YearRoundRange", "\u540c\u6bd4\u533a\u95f4\u7b97\u6cd5"),
                            ("RingRatioAmplitude", "\u73af\u6bd4\u632f\u5e45\u7b97\u6cd5"),
                        ],
                    ),
                ),
                ("algorithm_config", bkmonitor.utils.db.fields.JsonField(verbose_name="\u7b97\u6cd5\u914d\u7f6e")),
                (
                    "trigger_config",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u89e6\u53d1\u6761\u4ef6\u914d\u7f6e"),
                ),
                (
                    "recovery_config",
                    bkmonitor.utils.db.fields.JsonField(verbose_name="\u6062\u590d\u6761\u4ef6\u914d\u7f6e"),
                ),
                ("message_template", models.TextField(verbose_name="\u7b97\u6cd5\u63cf\u8ff0\u6a21\u677f\u914d\u7f6e")),
                ("level", models.IntegerField(default=3, verbose_name="\u76d1\u63a7\u7b49\u7ea7", blank=True)),
                ("item_id", models.IntegerField(verbose_name="\u5173\u8054\u76d1\u63a7\u9879ID", db_index=True)),
                ("strategy_id", models.IntegerField(verbose_name="\u5173\u8054\u7b56\u7565ID", db_index=True)),
            ],
            options={
                "db_table": "alarm_detect_algorithm",
                "verbose_name": "\u68c0\u6d4b\u7b97\u6cd5\u914d\u7f6e",
                "verbose_name_plural": "\u68c0\u6d4b\u7b97\u6cd5\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "event_id",
                    models.CharField(unique=True, max_length=255, verbose_name="\u4e8b\u4ef6ID", db_index=True),
                ),
                ("begin_time", models.DateTimeField(verbose_name="\u4e8b\u4ef6\u4ea7\u751f\u65f6\u95f4")),
                (
                    "end_time",
                    models.DateTimeField(
                        default=datetime.datetime(1980, 1, 1, 8, 0, tzinfo=utc),
                        verbose_name="\u4e8b\u4ef6\u7ed3\u675f\u65f6\u95f4",
                    ),
                ),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="\u4e1a\u52a1ID", blank=True)),
                ("strategy_id", models.IntegerField(verbose_name="\u5173\u8054\u7b56\u7565ID")),
                (
                    "origin_alarm",
                    bkmonitor.utils.db.fields.JsonField(
                        default=None, verbose_name="\u539f\u59cb\u7684\u5f02\u5e38\u5185\u5bb9"
                    ),
                ),
                (
                    "origin_config",
                    bkmonitor.utils.db.fields.JsonField(
                        default=None, verbose_name="\u544a\u8b66\u7b56\u7565\u539f\u59cb\u914d\u7f6e"
                    ),
                ),
                (
                    "level",
                    models.IntegerField(
                        default=0,
                        verbose_name="\u7ea7\u522b",
                        choices=[(1, "\u81f4\u547d"), (2, "\u9884\u8b66"), (3, "\u63d0\u9192")],
                    ),
                ),
                (
                    "status",
                    bkmonitor.utils.db.fields.EventStatusField(
                        default="ABNORMAL",
                        verbose_name="\u72b6\u6001",
                        choices=[
                            ("RECOVERED", "\u5df2\u4fee\u590d"),
                            ("ABNORMAL", "\u5f02\u5e38\u4e2d"),
                            ("CLOSED", "\u5df2\u5173\u95ed"),
                        ],
                    ),
                ),
                ("is_ack", models.BooleanField(default=False, verbose_name="\u662f\u5426\u786e\u8ba4")),
                (
                    "p_event_id",
                    models.CharField(default="", max_length=255, verbose_name="\u7236\u4e8b\u4ef6ID", blank=True),
                ),
                (
                    "is_shielded",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u5904\u4e8e\u5c4f\u853d\u72b6\u6001"),
                ),
                (
                    "target_key",
                    models.CharField(
                        default="", max_length=128, verbose_name="\u76ee\u6807\u6807\u8bc6\u7b26", blank=True
                    ),
                ),
                ("notify_status", models.IntegerField(default=0, verbose_name="\u901a\u77e5\u72b6\u6001")),
            ],
            options={
                "db_table": "alarm_event",
                "verbose_name": "\u4e8b\u4ef6",
                "verbose_name_plural": "\u4e8b\u4ef6",
            },
        ),
        migrations.CreateModel(
            name="EventAction",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u64cd\u4f5c\u65f6\u95f4")),
                (
                    "username",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u64cd\u4f5c\u4eba", db_index=True, blank=True
                    ),
                ),
                (
                    "operate",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u64cd\u4f5c",
                        choices=[
                            ("ACK", "\u544a\u8b66\u786e\u8ba4"),
                            ("ANOMALY_NOTICE", "\u544a\u8b66\u901a\u77e5"),
                            ("RECOVERY_NOTICE", "\u6062\u590d\u901a\u77e5"),
                            ("CREATE", "\u89e6\u53d1\u544a\u8b66"),
                            ("CONVERGE", "\u544a\u8b66\u6536\u655b"),
                            ("RECOVER", "\u544a\u8b66\u6062\u590d"),
                            ("CLOSE", "\u544a\u8b66\u5173\u95ed"),
                            ("CREATE_ORDER", "\u751f\u6210\u5de5\u5355"),
                            ("MESSAGE_QUEUE", "\u6d88\u606f\u961f\u5217"),
                        ],
                    ),
                ),
                ("message", models.TextField(default="", verbose_name="\u4e8b\u4ef6\u786e\u8ba4\u8bc4\u8bba")),
                (
                    "extend_info",
                    bkmonitor.utils.db.fields.JsonField(default={}, verbose_name="\u62d3\u5c55\u4fe1\u606f"),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u64cd\u4f5c\u72b6\u6001",
                        choices=[
                            ("RUNNING", "\u8fd0\u884c\u4e2d"),
                            ("SUCCESS", "\u6210\u529f"),
                            ("PARTIAL_SUCCESS", "\u90e8\u5206\u6210\u529f"),
                            ("FAILED", "\u5931\u8d25"),
                            ("SHIELDED", "\u5c4f\u853d"),
                        ],
                    ),
                ),
                (
                    "event_id",
                    models.CharField(max_length=255, verbose_name="\u5173\u8054\u4e8b\u4ef6ID", db_index=True),
                ),
            ],
            options={
                "db_table": "alarm_event_action",
                "verbose_name": "\u4e8b\u4ef6\u52a8\u4f5c\u65e5\u5fd7",
                "verbose_name_plural": "\u4e8b\u4ef6\u52a8\u4f5c\u65e5\u5fd7",
            },
        ),
        migrations.CreateModel(
            name="EventStats",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                "db_table": "alarm_event_stats",
            },
        ),
        migrations.CreateModel(
            name="GlobalConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("key", models.CharField(unique=True, max_length=255, verbose_name="\u914d\u7f6e\u540d")),
                ("value", bkmonitor.utils.db.fields.JsonField(verbose_name="\u914d\u7f6e\u4fe1\u606f", blank=True)),
                ("create_at", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                ("update_at", models.DateTimeField(auto_now=True, verbose_name="\u66f4\u65b0\u65f6\u95f4")),
                ("description", models.TextField(default="", verbose_name="\u63cf\u8ff0")),
                (
                    "data_type",
                    models.CharField(
                        default="JSON",
                        max_length=32,
                        verbose_name="\u6570\u636e\u7c7b\u578b",
                        choices=[
                            ("Integer", "\u6574\u6570"),
                            ("Char", "\u5b57\u7b26\u4e32"),
                            ("Boolean", "\u5e03\u5c14\u503c"),
                            ("JSON", "JSON"),
                            ("List", "\u5217\u8868"),
                            ("Choice", "\u5355\u9009"),
                            ("MultipleChoice", "\u591a\u9009"),
                        ],
                    ),
                ),
                (
                    "options",
                    bkmonitor.utils.db.fields.JsonField(
                        default={}, verbose_name="\u5b57\u6bb5\u9009\u9879", blank=True
                    ),
                ),
                (
                    "is_advanced",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u4e3a\u9ad8\u7ea7\u9009\u9879"),
                ),
                (
                    "is_internal",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u4e3a\u5185\u7f6e\u914d\u7f6e"),
                ),
            ],
            options={
                "db_table": "global_setting",
                "verbose_name": "\u52a8\u6001\u914d\u7f6e\u4fe1\u606f",
            },
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("name", models.CharField(max_length=256, verbose_name="\u76d1\u63a7\u9879\u540d\u79f0")),
                ("metric_id", models.CharField(default="", max_length=128, verbose_name="\u6307\u6807ID")),
                (
                    "data_source_label",
                    models.CharField(max_length=255, verbose_name="\u6570\u636e\u6765\u6e90\u6807\u7b7e"),
                ),
                (
                    "data_type_label",
                    models.CharField(max_length=255, verbose_name="\u6570\u636e\u7c7b\u578b\u6807\u7b7e"),
                ),
                ("rt_query_config_id", models.IntegerField(verbose_name="\u67e5\u8be2\u914d\u7f6eID")),
                (
                    "no_data_config",
                    bkmonitor.utils.db.fields.JsonField(
                        default="", verbose_name="\u65e0\u6570\u636e\u914d\u7f6e", blank=True
                    ),
                ),
                ("strategy_id", models.IntegerField(verbose_name="\u5173\u8054\u7b56\u7565ID", db_index=True)),
            ],
            options={
                "db_table": "alarm_item",
                "verbose_name": "\u7b56\u7565\u76d1\u63a7\u9879\u914d\u7f6e",
                "verbose_name_plural": "\u7b56\u7565\u76d1\u63a7\u9879\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="NoticeGroup",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("name", models.CharField(max_length=128, verbose_name="\u901a\u77e5\u7ec4\u540d\u79f0")),
                ("bk_biz_id", models.IntegerField(default=0, db_index=True, verbose_name="\u4e1a\u52a1ID", blank=True)),
                ("notice_receiver", bkmonitor.utils.db.fields.JsonField(verbose_name="\u901a\u77e5\u5bf9\u8c61")),
                ("notice_way", bkmonitor.utils.db.fields.JsonField(verbose_name="\u901a\u77e5\u65b9\u5f0f")),
                ("message", models.TextField(verbose_name="\u8bf4\u660e/\u5907\u6ce8")),
                (
                    "source",
                    models.CharField(
                        default=bkmonitor.middlewares.source.get_source_app_code,
                        max_length=32,
                        verbose_name="\u6765\u6e90\u7cfb\u7edf",
                    ),
                ),
            ],
            options={
                "db_table": "alarm_notice_group",
                "verbose_name": "\u901a\u77e5\u7ec4\u914d\u7f6e",
                "verbose_name_plural": "\u901a\u77e5\u7ec4\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="NoticeTemplate",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("anomaly_template", models.TextField(default="", verbose_name="\u5f02\u5e38\u901a\u77e5\u6a21\u677f")),
                (
                    "recovery_template",
                    models.TextField(default="", verbose_name="\u6062\u590d\u901a\u77e5\u6a21\u677f"),
                ),
                ("action_id", models.IntegerField(verbose_name="\u5173\u8054\u52a8\u4f5cID", db_index=True)),
            ],
            options={
                "db_table": "alarm_notice_template",
                "verbose_name": "\u901a\u77e5\u6a21\u677f\u914d\u7f6e",
                "verbose_name_plural": "\u901a\u77e5\u6a21\u677f\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="ResultTableDSLConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("result_table_id", models.CharField(max_length=256, verbose_name="\u7ed3\u679c\u8868")),
                ("agg_method", models.CharField(max_length=64, verbose_name="\u805a\u5408\u65b9\u6cd5")),
                ("agg_interval", models.PositiveIntegerField(default=60, verbose_name="\u805a\u5408\u5468\u671f")),
                ("agg_dimension", bkmonitor.utils.db.fields.JsonField(verbose_name="\u805a\u5408\u7ef4\u5ea6")),
                ("agg_condition", bkmonitor.utils.db.fields.JsonField(verbose_name="\u76d1\u63a7\u6761\u4ef6")),
                ("keywords_query_string", models.TextField(verbose_name="\u5173\u952e\u5b57\u67e5\u8be2\u6761\u4ef6")),
                ("rule", models.CharField(max_length=256, verbose_name="\u7ec4\u5408\u65b9\u5f0f")),
                ("keywords", bkmonitor.utils.db.fields.JsonField(verbose_name="\u7ec4\u5408\u5b57\u6bb5")),
                ("extend_fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u6269\u5c55\u5b57\u6bb5")),
            ],
            options={
                "db_table": "alarm_rt_dsl_config",
                "verbose_name": "DSL\u7c7b\u7ed3\u679c\u8868\u67e5\u8be2\u914d\u7f6e",
                "verbose_name_plural": "DSL\u7c7b\u7ed3\u679c\u8868\u67e5\u8be2\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="ResultTableSQLConfig",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("result_table_id", models.CharField(max_length=256, verbose_name="\u7ed3\u679c\u8868")),
                ("agg_method", models.CharField(max_length=64, verbose_name="\u805a\u5408\u65b9\u6cd5")),
                ("agg_interval", models.PositiveIntegerField(default=60, verbose_name="\u805a\u5408\u5468\u671f")),
                ("agg_dimension", bkmonitor.utils.db.fields.JsonField(verbose_name="\u805a\u5408\u7ef4\u5ea6")),
                ("agg_condition", bkmonitor.utils.db.fields.JsonField(verbose_name="\u805a\u5408\u6761\u4ef6")),
                ("metric_field", models.CharField(max_length=256, verbose_name="\u5b57\u6bb5")),
                ("unit", models.CharField(default="", max_length=32, verbose_name="\u5355\u4f4d")),
                ("unit_conversion", models.FloatField(default=1.0, verbose_name="\u5355\u4f4d\u8f6c\u6362")),
                ("extend_fields", bkmonitor.utils.db.fields.JsonField(verbose_name="\u6269\u5c55\u5b57\u6bb5")),
            ],
            options={
                "db_table": "alarm_rt_sql_config",
                "verbose_name": "SQL\u7c7b\u7ed3\u679c\u8868\u67e5\u8be2\u914d\u7f6e",
                "verbose_name_plural": "SQL\u7c7b\u7ed3\u679c\u8868\u67e5\u8be2\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="Shield",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("bk_biz_id", models.IntegerField(default=0, db_index=True, verbose_name="\u4e1a\u52a1ID", blank=True)),
                (
                    "category",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u5c4f\u853d\u7c7b\u578b",
                        choices=[
                            ("scope", "\u8303\u56f4\u5c4f\u853d"),
                            ("strategy", "\u7b56\u7565\u5c4f\u853d"),
                            ("event", "\u4e8b\u4ef6\u5c4f\u853d"),
                        ],
                    ),
                ),
                (
                    "scope_type",
                    models.CharField(
                        max_length=32,
                        verbose_name="\u5c4f\u853d\u8303\u56f4\u7c7b\u578b",
                        choices=[
                            ("instance", "\u5b9e\u4f8b"),
                            ("ip", "IP"),
                            ("node", "\u8282\u70b9"),
                            ("biz", "\u4e1a\u52a1"),
                        ],
                    ),
                ),
                ("content", models.TextField(verbose_name="\u5c4f\u853d\u5185\u5bb9\u5feb\u7167")),
                ("begin_time", models.DateTimeField(verbose_name="\u5c4f\u853d\u5f00\u59cb\u65f6\u95f4")),
                ("end_time", models.DateTimeField(verbose_name="\u5c4f\u853d\u7ed3\u675f\u65f6\u95f4")),
                ("failure_time", models.DateTimeField(verbose_name="\u5c4f\u853d\u5931\u6548\u65f6\u95f4")),
                ("dimension_config", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5c4f\u853d\u7ef4\u5ea6")),
                ("cycle_config", bkmonitor.utils.db.fields.JsonField(verbose_name="\u5c4f\u853d\u5468\u671f")),
                ("notice_config", bkmonitor.utils.db.fields.JsonField(verbose_name="\u901a\u77e5\u914d\u7f6e")),
                ("description", models.TextField(verbose_name="\u5c4f\u853d\u539f\u56e0")),
                (
                    "is_quick",
                    models.BooleanField(default=False, verbose_name="\u662f\u5426\u662f\u5feb\u6377\u5c4f\u853d"),
                ),
                (
                    "source",
                    models.CharField(
                        default=bkmonitor.middlewares.source.get_source_app_code,
                        max_length=32,
                        verbose_name="\u6765\u6e90\u7cfb\u7edf",
                    ),
                ),
            ],
            options={
                "db_table": "alarm_shield",
                "verbose_name": "\u5c4f\u853d\u914d\u7f6e",
                "verbose_name_plural": "\u5c4f\u853d\u914d\u7f6e",
            },
        ),
        migrations.CreateModel(
            name="SnapshotHostIndex",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("category", models.CharField(max_length=32, verbose_name="category")),
                ("item", bkmonitor.utils.db.fields.ReadWithUnderscoreField(max_length=32, verbose_name="item")),
                ("type", models.CharField(max_length=32, verbose_name="type")),
                ("result_table_id", models.CharField(max_length=128, verbose_name="result table id")),
                ("description", models.CharField(max_length=50, verbose_name="description")),
                ("dimension_field", models.CharField(max_length=1024, verbose_name="dimension field")),
                ("conversion", models.FloatField(verbose_name="conversion")),
                ("conversion_unit", models.CharField(max_length=32, verbose_name="conversion unit")),
                (
                    "metric",
                    bkmonitor.utils.db.fields.ReadWithUnderscoreField(
                        max_length=128, null=True, verbose_name="metric", blank=True
                    ),
                ),
                ("is_linux", models.BooleanField(default=True, verbose_name="is liunx metric")),
                ("is_windows", models.BooleanField(default=True, verbose_name="is windows metric")),
                ("is_aix", models.BooleanField(default=True, verbose_name="is aix metric")),
            ],
            options={
                "db_table": "app_snapshot_host_index",
            },
        ),
        migrations.CreateModel(
            name="Strategy",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("is_enabled", models.BooleanField(default=True, verbose_name="\u662f\u5426\u542f\u7528")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="\u662f\u5426\u5220\u9664")),
                (
                    "create_user",
                    models.CharField(default="", max_length=32, verbose_name="\u521b\u5efa\u4eba", blank=True),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="\u521b\u5efa\u65f6\u95f4")),
                (
                    "update_user",
                    models.CharField(
                        default="", max_length=32, verbose_name="\u6700\u540e\u4fee\u6539\u4eba", blank=True
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(auto_now=True, verbose_name="\u6700\u540e\u4fee\u6539\u65f6\u95f4"),
                ),
                ("name", models.CharField(max_length=128, verbose_name="\u7b56\u7565\u540d\u79f0", db_index=True)),
                ("bk_biz_id", models.IntegerField(default=0, db_index=True, verbose_name="\u4e1a\u52a1ID", blank=True)),
                (
                    "source",
                    models.CharField(
                        default=bkmonitor.middlewares.source.get_source_app_code,
                        max_length=32,
                        verbose_name="\u6765\u6e90\u7cfb\u7edf",
                    ),
                ),
                ("scenario", models.CharField(max_length=64, verbose_name="\u76d1\u63a7\u573a\u666f", db_index=True)),
                (
                    "target",
                    bkmonitor.utils.db.fields.JsonField(
                        default="", verbose_name="\u76d1\u63a7\u76ee\u6807", blank=True
                    ),
                ),
            ],
            options={
                "db_table": "alarm_strategy",
                "verbose_name": "\u7b56\u7565\u914d\u7f6e",
                "verbose_name_plural": "\u7b56\u7565\u914d\u7f6e",
            },
        ),
        migrations.AlterIndexTogether(
            name="strategy",
            index_together={("bk_biz_id", "source")},
        ),
        migrations.AlterIndexTogether(
            name="shield",
            index_together={("bk_biz_id", "source"), ("begin_time", "bk_biz_id")},
        ),
        migrations.AlterIndexTogether(
            name="noticegroup",
            index_together={("bk_biz_id", "source")},
        ),
        migrations.AlterIndexTogether(
            name="item",
            index_together={("data_type_label", "data_source_label")},
        ),
        migrations.AlterIndexTogether(
            name="eventaction",
            index_together={("create_time", "operate")},
        ),
        migrations.AlterIndexTogether(
            name="event",
            index_together={
                ("target_key", "status", "end_time", "bk_biz_id", "level", "strategy_id"),
                ("end_time", "bk_biz_id", "status", "strategy_id", "notify_status"),
                ("level", "end_time", "bk_biz_id", "status", "strategy_id", "notify_status"),
                ("notify_status", "status", "end_time", "bk_biz_id", "level", "strategy_id"),
            },
        ),
    ]
