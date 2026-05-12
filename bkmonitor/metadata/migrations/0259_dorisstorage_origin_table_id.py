# Generated manually on 2026-05-11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0258_addindex_timeseriesmetric"),
    ]

    operations = [
        migrations.AddField(
            model_name="dorisstorage",
            name="origin_table_id",
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name="原始结果表名"),
        ),
    ]
