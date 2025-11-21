import re

from django.db import migrations


def migrate_cluster_name(apps, schema_editor):
    ClusterInfo = apps.get_model("metadata", "ClusterInfo")
    re_cluster_name = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,49}$")

    for cluster in ClusterInfo.objects.all():
        cluster.display_name = cluster.cluster_name

        # 检查cluster_name是否符合[a-zA-Z][a-zA-Z0-9_]*格式
        if re_cluster_name.match(cluster.cluster_name):
            continue

        # 替换为新的cluster_name，体现自动生成的含义
        cluster.cluster_name = f"auto_cluster_name_{cluster.cluster_id}"
        cluster.save()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0245_auto_20251121_1510"),
    ]

    operations = [
        migrations.RunPython(migrate_cluster_name),
    ]
