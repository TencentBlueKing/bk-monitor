from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0057_toponode_heartbeat"),
    ]

    operations = [
        migrations.AddField(
            model_name="tracedatasource",
            name="history_link_info",
            field=models.JSONField(default=list, verbose_name="历史链路信息"),
        ),
    ]
