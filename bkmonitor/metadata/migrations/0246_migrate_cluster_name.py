import re
from django.db import migrations


def migrate_cluster_name(apps, schema_editor):
    ClusterInfo = apps.get_model("metadata", "ClusterInfo")

    re_cluster_name = re.compile(r"^[_A-Za-z0-9][_A-Za-z0-9-]{0,49}$")
    for cluster in ClusterInfo.objects.all():
        # 设置显示名称
        cluster.display_name = cluster.cluster_name

        # 检查cluster_name是否符合[a-zA-Z][a-zA-Z0-9_]*格式
        if not re_cluster_name.match(cluster.cluster_name):
            # 替换为新的cluster_name，体现自动生成的含义
            cluster.cluster_name = f"auto_cluster_name_{cluster.cluster_id}"

        # 如果集群类型为VM或注册来源系统为BKDATA，则默认标记为已注册到bkbase平台
        if cluster.cluster_type == "victoria_metrics" or cluster.registered_system == "bkdata":
            cluster.registered_to_bkbase = True

        cluster.save()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0245_auto_20251121_1510"),
    ]

    operations = [
        migrations.RunPython(migrate_cluster_name),
    ]
