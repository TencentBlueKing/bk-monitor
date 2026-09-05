from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitor_web", "0080_nodeman_v3_result_state")]

    operations = [
        migrations.AddField(
            model_name="nodemanintegrationbinding",
            name="node_man_deploy_policy_id",
            field=models.BigIntegerField(blank=True, null=True, verbose_name="NodeMan 部署策略 ID"),
        ),
        migrations.AddField(
            model_name="nodemanintegrationbinding",
            name="node_man_policy_fingerprint",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="最近提交的策略指纹"),
        ),
    ]
