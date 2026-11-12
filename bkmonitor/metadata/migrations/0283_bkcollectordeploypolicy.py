from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0282_doris_physical_tables")]

    operations = [
        migrations.CreateModel(
            name="BkCollectorDeployPolicy",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=128, verbose_name="租户ID")),
                ("scene", models.CharField(max_length=32, verbose_name="下发场景")),
                ("resource_key", models.CharField(max_length=255, verbose_name="场景内资源标识")),
                ("bk_biz_id", models.IntegerField(db_index=True, default=0, verbose_name="业务ID")),
                ("bk_cloud_id", models.IntegerField(default=-1, verbose_name="云区域ID")),
                ("policy_name", models.CharField(max_length=255, verbose_name="部署策略名称")),
                ("deploy_policy_id", models.BigIntegerField(default=None, null=True, verbose_name="部署策略ID")),
                (
                    "fingerprint",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="最近一次成功下发的策略指纹"),
                ),
                ("bk_host_ids", models.JSONField(default=list, verbose_name="最近一次成功下发的目标主机")),
                (
                    "last_workflow_id",
                    models.CharField(blank=True, default="", max_length=128, verbose_name="最近一次执行的工作流ID"),
                ),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "bk-collector 节点管理V3部署策略",
                "verbose_name_plural": "bk-collector 节点管理V3部署策略",
                "db_table": "metadata_bk_collector_deploy_policy",
                "unique_together": {("bk_tenant_id", "scene", "resource_key")},
            },
        ),
    ]
