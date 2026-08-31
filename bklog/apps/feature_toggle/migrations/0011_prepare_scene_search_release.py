"""为场景化检索正式发布准备数据库特性开关。"""

from django.db import migrations

from apps.feature_toggle.plugins.constants import SCENE_SEARCH


def prepare_scene_search_release(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.update_or_create(
        name=SCENE_SEARCH,
        defaults={"status": "debug"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("feature_toggle", "0010_init_ext_json_expand_depth_toggle"),
    ]

    operations = [migrations.RunPython(prepare_scene_search_release, migrations.RunPython.noop)]
