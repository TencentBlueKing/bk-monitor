from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metric_plugin", "0002_alter_metricpluginversionmodel_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobtaskinstancemodel",
            name="collect_instance_info",
            field=models.JSONField(
                default=dict,
                help_text="实际执行采集和下发的实例信息，远程采集时为远程采集主机",
                verbose_name="采集执行实例信息",
            ),
        ),
    ]
