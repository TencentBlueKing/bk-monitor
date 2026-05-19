# Generated for scene_search fields config template refactor

import apps.models
import apps.utils.local
from django.db import migrations, models


def _migrate_user_scene_fields(apps_registry, schema_editor):
    """Convert legacy single-table UserSceneFieldsConfig rows into template + pointer.

    For every (bk_biz_id, scene_id, scope, source_app_code) tuple, ensure a "default"
    SceneFieldsConfig exists; users whose display_fields/sort_list mismatch the default
    get their own "<username>-custom" template. Then back-fill UserSceneFieldsConfig.config_id.
    """
    UserSceneFieldsConfig = apps_registry.get_model("log_search", "UserSceneFieldsConfig")
    SceneFieldsConfig = apps_registry.get_model("log_search", "SceneFieldsConfig")

    default_name = "默认"

    # Group rows by (biz, scene, scope, source) → keep order to make first row the default seed.
    grouped: dict[tuple, list] = {}
    for row in UserSceneFieldsConfig.objects.all():
        key = (row.bk_biz_id, row.scene_id, row.scope, row.source_app_code or "")
        grouped.setdefault(key, []).append(row)

    for (bk_biz_id, scene_id, scope, source_app_code), rows in grouped.items():
        default_template = SceneFieldsConfig.objects.filter(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            name=default_name,
            scope=scope,
            source_app_code=source_app_code,
        ).first()
        if default_template is None:
            seed = rows[0]
            default_template = SceneFieldsConfig.objects.create(
                name=default_name,
                bk_biz_id=bk_biz_id,
                scene_id=scene_id,
                scope=scope,
                source_app_code=source_app_code,
                display_fields=list(seed.display_fields or []),
                sort_list=list(seed.sort_list or []),
            )

        for row in rows:
            user_display = list(row.display_fields or [])
            user_sort = list(row.sort_list or [])
            default_display = list(default_template.display_fields or [])
            default_sort = list(default_template.sort_list or [])
            if user_display == default_display and user_sort == default_sort:
                row.config_id = default_template.id
            else:
                # Custom personal template named after the user; "-custom" suffix to avoid name clash.
                user_template = SceneFieldsConfig.objects.create(
                    name=f"{row.username}-custom",
                    bk_biz_id=bk_biz_id,
                    scene_id=scene_id,
                    scope=scope,
                    source_app_code=source_app_code,
                    display_fields=user_display,
                    sort_list=user_sort,
                )
                row.config_id = user_template.id
            row.save(update_fields=["config_id"])


def _migrate_user_scene_fields_reverse(apps_registry, schema_editor):
    """Restore display_fields/sort_list on UserSceneFieldsConfig from its referenced template."""
    UserSceneFieldsConfig = apps_registry.get_model("log_search", "UserSceneFieldsConfig")
    SceneFieldsConfig = apps_registry.get_model("log_search", "SceneFieldsConfig")
    for row in UserSceneFieldsConfig.objects.all():
        if not row.config_id:
            continue
        try:
            tpl = SceneFieldsConfig.objects.get(pk=row.config_id)
        except SceneFieldsConfig.DoesNotExist:
            continue
        row.display_fields = list(tpl.display_fields or [])
        row.sort_list = list(tpl.sort_list or [])
        row.save(update_fields=["display_fields", "sort_list"])


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0097_user_scene_fields_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="SceneFieldsConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, verbose_name="配置名称")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="业务ID")),
                ("scene_id", models.CharField(db_index=True, max_length=64, verbose_name="场景ID")),
                (
                    "scope",
                    models.CharField(db_index=True, default="default", max_length=16, verbose_name="范围"),
                ),
                (
                    "source_app_code",
                    models.CharField(
                        blank=True,
                        default=apps.utils.local.get_request_app_code,
                        max_length=32,
                        verbose_name="来源系统",
                    ),
                ),
                ("display_fields", apps.models.JsonField(default=list, verbose_name="字段配置")),
                ("sort_list", apps.models.JsonField(default=None, null=True, verbose_name="排序规则")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("created_by", models.CharField(blank=True, default="", max_length=64, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=64, verbose_name="更新者")),
            ],
            options={
                "verbose_name": "场景化检索-字段配置模板",
                "verbose_name_plural": "场景化检索-字段配置模板",
                "unique_together": {("bk_biz_id", "scene_id", "name", "scope", "source_app_code")},
            },
        ),
        migrations.AddField(
            model_name="userscenefieldsconfig",
            name="config_id",
            field=models.IntegerField(db_index=True, null=True, verbose_name="场景字段配置ID"),
        ),
        migrations.RunPython(_migrate_user_scene_fields, _migrate_user_scene_fields_reverse),
    ]
