from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0281_databusconfig_options")]

    operations = [
        migrations.AddField(
            model_name=model_name,
            name="physical_tables",
            field=models.JSONField(default=dict, verbose_name="物理表用途映射"),
        )
        for model_name in ("dorisstorage", "dorisstoragebindingconfig", "storageclusterrecord")
    ] + [
        migrations.AddField(
            model_name="storageclusterrecord",
            name="bkbase_table_id",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="BKBase结果表ID"),
        ),
    ]
