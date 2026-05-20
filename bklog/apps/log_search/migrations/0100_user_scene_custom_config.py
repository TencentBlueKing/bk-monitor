# Generated for scene_search user custom config (UI preference JSON layer)

import apps.utils.local
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0099_scene_fields_config_drop_legacy"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSceneCustomConfig",
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
                ("scene_config", models.JSONField(default=dict, verbose_name="场景用户配置")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "场景化检索-用户UI偏好",
                "verbose_name_plural": "场景化检索-用户UI偏好",
                "unique_together": {("bk_biz_id", "username", "scene_id", "scope", "source_app_code")},
            },
        ),
    ]
