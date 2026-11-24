from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0060_activeprofilinghostexecution_cancelled_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="activeprofilingexecution",
            name="source_task_id",
            field=models.IntegerField(null=True, verbose_name="触发计划 ID"),
        ),
    ]
