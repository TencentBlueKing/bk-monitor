from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0280_recordrulev4_as_code")]

    operations = [
        migrations.AddField(
            model_name="databusconfig",
            name="options",
            field=models.JSONField(blank=True, default=dict, verbose_name="清洗任务额外配置"),
        ),
    ]
