# Generated by Django 3.2.15 on 2023-12-19 12:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0031_auto_20230829_1416"),
    ]

    operations = [
        migrations.CreateModel(
            name="BkdataFlowConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="监控业务id")),
                ("app_name", models.CharField(max_length=50, verbose_name="应用名称")),
                ("is_finished", models.BooleanField(default=False, verbose_name="是否已配置完成")),
                ("finished_time", models.DateTimeField(null=True, verbose_name="配置完成时间")),
                ("project_id", models.CharField(max_length=128, null=True, verbose_name="project id")),
                ("deploy_bk_biz_id", models.IntegerField(verbose_name="计算平台数据源所在的业务ID")),
                ("deploy_data_id", models.CharField(max_length=128, null=True, verbose_name="数据源dataid")),
                ("deploy_config", models.JSONField(null=True, verbose_name="数据源配置")),
                ("databus_clean_id", models.CharField(max_length=128, null=True, verbose_name="清洗配置ID")),
                ("databus_clean_config", models.JSONField(null=True, verbose_name="清洗配置")),
                (
                    "databus_clean_result_table_id",
                    models.CharField(max_length=128, null=True, verbose_name="清洗输出结果表ID"),
                ),
                ("flow_id", models.CharField(max_length=128, null=True, verbose_name="dataflow id")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("config_deploy_failed", "数据源配置失败"),
                            ("config_cleans_failed", "清洗配置失败"),
                            ("config_cleans_start_failed", "清洗启动失败"),
                            ("auth_failed", "项目授权失败"),
                            ("config_flow_failed", "Flow配置失败"),
                            ("success", "启动完成"),
                        ],
                        max_length=64,
                        null=True,
                        verbose_name="配置状态",
                    ),
                ),
                ("process_info", models.JSONField(null=True, verbose_name="执行日志")),
                ("last_process_time", models.DateTimeField(null=True, verbose_name="上次执行时间")),
                (
                    "flow_type",
                    models.CharField(choices=[("tail_sampling", "尾部采样Flow")], max_length=32, verbose_name="Flow类型"),
                ),
                ("create_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "APM Flow管理表",
            },
        ),
        migrations.AlterField(
            model_name="normaltypevalueconfig",
            name="type",
            field=models.CharField(
                choices=[
                    ("metrics_batch_size", "每批Metric发送大小"),
                    ("traces_batch_size", "每批Trace发送大小"),
                    ("logs_batch_size", "每批Log发送大小"),
                    ("db_slow_command_config", "db慢命令配置"),
                    ("db_config", "db配置"),
                ],
                max_length=32,
                verbose_name="配置类型",
            ),
        ),
    ]
