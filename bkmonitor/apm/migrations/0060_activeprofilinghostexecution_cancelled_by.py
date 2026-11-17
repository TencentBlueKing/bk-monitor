from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0059_merge_20261102_1150"),
    ]

    operations = [
        migrations.AddField(
            model_name="activeprofilinghostexecution",
            name="cancelled_by",
            field=models.CharField(max_length=128, null=True, verbose_name="取消人"),
        ),
    ]
