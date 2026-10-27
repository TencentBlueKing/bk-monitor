from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0280_recordrulev4_as_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="LogClusteringSinkConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
                ("status", models.CharField(max_length=64, verbose_name="状态")),
                ("data_link_name", models.CharField(blank=True, max_length=64, verbose_name="数据链路名称")),
                ("bk_biz_id", models.BigIntegerField(verbose_name="业务ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("name", models.CharField(db_index=True, max_length=64, verbose_name="聚类Sink名称")),
                ("table_id", models.CharField(blank=True, default="", max_length=255, verbose_name="结果表ID")),
                ("raw_sink", models.JSONField(default=dict, verbose_name="原始存储引用")),
                ("binding", models.JSONField(default=dict, verbose_name="聚类绑定配置")),
                ("kafka_resource", models.JSONField(default=dict, verbose_name="聚类Kafka资源引用")),
                ("pattern_resource", models.JSONField(default=dict, verbose_name="Pattern存储资源引用")),
                ("attached", models.BooleanField(default=False, verbose_name="是否被Databus引用")),
                ("revision", models.IntegerField(default=0, verbose_name="配置版本")),
                (
                    "last_operation_id",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="最近操作ID"),
                ),
                (
                    "last_request_digest",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="最近请求摘要"),
                ),
            ],
            options={
                "verbose_name": "日志聚类Sink配置",
                "verbose_name_plural": "日志聚类Sink配置",
                "indexes": [
                    models.Index(fields=["bk_tenant_id", "namespace", "data_link_name"], name="lcsc_tenant_ns_dl_idx")
                ],
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
    ]
