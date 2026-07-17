"""初始化 __ext_json 动态解析层级实验开关。"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import EXT_JSON_EXPAND_DEPTH


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.update_or_create(
        name=EXT_JSON_EXPAND_DEPTH,
        defaults={
            "alias": "动态 JSON 解析层级",
            "status": "debug",
            "is_viewed": True,
            "biz_id_white_list": [],
            "biz_id_black_list": [],
            "description": "__ext_json 动态解析层级按业务灰度，白名单业务可配置",
        },
    )


def backwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name=EXT_JSON_EXPAND_DEPTH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0009_init_scene_search_toggle"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
