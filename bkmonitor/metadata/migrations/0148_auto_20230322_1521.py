# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-03-22 07:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('metadata', '0147_merge_20230302_1756'),
    ]

    operations = [
        migrations.AlterField(
            model_name='space',
            name='space_name',
            field=models.CharField(help_text='空间类型下唯一', max_length=256, verbose_name='空间中文名称'),
        ),
    ]
