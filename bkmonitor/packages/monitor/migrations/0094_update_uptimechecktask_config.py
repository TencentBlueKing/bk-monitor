from django.db import migrations

from monitor.utils import update_task_config


def update_config(apps, schema_editor):
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")
    for task in UptimeCheckTask.objects.filter(is_deleted=False):
        # http拨测结构升级
        if task.protocol == "HTTP":
            if task.config:
                task.config = update_task_config(task.config)
        # 支持秒级拨测
        task.config["period"] = task.config.get("period", 1) * 60
        task.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0093_remove_uptimechecktask_subscription_id"),
    ]

    operations = [
        migrations.RunPython(update_config),
    ]
