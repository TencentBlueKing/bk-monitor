from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0053_shared_datasource"),
    ]

    operations = [
        migrations.AddField(
            model_name="sharedtracedatasource",
            name="bkdata_datalink_config",
            field=models.JSONField(default=dict, verbose_name="BkData链路配置"),
        ),
        migrations.AddField(
            model_name="tracedatasource",
            name="bkdata_datalink_config",
            field=models.JSONField(default=dict, verbose_name="BkData链路配置"),
        ),
    ]
