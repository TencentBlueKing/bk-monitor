# Generated manually on 2026-05-17

from django.db import migrations, models


def backfill_data_labels(apps, schema_editor):
    VMShortLinkRecord = apps.get_model("metadata", "VMShortLinkRecord")
    ResultTable = apps.get_model("metadata", "ResultTable")
    result_table_map = {
        (record["bk_tenant_id"], record["table_id"]): record["data_label"] or ""
        for record in ResultTable.objects.filter(
            table_id__in=VMShortLinkRecord.objects.values_list("table_id", flat=True)
        ).values("bk_tenant_id", "table_id", "data_label")
    }
    records = []
    for record in VMShortLinkRecord.objects.all():
        data_label = result_table_map.get((record.bk_tenant_id, record.table_id), "")
        record.data_labels = [label for label in data_label.split(",") if label]
        records.append(record)
    if records:
        VMShortLinkRecord.objects.bulk_update(records, ["data_labels"])


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0262_recordrulev4"),
    ]

    operations = [
        migrations.AddField(
            model_name="vmshortlinkrecord",
            name="data_labels",
            field=models.JSONField(default=list, verbose_name="数据标签列表"),
        ),
        migrations.RunPython(backfill_data_labels, migrations.RunPython.noop),
    ]
