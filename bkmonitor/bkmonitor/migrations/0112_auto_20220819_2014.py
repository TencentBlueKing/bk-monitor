# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-08-19 12:14
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0111_auto_20220725_1506"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventPluginInstance",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("plugin_id", models.CharField(db_index=True, max_length=64, verbose_name="插件ID")),
                ("version", models.CharField(db_index=True, max_length=64, verbose_name="插件版本号")),
                ("name", models.CharField(blank=True, default="", max_length=64, verbose_name="配置名称")),
                ("bk_biz_id", models.IntegerField(blank=True, db_index=True, default=0, verbose_name="业务ID")),
                ("data_id", models.IntegerField(default=0, verbose_name="数据ID")),
                (
                    "config_params",
                    models.JSONField(default=list, verbose_name="插件配置实例信息"),
                ),
                (
                    "ingest_config",
                    models.JSONField(default=dict, verbose_name="插件配置信息"),
                ),
                (
                    "normalization_config",
                    models.JSONField(default=list, verbose_name="字段清洗规则"),
                ),
            ],
            options={
                "verbose_name": "插件安装信息",
                "verbose_name_plural": "插件安装信息",
                "db_table": "event_plugin_instance",
            },
        ),
        migrations.CreateModel(
            name="EventPluginV2",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("plugin_id", models.CharField(db_index=True, max_length=64, verbose_name="插件ID")),
                ("version", models.CharField(db_index=True, max_length=64, verbose_name="版本号")),
                ("is_latest", models.BooleanField(default=False, verbose_name="是否最新版本")),
                ("plugin_display_name", models.CharField(blank=True, default="", max_length=64, verbose_name="插件别名")),
                (
                    "plugin_type",
                    models.CharField(
                        choices=[
                            ("http_push", "HTTP 推送"),
                            ("http_pull", "HTTP 拉取"),
                            ("email_pull", "Email 拉取"),
                            ("kafka_push", "kafka 推送"),
                        ],
                        db_index=True,
                        max_length=32,
                        verbose_name="插件类型",
                    ),
                ),
                ("summary", models.TextField(blank=True, default="", verbose_name="概述")),
                ("author", models.CharField(blank=True, default="", max_length=64, verbose_name="作者")),
                ("description", models.TextField(blank=True, default="", verbose_name="详细描述，markdown文本")),
                ("tutorial", models.TextField(blank=True, default="", verbose_name="配置向导，markdown文本")),
                ("logo", models.ImageField(null=True, upload_to="", verbose_name="logo文件")),
                ("package_dir", models.TextField(blank=True, default="", verbose_name="包路径")),
                ("bk_biz_id", models.IntegerField(blank=True, db_index=True, default=0, verbose_name="业务ID")),
                ("tags", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="插件标签")),
                (
                    "scenario",
                    models.CharField(
                        choices=[("MONITOR", "监控工具"), ("REST_API", "Rest API"), ("EMAIL", "电子邮件"), ("KAFKA", "Kafka")],
                        default="MONITOR",
                        max_length=64,
                        verbose_name="场景",
                    ),
                ),
                ("popularity", models.IntegerField(default=0, verbose_name="热度")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ('NO_DATA', '无数据'),
                            ('REMOVE_SOON', '将下架'),
                            ('REMOVED', '已下架'),
                            ('DISABLED', '已停用'),
                            ('AVAILABLE', '可用'),
                            ('DEBUG', '调试中'),
                        ],
                        default='AVAILABLE',
                        max_length=32,
                        verbose_name='状态',
                    ),
                ),
                (
                    "config_params",
                    models.JSONField(default=list, verbose_name="插件配置实例信息"),
                ),
                (
                    "ingest_config",
                    models.JSONField(default=dict, verbose_name="接入配置"),
                ),
                (
                    "normalization_config",
                    models.JSONField(default=list, verbose_name="字段清洗规则"),
                ),
            ],
            options={
                "verbose_name": "插件信息V2",
                "verbose_name_plural": "插件信息V2",
                "db_table": "event_plugin",
            },
        ),
        migrations.AddField(
            model_name="alertconfig",
            name="plugin_instance_id",
            field=models.IntegerField(default=0, verbose_name="插件实例ID"),
        ),
        migrations.AlterField(
            model_name="eventplugin",
            name="plugin_type",
            field=models.CharField(
                choices=[
                    ("http_push", "HTTP 推送"),
                    ("http_pull", "HTTP 拉取"),
                    ("email_pull", "Email 拉取"),
                    ("kafka_push", "kafka 推送"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="插件类型",
            ),
        ),
        migrations.AlterField(
            model_name="eventplugin",
            name="scenario",
            field=models.CharField(
                choices=[("MONITOR", "监控工具"), ("REST_API", "Rest API"), ("EMAIL", "电子邮件"), ("KAFKA", "Kafka")],
                default="MONITOR",
                max_length=64,
                verbose_name="场景",
            ),
        ),
        migrations.AlterField(
            model_name="eventplugin",
            name="status",
            field=models.CharField(
                choices=[
                    ('NO_DATA', '无数据'),
                    ('REMOVE_SOON', '将下架'),
                    ('REMOVED', '已下架'),
                    ('DISABLED', '已停用'),
                    ('AVAILABLE', '可用'),
                    ('DEBUG', '调试中'),
                ],
                default='AVAILABLE',
                max_length=32,
                verbose_name='状态',
            ),
        ),
        migrations.AlterUniqueTogether(
            name="eventpluginv2",
            unique_together={("plugin_id", "version")},
        ),
    ]
