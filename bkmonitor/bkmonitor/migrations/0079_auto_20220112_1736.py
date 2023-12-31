# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-01-12 09:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0078_auto_20220105_1739"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dutyarrange",
            name="duty_type",
            field=models.CharField(
                choices=[("daily", "每天"), ("always", "每天"), ("weekly", "每周"), ("monthly", "每月")],
                default="daily",
                max_length=32,
                verbose_name="值班类型",
            ),
        ),
    ]
