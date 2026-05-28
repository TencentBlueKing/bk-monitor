# Generated for scene_search favorite group source_type isolation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0100_user_scene_custom_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="favoritegroup",
            name="source_type",
            field=models.CharField(
                choices=[("index_set", "索引集检索"), ("scene", "场景化检索")],
                db_index=True,
                default="index_set",
                max_length=16,
                verbose_name="收藏来源类型",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="favoritegroup",
            unique_together={("name", "space_uid", "created_by", "source_app_code", "source_type")},
        ),
    ]
