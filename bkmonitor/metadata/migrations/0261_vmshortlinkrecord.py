# Generated manually on 2026-05-15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0260_basereportsinkconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="VMShortLinkRecord",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("space_type", models.CharField(db_index=True, max_length=64, verbose_name="空间类型")),
                ("space_id", models.CharField(db_index=True, max_length=128, verbose_name="空间ID")),
                ("table_id", models.CharField(db_index=True, max_length=128, verbose_name="虚拟结果表ID")),
                ("vm_result_table_id", models.CharField(db_index=True, max_length=128, verbose_name="VM 结果表ID")),
                ("vm_result_table_name", models.CharField(max_length=255, verbose_name="VM 结果表名称")),
                ("vm_cluster_id", models.IntegerField(verbose_name="VM 集群ID")),
                ("query_router_config", models.JSONField(default=dict, verbose_name="查询路由配置")),
                ("is_global", models.BooleanField(default=False, verbose_name="是否为同类型空间全局表")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="是否删除")),
            ],
            options={
                "verbose_name": "VM 短链路接入记录",
                "verbose_name_plural": "VM 短链路接入记录",
                "unique_together": {("bk_tenant_id", "table_id"), ("bk_tenant_id", "vm_result_table_id")},
            },
        ),
    ]
