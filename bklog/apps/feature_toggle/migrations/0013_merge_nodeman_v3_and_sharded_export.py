from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0012_init_sharded_async_export_toggle"),
        ("feature_toggle", "0012_merge_nodeman_v3_and_iam_permission"),
    ]

    operations = []
