# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-05-22 03:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('metadata', '0154_auto_20230519_1738'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessVMRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'data_type',
                    models.CharField(
                        choices=[
                            ('bcs_cluster_k8s', 'BCS 集群k8s指标'),
                            ('bcs_cluster_custom', 'BCS 集群自定义指标'),
                            ('user_custom', '用户自定义指标'),
                        ],
                        default='bcs_cluster_k8s',
                        max_length=32,
                        verbose_name='数据类型',
                    ),
                ),
                ('result_table_id', models.CharField(help_text='结果表ID', max_length=64, verbose_name='结果表ID')),
                (
                    'bcs_cluster_id',
                    models.CharField(blank=True, help_text='bcs集群ID', max_length=32, null=True, verbose_name='bcs集群ID'),
                ),
                (
                    'storage_cluster_id',
                    models.IntegerField(blank=True, help_text='对接使用的集群ID', null=True, verbose_name='对接使用的storage域名'),
                ),
                ('vm_cluster_id', models.IntegerField(help_text='vm 对应的集群ID', verbose_name='集群ID')),
                ('bk_base_data_id', models.IntegerField(help_text='数据平台的data_id', verbose_name='数据平台的data_id')),
                ('vm_result_table_id', models.CharField(help_text='VM 结果表rt', max_length=64, verbose_name='VM 结果表rt')),
                (
                    'remark',
                    models.CharField(blank=True, help_text='接入备注', max_length=256, null=True, verbose_name='接入备注'),
                ),
            ],
            options={
                'verbose_name': '接入VM记录表',
                'verbose_name_plural': '接入VM记录表',
            },
        ),
    ]
