"""分片异步导出单片目标调整为 6 万条 / 128 MiB。

策略在创建任务时冻结为快照，这里只改开关上的实时配置，存量任务不受影响。
仅当配置仍是旧的 3 万条 / 64 MiB 时才更新，避免覆盖运维手工调整过的值。
"""

from django.db import migrations


FEATURE_NAME = "feature_async_export_sharded"
# 键: (旧值, 新值)
UPDATES = {
    "target_rows": (30_000, 60_000),
    "target_bytes": (64 * 1024 * 1024, 128 * 1024 * 1024),
}


def _apply(apps, pairs):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    toggle = feature_toggle.objects.filter(name=FEATURE_NAME).first()
    if toggle is None:
        return
    config = dict(toggle.feature_config or {})
    changed = False
    for key, (expected, target) in pairs.items():
        if config.get(key) == expected:
            config[key] = target
            changed = True
    if not changed:
        return
    toggle.feature_config = config
    toggle.save(update_fields=["feature_config"])


def forwards_func(apps, schema_editor):
    _apply(apps, UPDATES)


def backwards_func(apps, schema_editor):
    _apply(apps, {key: (target, expected) for key, (expected, target) in UPDATES.items()})


class Migration(migrations.Migration):
    dependencies = [("feature_toggle", "0012_init_sharded_async_export_toggle")]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
