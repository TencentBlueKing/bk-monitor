# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2021-11-30 06:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0073_merge_20211123_1526"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionconfig",
            name="is_builtin",
            field=models.BooleanField(default=False, verbose_name="是否内置"),
        ),
    ]
