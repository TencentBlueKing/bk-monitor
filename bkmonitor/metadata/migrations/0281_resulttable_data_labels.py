from django.db import migrations, models


def migrate_data_labels(apps, schema_editor):
    ResultTable = apps.get_model("metadata", "ResultTable")
    tables = ResultTable.objects.using(schema_editor.connection.alias)
    batch = []
    for table in tables.only("pk", "data_label").iterator(chunk_size=1000):
        table.data_labels = [label for label in (table.data_label or "").split(",") if label]
        batch.append(table)
        if len(batch) == 1000:
            tables.bulk_update(batch, ["data_labels"], batch_size=1000)
            batch = []
    if batch:
        tables.bulk_update(batch, ["data_labels"], batch_size=1000)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("metadata", "0280_recordrulev4_as_code")]
    operations = [
        migrations.AddField(
            model_name="resulttable",
            name="data_labels",
            field=models.JSONField("数据标签列表", default=list, blank=True),
        ),
        migrations.RunPython(migrate_data_labels, migrations.RunPython.noop),
    ]
