# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-09-13 12:02
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bkmonitor', '0111_auto_20220725_1506'),
    ]

    operations = [
        migrations.CreateModel(
            name='BCSPodMonitor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bk_biz_id', models.IntegerField(db_index=True, default=0, verbose_name='业务ID')),
                ('bcs_cluster_id', models.CharField(db_index=True, max_length=32)),
                ('created_at', models.DateTimeField()),
                ('deleted_at', models.DateTimeField(null=True)),
                ('status', models.CharField(db_index=True, default='', max_length=32)),
                ('monitor_status', models.CharField(default='', max_length=32)),
                ('last_synced_at', models.DateTimeField(verbose_name='同步时间')),
                ('unique_hash', models.CharField(max_length=32, null=True, unique=True)),
                ('name', models.CharField(max_length=128)),
                ('namespace', models.CharField(max_length=128)),
                ('endpoints', models.CharField(max_length=32)),
                ('metric_path', models.CharField(max_length=32)),
                ('metric_port', models.CharField(max_length=32)),
                ('metric_interval', models.CharField(max_length=8)),
            ],
        ),
        migrations.CreateModel(
            name='BCSPodMonitorLabels',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bcs_cluster_id', models.CharField(db_index=True, max_length=128, verbose_name='集群ID')),
                (
                    'label',
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='bkmonitor.BCSLabel'
                    ),
                ),
                (
                    'resource',
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='bkmonitor.BCSPodMonitor'
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='bcspodmonitor',
            name='labels',
            field=models.ManyToManyField(through='bkmonitor.BCSPodMonitorLabels', to='bkmonitor.BCSLabel'),
        ),
        migrations.AlterIndexTogether(
            name='bcspodmonitor',
            index_together={('bk_biz_id', 'bcs_cluster_id')},
        ),
    ]
