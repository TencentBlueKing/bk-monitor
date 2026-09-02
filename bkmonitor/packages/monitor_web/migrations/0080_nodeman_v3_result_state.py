from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitor_web", "0079_nodeman_v3_deploy_policy")]

    operations = [
        migrations.AddField(
            model_name="monitornodemanoperation",
            name="result_state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("unsupported", "接口协议确定不支持"),
                    ("write_result_unknown", "写请求结果不确定"),
                ],
                default="",
                max_length=32,
                verbose_name="结果标记",
            ),
        ),
        migrations.AddField(
            model_name="monitornodemanworkflow",
            name="result_state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("unsupported", "接口协议确定不支持"),
                    ("write_result_unknown", "写请求结果不确定"),
                ],
                default="",
                max_length=32,
                verbose_name="结果标记",
            ),
        ),
    ]
