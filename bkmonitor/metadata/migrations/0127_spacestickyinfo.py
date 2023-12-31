# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-08-14 15:14
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0126_auto_20220809_1435"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpaceStickyInfo",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("space_uid_list", bkmonitor.utils.db.fields.JsonField(default=[], verbose_name="置顶空间uid列表")),
                ("username", models.CharField(db_index=True, max_length=64, verbose_name="用户名")),
            ],
        ),
    ]
