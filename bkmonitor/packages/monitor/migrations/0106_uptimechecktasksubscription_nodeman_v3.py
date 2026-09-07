from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitor", "0105_uptimechecknode_bk_tenant_id")]

    operations = [
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_backend",
            field=models.CharField(default="v2", max_length=16, verbose_name="节点管理后端"),
        ),
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_error",
            field=models.TextField(blank=True, default="", verbose_name="节点管理错误"),
        ),
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_operation_status",
            field=models.CharField(blank=True, default="", max_length=32, verbose_name="节点管理操作状态"),
        ),
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_policy_fingerprint",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="节点管理策略指纹"),
        ),
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_result_state",
            field=models.CharField(blank=True, default="", max_length=32, verbose_name="节点管理写入结果状态"),
        ),
        migrations.AddField(
            model_name="uptimechecktasksubscription",
            name="node_man_trigger_id",
            field=models.CharField(blank=True, default="", max_length=128, verbose_name="节点管理触发ID"),
        ),
    ]
