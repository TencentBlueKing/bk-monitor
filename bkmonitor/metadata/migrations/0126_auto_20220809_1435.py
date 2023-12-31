# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-08-09 06:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0125_merge_20220726_2048"),
    ]

    operations = [
        migrations.AddField(
            model_name="space",
            name="language",
            field=models.CharField(default="zh-hans", help_text="使用的语言", max_length=16, verbose_name="默认语言"),
        ),
        migrations.AddField(
            model_name="space",
            name="time_zone",
            field=models.CharField(
                default="Asia/Shanghai", help_text="时区，默认为Asia/Shanghai", max_length=32, verbose_name="时区"
            ),
        ),
        migrations.AlterField(
            model_name="resulttableoption",
            name="name",
            field=models.CharField(
                choices=[
                    ("cmdb_level_config", "cmdb_level_config"),
                    ("es_unique_field_list", "es_unique_field_list"),
                    ("group_info_alias", "group_info_alias"),
                    ("dimensions_values", "dimensions_values"),
                    ("segmented_query_enable", "分段查询开关"),
                ],
                max_length=128,
                verbose_name="option名称",
            ),
        ),
    ]
