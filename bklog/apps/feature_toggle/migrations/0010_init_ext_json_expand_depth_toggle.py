"""初始化 __ext_json 动态解析层级实验开关。

- status=debug：仅 biz_id_white_list 内业务可见「动态字段解析层级」配置
- is_viewed=True：通过 /meta/index_html_environment/ 透传给前端
  window.FEATURE_TOGGLE.ext_json_expand_depth
  window.FEATURE_TOGGLE_WHITE_LIST.ext_json_expand_depth
  window.FEATURE_TOGGLE_BLACK_LIST.ext_json_expand_depth
- 不控制「JSON 字段动态新增」开关本身，仅控制解析层级实验入口
"""

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
            "biz_id_white_list": [2],
            "biz_id_black_list": [],
            "description": "__ext_json 动态解析层级实验特性，按业务灰度开启；不控制 JSON 字段动态新增开关",
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
