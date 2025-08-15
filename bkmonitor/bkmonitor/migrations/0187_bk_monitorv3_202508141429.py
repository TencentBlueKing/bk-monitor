from django.db import migrations

from iam.contrib.iam_migration.migrator import IAMMigrator


def forward_func(apps, schema_editor):
    migrator = IAMMigrator(Migration.migration_json)
    migrator.migrate()


class Migration(migrations.Migration):
    migration_json = "0004_uptime_check_node.json"

    dependencies = [("bkmonitor", "0186_auto_20250814_1255")]

    operations = [migrations.RunPython(forward_func)]
