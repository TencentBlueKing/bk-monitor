from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0276_custom_format_datalink"),
    ]

    operations = [
        migrations.CreateModel(
            name="VmQueryClusterConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_tenant_id", models.CharField(max_length=256, verbose_name="租户ID")),
                ("namespace", models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间")),
                ("name", models.CharField(max_length=255, verbose_name="资源名称")),
                ("cluster_name", models.CharField(max_length=255, verbose_name="查询集群名称")),
                ("cluster_domain", models.CharField(max_length=255, verbose_name="查询集群域名")),
                ("num_replicas", models.PositiveIntegerField(verbose_name="副本数")),
                ("monitor_storage_clusters", models.JSONField(default=list, verbose_name="关联的 VM storage 名称")),
                ("k8s_cluster", models.CharField(max_length=255, verbose_name="K8s 集群")),
                ("k8s_namespace", models.CharField(max_length=255, verbose_name="K8s 命名空间")),
                ("version", models.CharField(max_length=255, verbose_name="版本")),
                ("status", models.CharField(blank=True, default="", max_length=64, verbose_name="状态")),
                ("last_synced_at", models.DateTimeField(blank=True, null=True, verbose_name="最后成功同步时间")),
                ("origin_config", models.JSONField(default=dict, verbose_name="原始配置")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
            ],
            options={
                "verbose_name": "VM 查询集群配置",
                "verbose_name_plural": "VM 查询集群配置",
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
    ]
