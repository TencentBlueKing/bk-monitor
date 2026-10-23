from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0011_init_iam_permission_toggle"),
        ("feature_toggle", "0011_init_nodeman_v3_collector_toggle"),
    ]

    operations = []
