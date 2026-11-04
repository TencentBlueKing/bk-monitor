from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0282_doris_physical_tables")]
    operations = [
        migrations.AddField(
            model_name="dorisstorage",
            name="table_version",
            field=models.PositiveIntegerField(default=0, verbose_name="物理表版本"),
        )
    ]
