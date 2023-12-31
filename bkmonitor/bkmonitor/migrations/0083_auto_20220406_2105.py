# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-04-06 13:05
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0082_merge_20220329_1634"),
    ]

    operations = [
        migrations.CreateModel(
            name="BCSCluster",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("area_name", models.CharField(max_length=32, verbose_name="区域")),
                ("project_name", models.CharField(max_length=32, verbose_name="业务名")),
                ("environment", models.CharField(max_length=32, verbose_name="环境")),
                ("updated_at", models.DateTimeField(verbose_name="更新时间")),
                ("node_count", models.IntegerField(verbose_name="节点数")),
                ("cpu_usage_ratio", models.FloatField(verbose_name="CPU使用率")),
                ("memory_usage_ratio", models.FloatField(verbose_name="内存使用率")),
                ("disk_usage_ratio", models.FloatField(verbose_name="磁盘使用率")),
                ("data_source", models.CharField(default="api", max_length=32, verbose_name="数据来源")),
                ("gray_status", models.BooleanField(default=False, verbose_name="BCS集群灰度接入蓝鲸监控")),
                (
                    "bcs_monitor_data_source",
                    models.CharField(default="prometheus", max_length=32, verbose_name="bcs监控数据源"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BCSContainer",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("resource_requests_cpu", models.IntegerField()),
                ("resource_requests_memory", models.BigIntegerField()),
                ("resource_limits_cpu", models.IntegerField()),
                ("resource_limits_memory", models.BigIntegerField()),
                ("name", models.CharField(max_length=128, verbose_name="名称")),
                ("namespace", models.CharField(max_length=128)),
                ("pod_name", models.CharField(max_length=128)),
                ("workload_type", models.CharField(max_length=32)),
                ("workload_name", models.CharField(max_length=128)),
                ("node_ip", models.CharField(max_length=16, null=True)),
                ("node_name", models.CharField(max_length=128)),
                ("image", models.CharField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name="BCSContainerLabels",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bcs_cluster_id", models.CharField(max_length=128, verbose_name="集群ID")),
            ],
        ),
        migrations.CreateModel(
            name="BCSLabel",
            fields=[
                ("hash_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=127)),
                ("value", models.CharField(max_length=127)),
            ],
        ),
        migrations.CreateModel(
            name="BCSNode",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("name", models.CharField(max_length=128)),
                ("roles", models.CharField(max_length=128, null=True)),
                ("cloud_id", models.CharField(max_length=32)),
                ("ip", models.CharField(max_length=32)),
                ("endpoint_count", models.IntegerField(max_length=32)),
                ("pod_count", models.IntegerField(max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name="BCSNodeLabels",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bcs_cluster_id", models.CharField(max_length=128, verbose_name="集群ID")),
                (
                    "label",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSLabel"
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSNode"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BCSPod",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("resource_requests_cpu", models.IntegerField()),
                ("resource_requests_memory", models.BigIntegerField()),
                ("resource_limits_cpu", models.IntegerField()),
                ("resource_limits_memory", models.BigIntegerField()),
                ("name", models.CharField(max_length=128)),
                ("namespace", models.CharField(max_length=128)),
                ("node_name", models.CharField(max_length=128)),
                ("node_ip", models.CharField(max_length=16, null=True)),
                ("workload_type", models.CharField(max_length=128)),
                ("workload_name", models.CharField(max_length=128)),
                ("total_container_count", models.IntegerField()),
                ("ready_container_count", models.IntegerField()),
                ("pod_ip", models.CharField(max_length=16, null=True)),
                ("images", models.TextField()),
                ("restarts", models.IntegerField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name="BCSPodLabels",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bcs_cluster_id", models.CharField(max_length=128, verbose_name="集群ID")),
                (
                    "label",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSLabel"
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSPod"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BCSService",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("name", models.CharField(max_length=128)),
                ("namespace", models.CharField(max_length=128)),
                ("type", models.CharField(max_length=32)),
                ("cluster_ip", models.CharField(max_length=32)),
                ("external_ip", models.CharField(max_length=32)),
                ("ports", models.TextField()),
                ("endpoint_count", models.IntegerField(default=0, max_length=128, null=True)),
                ("pod_count", models.IntegerField(default=0, max_length=128, null=True)),
                ("pod_name_list", models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name="BCSServiceLabels",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bcs_cluster_id", models.CharField(max_length=128, verbose_name="集群ID")),
                (
                    "label",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSLabel"
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSService"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BCSWorkload",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(default=0, verbose_name="业务ID")),
                ("bcs_cluster_id", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField()),
                ("deleted_at", models.DateTimeField(null=True)),
                ("status", models.CharField(default="", max_length=32)),
                ("monitor_status", models.CharField(default="", max_length=32)),
                ("last_synced_at", models.DateTimeField(verbose_name="同步时间")),
                ("unique_hash", models.CharField(max_length=32, null=True)),
                ("values_hash", models.CharField(max_length=32, null=True)),
                ("type", models.CharField(max_length=128)),
                ("name", models.CharField(max_length=128)),
                ("namespace", models.CharField(max_length=128)),
                ("pod_name_list", models.TextField()),
                ("images", models.TextField()),
                ("pod_count", models.IntegerField()),
                ("resource_requests_cpu", models.IntegerField()),
                ("resource_requests_memory", models.BigIntegerField()),
                ("resource_limits_cpu", models.IntegerField()),
                ("resource_limits_memory", models.BigIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="BCSWorkloadLabels",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bcs_cluster_id", models.CharField(max_length=128, verbose_name="集群ID")),
                (
                    "label",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSLabel"
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSWorkload"
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="shield",
            name="category",
            field=models.CharField(
                choices=[
                    ("scope", "范围屏蔽"),
                    ("strategy", "策略屏蔽"),
                    ("event", "事件屏蔽"),
                    ("alert", "告警屏蔽"),
                    ("dimension", "维度屏蔽"),
                ],
                max_length=32,
                verbose_name="屏蔽类型",
            ),
        ),
        migrations.AddField(
            model_name="bcsworkload",
            name="labels",
            field=models.ManyToManyField(through="bkmonitor.BCSWorkloadLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AddField(
            model_name="bcsservice",
            name="labels",
            field=models.ManyToManyField(through="bkmonitor.BCSServiceLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AddField(
            model_name="bcspod",
            name="labels",
            field=models.ManyToManyField(through="bkmonitor.BCSPodLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AddField(
            model_name="bcsnode",
            name="labels",
            field=models.ManyToManyField(through="bkmonitor.BCSNodeLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AlterUniqueTogether(
            name="bcslabel",
            unique_together={("key", "value")},
        ),
        migrations.AddField(
            model_name="bcscontainerlabels",
            name="label",
            field=models.ForeignKey(
                db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSLabel"
            ),
        ),
        migrations.AddField(
            model_name="bcscontainerlabels",
            name="resource",
            field=models.ForeignKey(
                db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to="bkmonitor.BCSContainer"
            ),
        ),
        migrations.AddField(
            model_name="bcscontainer",
            name="labels",
            field=models.ManyToManyField(through="bkmonitor.BCSContainerLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AlterUniqueTogether(
            name="bcsworkload",
            unique_together={("bcs_cluster_id", "namespace", "type", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="bcsservice",
            unique_together={("bcs_cluster_id", "namespace", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="bcspod",
            unique_together={("bcs_cluster_id", "namespace", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="bcsnode",
            unique_together={("bcs_cluster_id", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="bcscontainer",
            unique_together={("bcs_cluster_id", "namespace", "pod_name", "name")},
        ),
    ]
