# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-01-09 11:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apm", "0018_tupdate_metric_dimensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="datalink",
            name="influxdb_cluster_name",
            field=models.CharField(default="", max_length=128, verbose_name="时序数据存储的influxdb集群名称"),
        ),
    ]
