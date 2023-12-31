# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-04-12 10:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bkmonitor', '0131_merge_20230410_1619'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertassigngroup',
            name='is_builtin',
            field=models.BooleanField(default=False, verbose_name='是否内置'),
        ),
        migrations.AlterField(
            model_name='actioninstance',
            name='signal',
            field=models.CharField(
                choices=[
                    ('manual', '手动处理时'),
                    ('abnormal', '告警触发时'),
                    ('recovered', '告警恢复时'),
                    ('closed', '告警关闭时'),
                    ('ack', '告警确认时'),
                    ('no_data', '无数据时'),
                    ('collect', '汇总'),
                    ('execute', '执行动作时'),
                    ('execute_success', '执行成功时'),
                    ('execute_failed', '执行失败时'),
                    ('demo', '调试时'),
                    ('unshielded', '解除屏蔽时'),
                    ('upgrade', '告警升级'),
                ],
                help_text='触发该事件的告警信号，如告警异常，告警恢复，告警关闭等',
                max_length=64,
                verbose_name='触发信号',
            ),
        ),
    ]
