# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-03-21 08:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('metadata', '0147_merge_20230302_1756'),
    ]

    operations = [
        migrations.AddField(
            model_name='pingserversubscriptionconfig',
            name='bk_host_id',
            field=models.IntegerField(default=None, null=True, verbose_name='主机ID'),
        )
    ]
