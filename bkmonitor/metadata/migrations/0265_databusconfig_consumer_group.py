# Generated manually on 2026-06-02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0264_add_token_field_to_timeseries_log_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="databusconfig",
            name="consumer_group",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Consumer Group"),
        ),
    ]
