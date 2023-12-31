# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-05-20 02:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0098_bk_monitorv3_202205122214"),
    ]

    operations = [
        migrations.AlterField(
            model_name="actioninstance",
            name="real_status",
            field=models.CharField(
                choices=[
                    ("received", "收到"),
                    ("waiting", "审批中"),
                    ("converging", "收敛中"),
                    ("sleep", "收敛处理等待"),
                    ("converged", "收敛结束"),
                    ("running", "处理中"),
                    ("success", "成功"),
                    ("partial_success", "部分成功"),
                    ("failure", "失败"),
                    ("partial_failure", "部分失败"),
                    ("skipped", "跳过"),
                    ("shield", "已屏蔽"),
                ],
                default="",
                max_length=64,
                verbose_name="真实执行状态",
            ),
        ),
        migrations.AlterField(
            model_name="actioninstance",
            name="status",
            field=models.CharField(
                choices=[
                    ("received", "收到"),
                    ("waiting", "审批中"),
                    ("converging", "收敛中"),
                    ("sleep", "收敛处理等待"),
                    ("converged", "收敛结束"),
                    ("running", "处理中"),
                    ("success", "成功"),
                    ("partial_success", "部分成功"),
                    ("failure", "失败"),
                    ("partial_failure", "部分失败"),
                    ("skipped", "跳过"),
                    ("shield", "已屏蔽"),
                ],
                default="received",
                max_length=64,
                verbose_name="执行状态",
            ),
        ),
        migrations.AlterField(
            model_name="algorithmmodel",
            name="type",
            field=models.CharField(
                choices=[
                    ("Threshold", "静态阈值算法"),
                    ("SimpleRingRatio", "简易环比算法"),
                    ("AdvancedRingRatio", "高级环比算法"),
                    ("SimpleYearRound", "简易同比算法"),
                    ("AdvancedYearRound", "高级同比算法"),
                    ("PartialNodes", "部分节点数算法"),
                    ("OsRestart", "主机重启算法"),
                    ("ProcPort", "进程端口算法"),
                    ("PingUnreachable", "Ping不可达算法"),
                    ("YearRoundAmplitude", "同比振幅算法"),
                    ("YearRoundRange", "同比区间算法"),
                    ("RingRatioAmplitude", "环比振幅算法"),
                    ("IntelligentDetect", "智能异常检测算法"),
                    ("TimeSeriesForecasting", "时序预测算法"),
                ],
                db_index=True,
                max_length=64,
                verbose_name="算法类型",
            ),
        ),
        migrations.AlterField(
            model_name="bcscluster",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcscontainer",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcscontainerlabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="bcsmonitor",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcsmonitorlabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="bcsnode",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcsnode",
            name="endpoint_count",
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name="bcsnode",
            name="pod_count",
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name="bcsnodelabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="bcspod",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcspod",
            name="labels",
            field=models.ManyToManyField(blank=True, through="bkmonitor.BCSPodLabels", to="bkmonitor.BCSLabel"),
        ),
        migrations.AlterField(
            model_name="bcspod",
            name="restarts",
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name="bcspodlabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="bcsservice",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcsservice",
            name="endpoint_count",
            field=models.IntegerField(default=0, null=True),
        ),
        migrations.AlterField(
            model_name="bcsservice",
            name="pod_count",
            field=models.IntegerField(default=0, null=True),
        ),
        migrations.AlterField(
            model_name="bcsservicelabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="bcsworkload",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="bcsworkloadlabels",
            name="bcs_cluster_id",
            field=models.CharField(db_index=True, max_length=128, verbose_name="集群ID"),
        ),
        migrations.AlterField(
            model_name="eventplugin",
            name="scenario",
            field=models.CharField(
                choices=[("MONITOR", "监控工具"), ("REST_API", "Rest API"), ("EMAIL", "Email")],
                default="MONITOR",
                max_length=64,
                verbose_name="场景",
            ),
        ),
    ]
