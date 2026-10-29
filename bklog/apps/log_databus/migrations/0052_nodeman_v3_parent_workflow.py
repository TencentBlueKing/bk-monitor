from django.db import migrations, models


class Migration(migrations.Migration):
    """
    NodeMan v3.0.1-alpha.84+ 的 deploy-policy 父子 workflow 契约。

    旧字段不改名：历史记录中的 workflow_id 是 plugin 子 workflow，直接重命名会把它误当成
    deploy-policy 父 workflow，导致状态与重试请求发到错误接口。
    """

    dependencies = [
        ("log_databus", "0051_nodeman_v3_target_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodemanv3workflow",
            name="parent_workflow_id",
            field=models.CharField(db_index=True, default="", max_length=128, verbose_name="部署策略父工作流ID"),
        ),
        migrations.AddField(
            model_name="nodemanv3workflow",
            name="plugin_workflow_ids",
            field=models.JSONField(default=list, verbose_name="插件子工作流ID列表"),
        ),
    ]
