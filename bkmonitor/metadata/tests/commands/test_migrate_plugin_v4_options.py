import json
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from metadata import models


@pytest.fixture(params=["migrate_default_plugin_v4", "migrate_multi_table_plugin_v4"])
def command_module(request):
    return import_module(f"metadata.management.commands.{request.param}")


def test_link_options_arguments(command_module, mocker):
    command = command_module.Command()
    mocker.patch.object(command, "handle_one")
    call_command(
        command,
        "pre-run",
        "--bk-tenant-id",
        "test-tenant",
        "--bk-data-id",
        "123",
        "--databus-cluster-name",
        "databus-test",
    )
    assert command.link_options == {
        "cmdb_level_config": ["bk_set_id", "bk_module_id"],
        "databus_prefer_cluster": {"name": "databus-test"},
    }


def test_cmdb_levels_are_enabled_by_default(command_module, mocker):
    command = command_module.Command()
    mocker.patch.object(command, "handle_one")
    call_command(command, "pre-run", "--bk-tenant-id", "test-tenant", "--bk-data-id", "123")
    assert command.link_options == {"cmdb_level_config": ["bk_set_id", "bk_module_id"]}


@pytest.mark.parametrize("phase", ["pre-run", "status"])
def test_read_only_phases_do_not_save_options_or_apply(command_module, mocker, phase):
    command = command_module.Command()
    mocker.patch.object(command, "load_context")
    mocker.patch.object(command, "precheck", return_value=[])
    mocker.patch.object(command, "plan", return_value={})
    mocker.patch.object(command, "check_status", return_value={"ready": True})
    writes = mocker.patch.object(models.ResultTableOption.objects, "update_or_create")
    apply_link = mocker.patch.object(command_module, "create_bkbase_data_link")
    call_command(
        command,
        phase,
        "--bk-tenant-id",
        "test-tenant",
        "--bk-data-id",
        "123",
        "--bk-biz-id",
        "2",
        "--databus-cluster-name",
        "databus-test",
    )
    writes.assert_not_called()
    apply_link.assert_not_called()


@pytest.mark.parametrize("existing,configured", [(False, False), (False, True), (True, True), (True, False)])
def test_options_saved_before_apply_without_reregistering_existing_resources(
    command_module, mocker, existing, configured
):
    command = command_module.Command()
    command.tenant, command.namespace, command.operator = "test-tenant", "bkmonitor", "tester"
    command.table_id, command.datalink_biz_id = "script_test.__default__", 2
    command.databus_cluster_name = "databus-test" if configured else None
    command.link_options = {"cmdb_level_config": ["bk_set_id", "bk_module_id"]}
    if configured:
        command.link_options["databus_prefer_cluster"] = {"name": "databus-test"}
    command.source = SimpleNamespace(
        etl_config="bk_standard",
        bk_data_id=123,
        register_to_bkbase=mocker.Mock(),
        delete_consul_config=mocker.Mock(),
    )
    command.cluster = SimpleNamespace(cluster_name="vm-test")
    component = SimpleNamespace(name="existing", kind="Databus")
    mocker.patch.object(command, "component_records", side_effect=[([component] if existing else []), [component]])
    wait = mocker.patch.object(command, "wait_for_components")
    writes = mocker.patch.object(models.ResultTableOption.objects, "update_or_create")
    mocker.patch.object(command_module, "compose_transfer_consumer_group", return_value="original-group")
    if hasattr(command, "prepare_default"):
        mocker.patch.object(command, "prepare_default")
        mocker.patch.object(command, "consumer_group_status", return_value=[{"matches": True}])
        mocker.patch.object(command, "publish_and_finalize")

    def apply(**kwargs):
        saved = {c.kwargs["name"]: c.kwargs for c in writes.call_args_list}
        for name, value in command.link_options.items():
            assert saved[name]["bk_tenant_id"] == "test-tenant"
            assert saved[name]["table_id"] == command.table_id
            assert json.loads(saved[name]["defaults"]["value"]) == value
            assert saved[name]["defaults"]["value_type"] == type(value).__name__
        assert kwargs["consumer_group"] == "original-group"

    apply_link = mocker.patch.object(command_module, "create_bkbase_data_link", side_effect=apply)
    command.execute_migration()
    saved_names = {call.kwargs["name"] for call in writes.call_args_list}
    assert ("cmdb_level_config" in saved_names) == (not existing or configured)
    assert ("databus_prefer_cluster" in saved_names) == configured
    assert apply_link.call_count == int(not existing or configured)
    assert command.source.register_to_bkbase.call_count == int(not existing)
    assert wait.call_args.kwargs["newly_applied"] == (not existing or configured)
