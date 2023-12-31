# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-07-06 04:31
from __future__ import unicode_literals

import functools
import secrets

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0108_bk_monitorv3_202207051730"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiAuthToken",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("name", models.CharField(max_length=64, unique=True, verbose_name="令牌名称")),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        default=functools.partial(secrets.token_hex, *(16,), **{}),
                        max_length=32,
                        unique=True,
                        verbose_name="鉴权令牌",
                    ),
                ),
                ("namespaces", models.JSONField(default=list, verbose_name="所属命名空间")),
                (
                    "type",
                    models.CharField(
                        choices=[("as_code", "AsCode"), ("grafana", "Grafana")], max_length=32, verbose_name="鉴权类型"
                    ),
                ),
            ],
            options={
                "verbose_name": "API鉴权令牌",
                "verbose_name_plural": "API鉴权令牌",
                "db_table": "api_auth_token",
            },
        ),
        migrations.AddField(
            model_name="actionconfig",
            name="app",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="所属应用"),
        ),
        migrations.AddField(
            model_name="actionconfig",
            name="hash",
            field=models.CharField(blank=True, default="", max_length=64, null=True, verbose_name="原始配置摘要"),
        ),
        migrations.AddField(
            model_name="actionconfig",
            name="path",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="资源路径"),
        ),
        migrations.AddField(
            model_name="actionconfig",
            name="snippet",
            field=models.TextField(blank=True, default="", null=True, verbose_name="配置片段"),
        ),
        migrations.AddField(
            model_name="strategymodel",
            name="app",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="所属应用"),
        ),
        migrations.AddField(
            model_name="strategymodel",
            name="hash",
            field=models.CharField(blank=True, default="", max_length=64, null=True, verbose_name="原始配置摘要"),
        ),
        migrations.AddField(
            model_name="strategymodel",
            name="path",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="资源路径"),
        ),
        migrations.AddField(
            model_name="strategymodel",
            name="snippet",
            field=models.TextField(blank=True, default="", null=True, verbose_name="配置片段"),
        ),
        migrations.AddField(
            model_name="usergroup",
            name="app",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="所属应用"),
        ),
        migrations.AddField(
            model_name="usergroup",
            name="hash",
            field=models.CharField(blank=True, default="", max_length=64, null=True, verbose_name="原始配置摘要"),
        ),
        migrations.AddField(
            model_name="usergroup",
            name="path",
            field=models.CharField(blank=True, default="", max_length=128, null=True, verbose_name="资源路径"),
        ),
        migrations.AddField(
            model_name="usergroup",
            name="snippet",
            field=models.TextField(blank=True, default="", null=True, verbose_name="配置片段"),
        ),
    ]
