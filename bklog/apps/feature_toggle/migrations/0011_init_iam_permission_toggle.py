"""初始化 IAM 鉴权模式配置。"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name__in=["iam_v3_permission", "iam_v4_permission"]).delete()
    feature_toggle.objects.update_or_create(
        name=IAM_PERMISSION_MODE,
        defaults={
            "alias": "IAM 鉴权模式",
            "status": "on",
            "is_viewed": False,
            "description": "IAM 鉴权模式，可选 v3 / v4 / union",
            "feature_config": {"mode": "v3"},
            "biz_id_white_list": None,
            "biz_id_black_list": None,
        },
    )


def backwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name=IAM_PERMISSION_MODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0010_init_ext_json_expand_depth_toggle"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
