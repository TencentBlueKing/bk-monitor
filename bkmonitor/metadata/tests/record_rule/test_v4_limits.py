"""部署上限不影响声明和解析，只影响预览判定与真实下发。"""

from types import SimpleNamespace

import pytest
import yaml
from django.core.cache.backends.locmem import LocMemCache
from django.db import connections
from django.test.utils import CaptureQueriesContext

from bkmonitor.as_code import parse
from bkmonitor.define.global_config import ADVANCED_OPTIONS
from bkmonitor.models import GlobalConfig
from bkmonitor.utils import dynamic_settings
from kernel_api.resource import recording_rule as api
from metadata import config, models
from metadata.models.record_rule.v4 import limits
from metadata.models.record_rule.v4.models import CONDITION_RESOLVED, RecordRuleV4
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator
from metadata.models.record_rule.v4.runner import RecordRuleV4Runner
from metadata.tests.record_rule.test_v4_operator import (
    SOURCE_BKBASE_TABLE_NAME,
    SOURCE_VM_TABLE_ID,
    TENANT_ID,
    build_check_result,
    create_source_vm_mapping,
    external_api as _external_api,
    v4_base_data as _v4_base_data,
)
from metadata.tests.record_rule.test_v4_public_api import call, group, public_context as _public_context

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context

pytestmark = pytest.mark.django_db(databases="__all__")


def config_with_rules(count, name="cpu"):
    value = group(name)
    value["rules"] = [{"record": f"cpu_{index}", "expr": "avg(system_cpu_usage)"} for index in range(count)]
    return value


def set_sources(count, external):
    source_ids = [SOURCE_VM_TABLE_ID]
    for index in range(1, count):
        vm_table_id = f"2_source_{index}"
        create_source_vm_mapping(
            table_id=f"source.table_{index}",
            vm_table_id=vm_table_id,
            bkbase_table_name=f"source_{index}",
            cluster_id=1001,
        )
        source_ids.append(vm_table_id)
    external.check_promql.return_value = build_check_result(result_table_id=source_ids)


def test_config_defaults_and_dynamic_database_updates(mocker):
    assert ADVANCED_OPTIONS["RECORD_RULE_V4_CONFIG"].default == {"max_sources": 20, "max_rules": 20}
    cache = LocMemCache("record-rule-v4-limit-test", {})
    cache.clear()
    mocker.patch.object(dynamic_settings, "locmem_cache", cache)
    mocker.patch.object(dynamic_settings, "redis_cache", None)
    GlobalConfig.objects.filter(key="RECORD_RULE_V4_CONFIG").delete()
    settings = dynamic_settings.DynamicSettings(
        SimpleNamespace(RECORD_RULE_V4_CONFIG={"max_sources": 20, "max_rules": 20}), GlobalConfig
    )
    mocker.patch.object(limits, "settings", settings)
    assert limits.check_deployment_limits(source_count=20, rule_count=20)["can_apply"]
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 2, "max_rules": 3}
    check = limits.check_deployment_limits(source_count=3, rule_count=4)
    assert not check["can_apply"] and len(check["errors"]) == 2
    assert check["max_sources"] == 2 and check["max_rules"] == 3
    assert GlobalConfig.get("RECORD_RULE_V4_CONFIG") == {"max_sources": 2, "max_rules": 3}
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 3, "max_rules": 4}
    assert limits.check_deployment_limits(source_count=3, rule_count=4)["can_apply"]
    cache.clear()


@pytest.mark.parametrize(
    "source_count,rule_count,allowed", [(20, 1, True), (21, 1, False), (1, 20, True), (1, 21, False)]
)
def test_preview_counts_boundaries_without_writes(public_context, source_count, rule_count, allowed):
    set_sources(source_count, public_context)
    with CaptureQueriesContext(connections[config.DATABASE_CONNECTION_NAME]) as queries:
        result = call(api.PreviewConfigResource, config=config_with_rules(rule_count))
    check = result["deployment_check"]
    assert check["source_count"] == source_count and check["rule_count"] == rule_count
    assert check["max_sources"] == check["max_rules"] == 20
    assert check["can_apply"] is allowed
    assert bool(check["errors"]) is not allowed
    assert len(result["records"]) == rule_count
    assert all(not query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for query in queries)
    assert not RecordRuleV4.objects.exists()
    public_context.apply_data_link.assert_not_called()
    public_context.space_redis.push_space_table_ids.assert_not_called()


def test_preview_source_identity_matches_flow_and_deduplicates_across_rules(public_context, settings):
    set_sources(2, public_context)
    models.ResultTableConfig.objects.filter(bk_tenant_id=TENANT_ID, name="source_1").update(
        namespace="another-namespace", name=SOURCE_BKBASE_TABLE_NAME
    )
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 2, "max_rules": 2}
    value = config_with_rules(2)
    preview = call(api.PreviewConfigResource, config=value)
    assert preview["deployment_check"]["source_count"] == 2
    assert preview["deployment_check"]["can_apply"]
    created = call(api.CreateConfigResource, config=value, apply=True)
    assert created["execution"]["succeeded"]
    nodes = public_context.apply_data_link.call_args.kwargs["config"][0]["spec"]["nodes"]
    assert len([node for node in nodes if node["kind"] == "VmSourceNode"]) == 2
    assert len([node for node in nodes if node["kind"] == "RecordingRuleNode"]) == 1


@pytest.mark.parametrize("source_count,rule_count,key", [(21, 1, "max_sources"), (1, 21, "max_rules")])
def test_create_saves_and_resolves_over_limit_but_apply_waits_for_config_change(
    public_context, settings, source_count, rule_count, key
):
    set_sources(source_count, public_context)
    created = call(api.CreateConfigResource, config=config_with_rules(rule_count), apply=True)
    assert created["saved"] and not created["execution"]["succeeded"]
    assert key in created["execution"]["error"]
    rule = RecordRuleV4.objects.get(pk=created["rule"]["id"])
    resolved = rule.get_latest_resolved()
    flow = rule.get_latest_flow()
    assert resolved.records.count() == rule_count
    assert rule.conditions[CONDITION_RESOLVED]["status"] == "True"
    assert rule.applied_resolved_id is None and flow is not None
    public_context.apply_data_link.assert_not_called()
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": source_count, "max_rules": rule_count}
    result = call(api.ApplyConfigResource, id=rule.pk)
    assert result["execution"]["succeeded"]
    rule.refresh_from_db()
    assert rule.applied_resolved_id == resolved.pk
    assert rule.get_latest_flow().pk == flow.pk
    public_context.apply_data_link.assert_called_once()


def test_save_and_manual_resolve_are_not_deployment_checks(public_context, settings):
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 1, "max_rules": 1}
    created = call(api.CreateConfigResource, config=config_with_rules(2))
    assert created["saved"] and created["execution"] is None
    rule = RecordRuleV4.objects.get(pk=created["rule"]["id"])
    assert rule.current_spec.records.count() == 2
    resolved = RecordRuleV4Operator(rule).refresh_resolved()
    assert resolved.records.count() == 2
    assert not rule.flows.exists()
    public_context.apply_data_link.assert_not_called()


def test_cached_flow_rechecks_latest_config_and_delete_is_not_blocked(public_context, settings):
    rule_id = call(api.CreateConfigResource, config=config_with_rules(2))["rule"]["id"]
    rule = RecordRuleV4.objects.get(pk=rule_id)
    RecordRuleV4Operator(rule).execute_declaration(auto_apply=False)
    flow = rule.get_latest_flow()
    assert flow is not None
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    assert not RecordRuleV4Runner(rule).apply()
    public_context.apply_data_link.assert_not_called()
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 2}
    assert RecordRuleV4Runner(rule).apply()
    rule.refresh_from_db()
    assert rule.get_applied_flow().pk == flow.pk
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    assert call(api.DeleteConfigResource, id=rule.pk)["execution"]["succeeded"]
    public_context.delete_data_link.assert_called_once()


def test_over_limit_update_preserves_previous_applied_flow(public_context, settings):
    created = call(api.CreateConfigResource, config=config_with_rules(1), apply=True)
    applied_id = created["rule"]["applied_resolved_id"]
    public_context.apply_data_link.reset_mock()
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    updated = call(api.UpdateConfigResource, id=created["rule"]["id"], config=config_with_rules(2), apply=True)
    assert updated["saved"] and not updated["execution"]["succeeded"]
    rule = RecordRuleV4.objects.get(pk=created["rule"]["id"])
    assert rule.current_spec.records.count() == rule.get_latest_resolved().records.count() == 2
    assert rule.applied_resolved_id == applied_id != rule.get_latest_resolved().pk
    public_context.apply_data_link.assert_not_called()


def test_ascode_limit_failure_keeps_declaration_and_skips_full_cleanup(public_context, settings):
    assert not parse.import_code_config(
        2, "limits-app", {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [config_with_rules(1, "old")]})}
    )
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    public_context.apply_data_link.reset_mock()
    errors = parse.import_code_config(
        2,
        "limits-app",
        {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [config_with_rules(2)]})},
        incremental=False,
    )
    assert "max_rules" in errors["recording_rule/cpu.yaml.groups[0]"]
    assert models.RecordRuleV4.objects.get(name="old").is_deleted is False
    rule = models.RecordRuleV4.objects.get(name="cpu")
    assert rule.current_spec is not None and rule.get_latest_resolved() is not None
    assert rule.applied_resolved_id is None
    public_context.apply_data_link.assert_not_called()


@pytest.mark.parametrize("entry", ["admin", "scheduler"])
def test_admin_and_scheduler_share_apply_limit(public_context, settings, entry):
    from kernel_api.rpc.functions.admin import record_rule_v4 as admin
    from metadata.task.record_rule_v4 import refresh_record_rule_v4

    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    value = config_with_rules(2)
    value["bkmonitor"]["auto_refresh"] = True
    rule_id = call(api.CreateConfigResource, config=value)["rule"]["id"]
    if entry == "admin":
        admin.apply_record_rule_v4({"bk_tenant_id": TENANT_ID, "id": rule_id})
    else:
        refresh_record_rule_v4()
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.get_latest_resolved() is not None
    assert rule.applied_resolved_id is None
    assert "max_rules" in rule.events.order_by("-id").first().message
    public_context.apply_data_link.assert_not_called()
