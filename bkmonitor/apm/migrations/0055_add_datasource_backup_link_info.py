from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0054_add_tracedatasource_bkdata_datalink_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="logdatasource",
            name="backup_link_info",
            field=models.JSONField(default=dict, verbose_name="备份链路信息"),
        ),
        migrations.AddField(
            model_name="metricdatasource",
            name="backup_link_info",
            field=models.JSONField(default=dict, verbose_name="备份链路信息"),
        ),
        migrations.AddField(
            model_name="profiledatasource",
            name="backup_link_info",
            field=models.JSONField(default=dict, verbose_name="备份链路信息"),
        ),
        migrations.AddField(
            model_name="tracedatasource",
            name="backup_link_info",
            field=models.JSONField(default=dict, verbose_name="备份链路信息"),
        ),
    ]
