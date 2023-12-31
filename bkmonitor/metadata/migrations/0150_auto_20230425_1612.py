# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-04-25 08:12
from __future__ import unicode_literals

from django.db import migrations, models

import metadata.models.influxdb_cluster


class Migration(migrations.Migration):

    dependencies = [
        ('metadata', '0149_auto_20230424_1502'),
    ]

    operations = [
        migrations.CreateModel(
            name='InfluxDBProxyStorage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creator', models.CharField(max_length=64, verbose_name='创建者')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updater', models.CharField(max_length=64, verbose_name='更新者')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('proxy_cluster_id', models.IntegerField(verbose_name='influxdb proxy 集群 ID')),
                ('service_name', models.CharField(max_length=64, verbose_name='influxdb proxy 服务名称')),
                ('instance_cluster_name', models.CharField(max_length=128, verbose_name='实际存储集群名称')),
                (
                    'is_default',
                    models.BooleanField(default=False, help_text='是否为默认存储，当用户未指定时，使用默认值', verbose_name='是否默认'),
                ),
            ],
            options={
                'verbose_name': 'InfluxDB Proxy 集群和实际存储集群关系表',
                'verbose_name_plural': 'InfluxDB Proxy 集群和实际存储集群关系表',
            },
            bases=(models.Model, metadata.models.influxdb_cluster.InfluxDBTool),
        ),
        migrations.AddField(
            model_name='influxdbstorage',
            name='influxdb_proxy_storage_id',
            field=models.IntegerField(
                blank=True,
                help_text='设置influxdb proxy 和 后端存储集群的关联关系记录 ID, 用以查询结果表使用的 proxy 和后端存储',
                null=True,
                verbose_name='influxdb proxy 和 存储的关联关系 ID',
            ),
        ),
        migrations.AlterField(
            model_name='space',
            name='space_name',
            field=models.CharField(help_text='空间类型下唯一', max_length=256, verbose_name='空间中文名称'),
        ),
        migrations.AlterUniqueTogether(
            name='influxdbproxystorage',
            unique_together={('proxy_cluster_id', 'instance_cluster_name')},
        ),
        migrations.RunSQL("alter table metadata_space modify space_name varchar(256) not null collate utf8_bin;"),
    ]
