from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bkmonitor", "0204_migrate_graph_relation_v4_biz_id_white_list")]

    operations = [
        migrations.AddField(
            model_name="shield",
            name="end_policy",
            field=models.CharField(default="notify_once", max_length=16, verbose_name="屏蔽结束处理方式"),
        ),
    ]
