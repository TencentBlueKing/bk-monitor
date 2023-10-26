from django.db import migrations


def update_config(apps, schema_editor):
    UptimeCheckTask = apps.get_model("monitor", "UptimeCheckTask")
    for task in UptimeCheckTask.objects.filter(is_deleted=False):
        # udp拨测结构升级
        if task.protocol == "UDP":
            if task.config and not task.config.get("request_format"):
                task.config["response_format"] = "hex" + "|" + task.config.get("response_format", "eq")
                task.config["request_format"] = "hex"
        task.save()


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0094_update_uptimechecktask_config"),
    ]

    operations = [
        migrations.RunPython(update_config),
    ]
