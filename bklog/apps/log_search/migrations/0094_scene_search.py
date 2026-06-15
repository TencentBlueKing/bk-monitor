"""Squashed migration for scene_search infrastructure.

Replaces the original 0094~0102 incremental migrations with a single, consolidated
migration. The data-migration steps (IndexSetTag.tag_type backfill, UserSceneFieldsConfig
-> SceneFieldsConfig template split, legacy FavoriteGroup name repair) and their strict
ordering ("create model -> migrate data -> drop legacy field") are preserved exactly so
the squashed result is behaviourally identical to applying the originals in sequence.
"""

import apps.models
import apps.utils.local
from django.db import migrations, models

INNER_TAG_NAMES = ["trace", "restoring", "restored", "no_data", "have_delay", "bkdata", "bcs", "clustering"]


def migrate_tag_types(apps_registry, schema_editor):
    """Set tag_type for existing rows: inner tags by name, scene tags by non-empty value."""
    IndexSetTag = apps_registry.get_model("log_search", "IndexSetTag")
    IndexSetTag.objects.filter(name__in=INNER_TAG_NAMES, value="").update(tag_type="inner")
    IndexSetTag.objects.exclude(value="").update(tag_type="scene")


def _migrate_user_scene_fields(apps_registry, schema_editor):
    """Convert legacy single-table UserSceneFieldsConfig rows into template + pointer."""
    UserSceneFieldsConfig = apps_registry.get_model("log_search", "UserSceneFieldsConfig")
    SceneFieldsConfig = apps_registry.get_model("log_search", "SceneFieldsConfig")

    default_name = "默认"

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


def fix_private_group_name(apps_registry, schema_editor):
    FavoriteGroup = apps_registry.get_model("log_search", "FavoriteGroup")
    FavoriteGroup.objects.filter(group_type="private", name="private").update(name="个人收藏")
    FavoriteGroup.objects.filter(group_type="unknown", name="unknown").update(name="未分组")


def fix_private_group_name_reverse(apps_registry, schema_editor):
    # No-op: the original literal cannot be reliably restored without per-row history.
    pass


class Migration(migrations.Migration):

    replaces = [
        ("log_search", "0094_indexsettag_value_and_unique_together"),
        ("log_search", "0095_indexsettag_tag_type"),
        ("log_search", "0096_favorite_scene_support"),
        ("log_search", "0097_user_scene_fields_config"),
        ("log_search", "0098_scene_fields_config_template"),
        ("log_search", "0099_scene_fields_config_drop_legacy"),
        ("log_search", "0100_user_scene_custom_config"),
        ("log_search", "0101_favoritegroup_source_type"),
        ("log_search", "0102_fix_private_group_name"),
    ]

    dependencies = [
        ("log_search", "0093_logindexset_is_platform_index_and_more"),
    ]

    operations = [
        # --- IndexSetTag: value + tag_type + unique constraint ---
        migrations.AddField(
            model_name="indexsettag",
            name="value",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="标签值"),
        ),
        migrations.AlterField(
            model_name="indexsettag",
            name="name",
            field=models.CharField(db_index=True, max_length=255, verbose_name="标签名称"),
        ),
        migrations.AddField(
            model_name="indexsettag",
            name="tag_type",
            field=models.CharField(
                choices=[("user", "用户自定义"), ("inner", "系统内置"), ("scene", "场景维度")],
                db_index=True,
                default="user",
                max_length=16,
                verbose_name="标签类型",
            ),
        ),
        migrations.RunPython(migrate_tag_types, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="indexsettag",
            unique_together={("name", "value", "tag_type")},
        ),
        # --- Favorite: scene_search support ---
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
        # --- UserSceneFieldsConfig: created with legacy fields, later split into templates ---
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
        # --- SceneFieldsConfig template model + data migration from legacy rows ---
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
        migrations.AlterField(
            model_name="userscenefieldsconfig",
            name="config_id",
            field=models.IntegerField(db_index=True, verbose_name="场景字段配置ID"),
        ),
        migrations.RemoveField(
            model_name="userscenefieldsconfig",
            name="display_fields",
        ),
        migrations.RemoveField(
            model_name="userscenefieldsconfig",
            name="sort_list",
        ),
        # --- UserSceneCustomConfig: UI preference JSON layer ---
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
        # --- FavoriteGroup: source_type isolation ---
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
        # --- FavoriteGroup: repair legacy English literal names ---
        migrations.RunPython(fix_private_group_name, fix_private_group_name_reverse),
    ]
