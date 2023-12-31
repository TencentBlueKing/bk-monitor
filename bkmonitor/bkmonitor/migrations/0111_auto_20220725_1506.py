# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-07-25 07:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0110_auto_20220722_1436"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemmodel",
            name="functions",
            field=models.JSONField(default=list, verbose_name="计算函数"),
        ),
        migrations.AlterField(
            model_name="eventplugin",
            name="scenario",
            field=models.CharField(
                choices=[("MONITOR", "监控工具"), ("REST_API", "Rest API"), ("EMAIL", "Email")],
                default="MONITOR",
                max_length=64,
                verbose_name="场景",
            ),
        ),
    ]
