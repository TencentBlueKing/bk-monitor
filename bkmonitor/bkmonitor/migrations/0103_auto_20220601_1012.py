# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-06-01 02:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0102_auto_20220525_1220"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bcscluster",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcscontainer",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcsmonitor",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcsnode",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcspod",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcsservice",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="bcsworkload",
            name="unique_hash",
            field=models.CharField(max_length=32, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="strategymodel",
            name="invalid_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", ""),
                    ("invalid_related_strategy", "关联的策略已失效"),
                    ("deleted_related_strategy", "关联的策略已删除"),
                    ("invalid_unit", "指标和检测算法的单位类型不一致"),
                    ("invalid_target", "监控目标全部失效"),
                    ("invalid_metric", "监控指标不存在"),
                    ("invalid_biz", "策略所属业务不存在"),
                ],
                default="",
                max_length=32,
                verbose_name="失效类型",
            ),
        ),
    ]
