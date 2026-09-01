from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitor_web", "0078_nodeman_v3_control_plane"),
    ]

    operations = [
        migrations.AddField(
            model_name="collectdeploymenttarget",
            name="node_man_deploy_policy_id",
            field=models.BigIntegerField(blank=True, null=True, verbose_name="NodeMan 部署策略 ID"),
        ),
        migrations.AddField(
            model_name="monitornodemanworkflow",
            name="trigger_id",
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name="NodeMan Trigger ID"),
        ),
        migrations.AddConstraint(
            model_name="monitornodemanworkflow",
            constraint=models.UniqueConstraint(
                fields=("monitor_operation", "trigger_id"),
                name="uniq_nodeman_trigger_operation_id",
            ),
        ),
    ]
