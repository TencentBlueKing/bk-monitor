# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-06-20 06:50
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('metadata', '0161_merge_20230615_1932'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomReportSubscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bk_biz_id', models.IntegerField(verbose_name='业务ID')),
                ('subscription_id', models.IntegerField(default=0, verbose_name='节点管理订阅ID')),
                ('bk_data_id', models.IntegerField(default=0, verbose_name='数据ID')),
                ('config', bkmonitor.utils.db.fields.JsonField(verbose_name='订阅配置')),
            ],
            options={
                'verbose_name': '自定义上报订阅配置v2',
                'verbose_name_plural': '自定义上报订阅配置v2',
            },
        ),
        migrations.AlterUniqueTogether(
            name='customreportsubscription',
            unique_together={('bk_biz_id', 'bk_data_id')},
        ),
    ]
