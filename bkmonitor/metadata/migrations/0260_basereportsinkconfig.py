# Generated manually on 2026-05-15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0259_dorisstorage_origin_table_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="BasereportSinkConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
                ("status", models.CharField(max_length=64, verbose_name="状态")),
                ("data_link_name", models.CharField(blank=True, max_length=64, verbose_name="数据链路名称")),
                ("bk_biz_id", models.BigIntegerField(verbose_name="业务ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("name", models.CharField(db_index=True, max_length=64, verbose_name="基础采集处理配置名称")),
                ("vm_storage_binding_names", models.JSONField(default=list, verbose_name="VM 存储绑定名称列表")),
                ("result_table_ids", models.JSONField(default=list, verbose_name="结果表 ID 列表")),
            ],
            options={
                "verbose_name": "基础采集处理配置",
                "verbose_name_plural": "基础采集处理配置",
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
    ]
