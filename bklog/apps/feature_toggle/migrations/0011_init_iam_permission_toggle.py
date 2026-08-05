"""初始化 IAM V3/V4 权限中心灰度开关。"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import IAM_V3_PERMISSION_TOGGLE, IAM_V4_PERMISSION_TOGGLE


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    toggle_defaults = {
        IAM_V3_PERMISSION_TOGGLE: {
            "alias": "IAM V3 权限中心",
            "status": "on",
            "is_viewed": False,
            "description": "IAM V3 权限校验开关，默认开启",
            "biz_id_white_list": None,
            "biz_id_black_list": None,
        },
        IAM_V4_PERMISSION_TOGGLE: {
            "alias": "IAM V4 权限中心",
            "status": "off",
            "is_viewed": False,
            "description": "IAM V4 权限校验开关，默认关闭",
            "biz_id_white_list": None,
            "biz_id_black_list": None,
        },
    }

    for name, defaults in toggle_defaults.items():
        feature_toggle.objects.update_or_create(name=name, defaults=defaults)


def backwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name__in=[IAM_V3_PERMISSION_TOGGLE, IAM_V4_PERMISSION_TOGGLE]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0010_init_ext_json_expand_depth_toggle"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
