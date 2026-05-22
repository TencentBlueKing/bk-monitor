# -*- coding: utf-8 -*-
"""
场景化检索按业务灰度初始化。
- status=debug：仅 biz_id_white_list 内业务可见
- is_viewed=True：通过 /meta/index_html_environment/ 透传给前端 window.FEATURE_TOGGLE
- biz_id_white_list 默认空，运维通过 Django Admin 按需添加 bk_biz_id
"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import SCENE_SEARCH


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.update_or_create(
        name=SCENE_SEARCH,
        defaults={
            "alias": "场景化检索",
            "status": "debug",
            "is_viewed": True,
            "biz_id_white_list": [],
            "biz_id_black_list": [],
            "description": "场景化检索按业务灰度，白名单内业务前端入口可见",
        },
    )


def backwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name=SCENE_SEARCH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0008_featuretoggle_biz_id_black_list"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
