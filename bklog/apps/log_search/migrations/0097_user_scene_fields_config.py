# Generated for scene_search user fields config

import apps.models
import apps.utils.local
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0096_favorite_scene_support"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSceneFieldsConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="业务ID")),
                ("username", models.CharField(db_index=True, max_length=64, verbose_name="用户名")),
                ("scene_id", models.CharField(db_index=True, max_length=64, verbose_name="场景ID")),
                ("scope", models.CharField(default="default", max_length=16, verbose_name="检索范围")),
                (
                    "source_app_code",
                    models.CharField(
                        blank=True,
                        default=apps.utils.local.get_request_app_code,
                        max_length=32,
                        verbose_name="来源系统",
                    ),
                ),
                ("display_fields", apps.models.JsonField(default=list, verbose_name="显示字段")),
                ("sort_list", apps.models.JsonField(default=list, verbose_name="排序规则")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "场景化检索-用户字段展示配置",
                "verbose_name_plural": "场景化检索-用户字段展示配置",
                "unique_together": {("bk_biz_id", "username", "scene_id", "scope", "source_app_code")},
            },
        ),
    ]
