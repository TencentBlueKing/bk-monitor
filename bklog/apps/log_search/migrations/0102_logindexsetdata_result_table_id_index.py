from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0101_favorite_scope"),
    ]

    operations = [
        migrations.AlterField(
            model_name="logindexsetdata",
            name="result_table_id",
            field=models.CharField(db_index=True, max_length=255, verbose_name="结果表"),
        ),
    ]
