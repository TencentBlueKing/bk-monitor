# Generated for scene_search favorite support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0095_indexsettag_tag_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="favorite",
            name="source_type",
            field=models.CharField(
                choices=[("index_set", "索引集检索"), ("scene", "场景化检索")],
                db_index=True,
                default="index_set",
                max_length=16,
                verbose_name="收藏来源类型",
            ),
        ),
        migrations.AddField(
            model_name="favorite",
            name="scene_id",
            field=models.CharField(
                blank=True, db_index=True, default=None, max_length=64, null=True, verbose_name="场景ID"
            ),
        ),
        migrations.AddField(
            model_name="favorite",
            name="table_id_conditions",
            field=models.JSONField(blank=True, default=None, null=True, verbose_name="场景路由条件"),
        ),
        migrations.AddField(
            model_name="favorite",
            name="scene_filter_values",
            field=models.JSONField(blank=True, default=None, null=True, verbose_name="场景维度筛选"),
        ),
    ]
