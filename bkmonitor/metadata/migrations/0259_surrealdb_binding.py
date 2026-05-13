# Generated manually for PR #10383 SurrealDB binding schema changes

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0258_addindex_timeseriesmetric"),
    ]

    operations = [
        migrations.CreateModel(
            name="SurrealDBBindingConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "namespace",
                    models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间"),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
                ("status", models.CharField(max_length=64, verbose_name="状态")),
                ("data_link_name", models.CharField(blank=True, max_length=64, verbose_name="数据链路名称")),
                ("bk_biz_id", models.BigIntegerField(verbose_name="业务ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("name", models.CharField(db_index=True, max_length=64, verbose_name="绑定配置名称")),
                ("surrealdb_cluster_name", models.CharField(max_length=64, verbose_name="SurrealDB 集群名称")),
                ("table_id", models.CharField(blank=True, default="", max_length=255, verbose_name="结果表ID")),
                ("bkbase_result_table_name", models.CharField(default="", max_length=255, verbose_name="BKBase结果表名称")),
                ("table_type", models.CharField(default="temporary", max_length=32, verbose_name="图表类型")),
                ("vertices", models.JSONField(default=list, verbose_name="顶点定义")),
                ("relations", models.JSONField(default=list, verbose_name="关系定义")),
            ],
            options={
                "verbose_name": "SurrealDB绑定配置",
                "verbose_name_plural": "SurrealDB绑定配置",
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
        migrations.CreateModel(
            name="GraphRelationBindingConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "namespace",
                    models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间"),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
                ("status", models.CharField(max_length=64, verbose_name="状态")),
                ("data_link_name", models.CharField(blank=True, max_length=64, verbose_name="数据链路名称")),
                ("bk_biz_id", models.BigIntegerField(verbose_name="业务ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("name", models.CharField(db_index=True, max_length=64, verbose_name="图关系绑定配置名称")),
                (
                    "write_mode",
                    models.CharField(
                        choices=[
                            ("vm", "VM"),
                            ("surrealdb", "SurrealDB"),
                            ("vm_and_surrealdb", "VM + SurrealDB"),
                        ],
                        default="vm_and_surrealdb",
                        max_length=32,
                        verbose_name="写入模式",
                    ),
                ),
                ("vm_cluster_name", models.CharField(blank=True, default="", max_length=64, verbose_name="VM集群名称")),
                (
                    "surrealdb_cluster_name",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="SurrealDB集群名称"),
                ),
                ("table_id", models.CharField(blank=True, default="", max_length=255, verbose_name="结果表ID")),
                ("bkbase_result_table_name", models.CharField(default="", max_length=255, verbose_name="BKBase结果表名称")),
                ("graph_result_table_name", models.CharField(default="", max_length=255, verbose_name="图BKBase结果表名称")),
                ("table_type", models.CharField(default="temporary", max_length=32, verbose_name="图表类型")),
                ("vertices", models.JSONField(default=list, verbose_name="顶点定义")),
                ("relations", models.JSONField(default=list, verbose_name="关系定义")),
            ],
            options={
                "verbose_name": "图关系绑定配置",
                "verbose_name_plural": "图关系绑定配置",
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
        migrations.CreateModel(
            name="SurrealDBStorage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("table_id", models.CharField(max_length=128, verbose_name="结果表ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("table_type", models.CharField(default="temporary", max_length=32, verbose_name="图表类型")),
                ("vertices", models.JSONField(default=list, verbose_name="顶点定义")),
                ("relations", models.JSONField(default=list, verbose_name="关系定义")),
                ("storage_cluster_id", models.IntegerField(verbose_name="存储集群")),
            ],
            options={
                "verbose_name": "SurrealDB存储表",
                "verbose_name_plural": "SurrealDB存储表",
                "unique_together": {("table_id", "bk_tenant_id")},
            },
        ),
        migrations.AlterField(
            model_name="clusterinfo",
            name="cluster_type",
            field=models.CharField(
                choices=[
                    ("influxdb", "influxDB"),
                    ("kafka", "kafka"),
                    ("redis", "redis"),
                    ("elasticsearch", "elasticsearch"),
                    ("argus", "argus"),
                    ("victoria_metrics", "victoria_metrics"),
                    ("doris", "doris"),
                    ("bkdata", "bkdata"),
                    ("surrealdb", "surrealdb"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="集群类型",
            ),
        ),
        migrations.AlterField(
            model_name="resulttable",
            name="default_storage",
            field=models.CharField(
                choices=[
                    ("influxdb", "influxDB"),
                    ("kafka", "kafka"),
                    ("redis", "redis"),
                    ("elasticsearch", "elasticsearch"),
                    ("argus", "argus"),
                    ("victoria_metrics", "victoria_metrics"),
                    ("doris", "doris"),
                    ("bkdata", "bkdata"),
                    ("surrealdb", "surrealdb"),
                ],
                max_length=32,
                verbose_name="默认存储方案",
            ),
        ),
        migrations.AlterField(
            model_name="spacerelatedstorageinfo",
            name="storage_type",
            field=models.CharField(
                choices=[
                    ("influxdb", "influxDB"),
                    ("kafka", "kafka"),
                    ("redis", "redis"),
                    ("elasticsearch", "elasticsearch"),
                    ("argus", "argus"),
                    ("victoria_metrics", "victoria_metrics"),
                    ("doris", "doris"),
                    ("bkdata", "bkdata"),
                    ("surrealdb", "surrealdb"),
                ],
                max_length=32,
                verbose_name="存储类型",
            ),
        ),
        migrations.AlterField(
            model_name="bkbaseresulttable",
            name="storage_type",
            field=models.CharField(
                choices=[
                    ("influxdb", "influxDB"),
                    ("kafka", "kafka"),
                    ("redis", "redis"),
                    ("elasticsearch", "elasticsearch"),
                    ("argus", "argus"),
                    ("victoria_metrics", "victoria_metrics"),
                    ("doris", "doris"),
                    ("bkdata", "bkdata"),
                    ("surrealdb", "surrealdb"),
                ],
                default="victoria_metrics",
                max_length=32,
                verbose_name="存储类型",
            ),
        ),
    ]
