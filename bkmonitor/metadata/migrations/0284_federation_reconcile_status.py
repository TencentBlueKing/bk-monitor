from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0283_bkcollectordeploypolicy")]

    operations = [
        migrations.AddField(
            model_name="bcsfederalclusterinfo",
            name="reconcile_status",
            field=models.CharField(
                "链路收敛状态",
                max_length=16,
                default="success",
                choices=[("pending", "待收敛"), ("success", "成功"), ("failed", "失败")],
            ),
        ),
        migrations.AddField(
            model_name="bcsfederalclusterinfo",
            name="reconcile_failures",
            field=models.PositiveIntegerField("当前配置连续收敛失败次数", default=0),
        ),
        migrations.AlterField(
            model_name="bcsfederalclusterinfo",
            name="reconcile_status",
            field=models.CharField(
                "链路收敛状态",
                max_length=16,
                default="pending",
                choices=[("pending", "待收敛"), ("success", "成功"), ("failed", "失败")],
            ),
        ),
    ]
