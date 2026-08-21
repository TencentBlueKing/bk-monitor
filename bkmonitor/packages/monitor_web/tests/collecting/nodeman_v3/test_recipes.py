import pytest

from monitor_web.collecting.deploy.nodeman_v3.recipes import build_collect_recipe
from monitor_web.collecting.deploy.nodeman_v3.validation import validate_config_matrix
from monitor_web.plugin.constant import PluginType


def test_exporter_recipe_uses_collect_config_identity_for_both_resources():
    recipe_a = build_collect_recipe(
        plugin_type=PluginType.EXPORTER,
        collect_config_id=101,
        plugin_name="mysql_exporter",
    )
    recipe_b = build_collect_recipe(
        plugin_type=PluginType.EXPORTER,
        collect_config_id=102,
        plugin_name="mysql_exporter",
    )

    assert [resource.role for resource in recipe_a.resources] == ["plugin_instance", "bkmonitorbeat_subconfig"]
    assert {resource.identity_key for resource in recipe_a.resources}.isdisjoint(
        {resource.identity_key for resource in recipe_b.resources}
    )
    assert all("collect:101" in resource.identity_key for resource in recipe_a.resources)
    assert all("collect:102" in resource.identity_key for resource in recipe_b.resources)


@pytest.mark.parametrize("plugin_type", [PluginType.SCRIPT, PluginType.DATADOG, PluginType.PROCESS])
def test_non_exporter_recipe_keeps_a_per_collect_bkmonitorbeat_subconfig(plugin_type):
    recipe = build_collect_recipe(plugin_type=plugin_type, collect_config_id=101, plugin_name="check_plugin")

    assert [resource.role for resource in recipe.resources] == ["bkmonitorbeat_subconfig"]
    assert recipe.resources[0].identity_key == "collect:101:bkmonitorbeat:check_plugin"


def test_k8s_is_not_routed_to_nodeman_v3_recipe():
    with pytest.raises(ValueError, match="K8S"):
        build_collect_recipe(plugin_type=PluginType.K8S, collect_config_id=101, plugin_name="plugin")


def test_install_and_upgrade_only_accept_main_config():
    main_config = {"is_main": True, "plugin_version": "1.0.0"}
    sub_config = {"is_main": False, "plugin_version": "1.0.0"}

    validate_config_matrix("install", [main_config], target_version="1.0.0")
    validate_config_matrix("upgrade", [main_config], target_version="1.0.0")
    with pytest.raises(ValueError, match="main config"):
        validate_config_matrix("install", [sub_config], target_version="1.0.0")
    with pytest.raises(ValueError, match="main config"):
        validate_config_matrix("upgrade", [main_config, sub_config], target_version="1.0.0")


def test_apply_requires_nonempty_subconfig_matching_current_process_version():
    sub_config = {"is_main": False, "plugin_version": "1.0.0"}

    validate_config_matrix("apply", [sub_config], current_version="1.0.0")
    with pytest.raises(ValueError, match="non-empty"):
        validate_config_matrix("apply", [], current_version="1.0.0")
    with pytest.raises(ValueError, match="subconfig"):
        validate_config_matrix("apply", [{"is_main": True, "plugin_version": "1.0.0"}], current_version="1.0.0")
    with pytest.raises(ValueError, match="current process version"):
        validate_config_matrix("apply", [sub_config], current_version="2.0.0")
