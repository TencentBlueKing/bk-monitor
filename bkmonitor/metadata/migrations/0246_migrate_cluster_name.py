from django.db import migrations


def migrate_cluster_name(apps, schema_editor):
    ClusterInfo = apps.get_model("metadata", "ClusterInfo")

    for cluster in ClusterInfo.objects.all():
        # 设置显示名称
        cluster.display_name = cluster.cluster_name

        # 检查cluster_name是否符合[a-zA-Z][a-zA-Z0-9_]*格式
        if ClusterInfo.CLUSTER_NAME_REGEX.match(cluster.cluster_name):
            continue

        # 替换为新的cluster_name，体现自动生成的含义
        cluster.cluster_name = f"auto_cluster_name_{cluster.cluster_id}"

        # 如果集群类型为VM或注册来源系统为BKDATA，则默认标记为已注册到bkbase平台
        if (
            cluster.cluster_type == ClusterInfo.TYPE_VM
            or cluster.registered_system == ClusterInfo.BKDATA_REGISTERED_SYSTEM
        ):
            cluster.registered_to_bkbase = True
            cluster.save()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0245_auto_20251121_1510"),
    ]

    operations = [
        migrations.RunPython(migrate_cluster_name),
    ]
