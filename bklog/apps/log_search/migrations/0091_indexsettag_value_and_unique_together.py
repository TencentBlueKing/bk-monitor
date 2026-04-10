"""
Add 'value' field to IndexSetTag and change unique constraint from name to (name, value).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0090_clear_favorite_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="indexsettag",
            name="value",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="标签值"),
        ),
        migrations.AlterField(
            model_name="indexsettag",
            name="name",
            field=models.CharField(db_index=True, max_length=255, verbose_name="标签名称"),
        ),
        migrations.AlterUniqueTogether(
            name="indexsettag",
            unique_together={("name", "value")},
        ),
    ]
