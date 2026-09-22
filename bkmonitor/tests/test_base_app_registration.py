"""升级 Base 后，主仓仍使用自身的 APM 和 metadata 模型。"""

from django.apps import apps


def test_base_upgrade_preserves_main_model_registration():
    # 必须经过真实 django.setup()：加载 Base apm_core 而未加载 Base metadata 会在初始化阶段失败。
    assert apps.get_app_config("apm").name == "apm"
    assert apps.get_app_config("metadata").name == "metadata"
    assert not apps.is_installed("bk_monitor_base.metadata")
    assert not apps.is_installed("bk_monitor_base.domains.apm_core")

    # 排除重复模型域时，仍保留 Access 使用的 Base strategy 模型。
    item_model = apps.get_model("strategy", "ItemModel")
    assert item_model._meta.db_table == "alarm_item_v2"
    assert item_model._meta.get_field("access_lookback_periods").null
