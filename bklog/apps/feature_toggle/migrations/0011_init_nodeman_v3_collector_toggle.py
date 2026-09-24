"""初始化 NodeMan V3 物理机采集准入开关。"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import NODEMAN_V3_COLLECTOR


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.get_or_create(
        name=NODEMAN_V3_COLLECTOR,
        defaults={
            "alias": "NodeMan V3 物理机采集",
            "status": "on",
            "is_viewed": False,
            "feature_config": {"collector_config_ids": []},
            "biz_id_white_list": [],
            "biz_id_black_list": [],
            "description": "控制新建物理机采集项进入 NodeMan V3；首次创建默认全量开启",
        },
    )


def backwards_func(apps, schema_editor):
    # 无法区分记录是本迁移创建，还是部署前由运维预置。回滚时保留记录，避免误删已有配置。
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0010_init_ext_json_expand_depth_toggle"),
    ]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
