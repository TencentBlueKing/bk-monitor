# Generated manually on 2026-05-26

from django.db import migrations

from metadata.migration_util import backfill_esstorage_origin_table_options


def backfill_options(apps, schema_editor):
    ESStorage = apps.get_model("metadata", "ESStorage")
    ResultTable = apps.get_model("metadata", "ResultTable")
    ResultTableOption = apps.get_model("metadata", "ResultTableOption")

    backfill_esstorage_origin_table_options(
        es_storage_model=ESStorage,
        result_table_model=ResultTable,
        result_table_option_model=ResultTableOption,
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("metadata", "0263_vmshortlinkrecord_data_labels"),
    ]

    operations = [
        migrations.RunPython(backfill_options, migrations.RunPython.noop),
    ]
