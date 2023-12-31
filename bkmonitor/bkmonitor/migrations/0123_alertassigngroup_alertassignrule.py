# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-12-05 07:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bkmonitor', '0122_merge_20221117_1912'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertAssignGroup',
            fields=[
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('create_user', models.CharField(blank=True, default='', max_length=32, verbose_name='创建人')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_user', models.CharField(blank=True, default='', max_length=32, verbose_name='最后修改人')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='最后修改时间')),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('priority', models.IntegerField(db_index=True, default=-1, verbose_name='优先级')),
                ('name', models.CharField(max_length=128, verbose_name='规则组名')),
                ('bk_biz_id', models.IntegerField(blank=True, db_index=True, default=0, verbose_name='业务ID')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='是否启用')),
            ],
            options={
                'verbose_name': '告警分派规则组',
                'verbose_name_plural': '告警分派规则组',
            },
        ),
        migrations.CreateModel(
            name='AlertAssignRule',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('assign_group_id', models.BigIntegerField(db_index=True, verbose_name='关联组')),
                ('bk_biz_id', models.IntegerField(blank=True, db_index=True, default=0, verbose_name='业务ID')),
                ('event_source', models.JSONField(default=list, verbose_name='告警来源')),
                ('scenario', models.JSONField(default=list, verbose_name='监控对象')),
                ('user_groups', models.JSONField(default=list, verbose_name='用户组')),
                ('conditions', models.JSONField(default=list, verbose_name='条件组')),
                ('actions', models.JSONField(default=list, verbose_name='处理事件')),
                ('is_enabled', models.BooleanField(default=False, verbose_name='是否启用')),
                (
                    'alert_severity',
                    models.IntegerField(
                        choices=[(1, '致命'), (2, '预警'), (3, '提醒'), (0, '保持')], default=0, verbose_name='告警级别'
                    ),
                ),
                ('additional_tags', models.JSONField(default=list, verbose_name='标签')),
            ],
        ),
    ]
