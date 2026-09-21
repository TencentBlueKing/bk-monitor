from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitor_web", "0077_collectorpluginmeta_id")]

    operations = [
        migrations.AddField(
            model_name=model,
            name="nodeman_backend",
            field=models.CharField(default="v2", max_length=16, verbose_name="节点管理后端"),
        )
        for model in ("collectorpluginmeta", "deploymentconfigversion")
    ]
