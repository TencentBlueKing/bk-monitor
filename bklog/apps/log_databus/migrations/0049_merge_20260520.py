# Merge migration: 收敛 deploy/doris_storage 与 master 同步后产生的双 leaf 冲突。
# - 0047_collectorconfig_storage_cluster_type 由 deploy/doris_storage 引入
# - 0047_grokinfo + 0048_init_builtin_grok_patterns 由 upstream/master 同步合入
# 两条链路在 0046_collectorconfig_enable_v4 之后分叉，需要 merge 节点收敛。

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("log_databus", "0047_collectorconfig_storage_cluster_type"),
        ("log_databus", "0048_init_builtin_grok_patterns"),
    ]

    operations = []
