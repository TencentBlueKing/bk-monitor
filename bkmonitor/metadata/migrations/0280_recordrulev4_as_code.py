from django.db import migrations, models


def mark_deleted_rules(apps, schema_editor):
    rule_model = apps.get_model("metadata", "RecordRuleV4")
    rule_model.objects.using(schema_editor.connection.alias).filter(
        models.Q(desired_status="deleted") | models.Q(deleted_at__isnull=False)
    ).update(is_deleted=True)


class Migration(migrations.Migration):
    dependencies = [("metadata", "0279_repair_system_base_metric_units")]

    operations = [
        migrations.AddField(
            model_name="recordrulev4",
            name="app",
            field=models.CharField("AsCode 所属应用", max_length=128, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="recordrulev4",
            name="path",
            field=models.TextField("AsCode 来源路径", blank=True, default=""),
        ),
        migrations.AddField(
            model_name="recordrulev4",
            name="is_deleted",
            field=models.BooleanField("是否软删除", default=False),
        ),
        migrations.RunPython(mark_deleted_rules, migrations.RunPython.noop),
    ]
