import copy
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connections
from django.test import override_settings

from bkmonitor.models import ActionPlugin

pytestmark = pytest.mark.django_db(databases=["monitor_api"])
migration = import_module("bkmonitor.migrations.0207_bk_incident_source_mapping")


@pytest.fixture
def plugin():
    ActionPlugin._base_manager.using("monitor_api").filter(pk=110).delete()
    return ActionPlugin._base_manager.using("monitor_api").create(
        id=110,
        plugin_key="bk_incident",
        plugin_type="bk_incident",
        name="custom plugin name",
        category="common",
        is_builtin=True,
        config_schema={"custom": "preserve"},
        backend_config=[
            {
                "function": "create_task",
                "resource_module": "api.bk_incident.default",
                "resource_class": "CreateTaskResource",
                "inputs": [{"key": "constants", "value": "custom expression"}],
                "custom": "preserve",
            },
            {"function": "schedule", "schedule_timedelta": 17},
        ],
    )


def read_plugin():
    return ActionPlugin._base_manager.using("monitor_api").filter(pk=110).values().get()


def run_migration():
    migration.add_source_mapping(apps, SimpleNamespace(connection=connections["monitor_api"]))


@override_settings(ENABLE_BK_INCIDENT_PLUGIN=False)
def test_migration_preserves_other_fields_and_is_idempotent(plugin, monkeypatch):
    monkeypatch.setenv("MIGRATE_ACTION_PLUGIN_ENABLED", "disabled")
    before = read_plugin()
    expected = copy.deepcopy(before)
    expected["backend_config"][0]["inputs"].append(migration.SOURCE_INPUT)
    run_migration()
    assert read_plugin() == expected
    run_migration()
    assert read_plugin() == expected


@pytest.mark.parametrize("source", [migration.SOURCE_INPUT, {"key": "source", "value": "custom", "format": "string"}])
def test_existing_source_is_not_overwritten(plugin, source):
    plugin.backend_config[0]["inputs"].append(source)
    plugin.save(using="monitor_api", update_fields=["backend_config"])
    before = read_plugin()
    run_migration()
    assert read_plugin() == before


@pytest.mark.parametrize(
    "field,value", [("plugin_key", "other"), ("plugin_type", "other"), ("is_builtin", False), ("is_deleted", True)]
)
def test_other_plugin_identity_is_not_modified(plugin, field, value):
    ActionPlugin._base_manager.using("monitor_api").filter(pk=110).update(**{field: value})
    before = read_plugin()
    run_migration()
    assert read_plugin() == before


def test_disabled_plugin_is_upgraded_without_enabling_it(plugin):
    ActionPlugin._base_manager.using("monitor_api").filter(pk=110).update(is_enabled=False)
    before = read_plugin()
    expected = copy.deepcopy(before)
    expected["backend_config"][0]["inputs"].append(migration.SOURCE_INPUT)
    run_migration()
    assert read_plugin() == expected


def test_missing_plugin_is_not_created(plugin):
    ActionPlugin._base_manager.using("monitor_api").filter(pk=110).delete()
    run_migration()
    assert not ActionPlugin._base_manager.using("monitor_api").filter(pk=110).exists()


@pytest.mark.parametrize("malformed", [None, {}, [], [{"function": "create_task", "inputs": []}]])
def test_malformed_config_fails_without_changes(plugin, malformed):
    ActionPlugin._base_manager.using("monitor_api").filter(pk=110).update(backend_config=malformed)
    before = read_plugin()
    with pytest.raises(RuntimeError, match="bk_incident plugin 110"):
        run_migration()
    assert read_plugin() == before


def test_duplicate_source_fails_without_changes(plugin):
    plugin.backend_config[0]["inputs"].extend([migration.SOURCE_INPUT, migration.SOURCE_INPUT])
    plugin.save(using="monitor_api", update_fields=["backend_config"])
    before = read_plugin()
    with pytest.raises(RuntimeError, match="duplicate source"):
        run_migration()
    assert read_plugin() == before


@pytest.mark.parametrize("change", ["duplicate_node", "bad_inputs", "wrong_resource"])
def test_changed_node_shape_fails_without_changes(plugin, change):
    if change == "duplicate_node":
        plugin.backend_config.append(copy.deepcopy(plugin.backend_config[0]))
    elif change == "bad_inputs":
        plugin.backend_config[0]["inputs"] = {}
    else:
        plugin.backend_config[0]["resource_module"] = "api.other"
    plugin.save(using="monitor_api", update_fields=["backend_config"])
    before = read_plugin()
    with pytest.raises(RuntimeError, match="bk_incident plugin 110"):
        run_migration()
    assert read_plugin() == before


def test_reverse_migration_keeps_existing_mapping(plugin):
    run_migration()
    before = read_plugin()
    migration.Migration.operations[0].reverse_code(apps, SimpleNamespace(connection=connections["monitor_api"]))
    assert read_plugin() == before
