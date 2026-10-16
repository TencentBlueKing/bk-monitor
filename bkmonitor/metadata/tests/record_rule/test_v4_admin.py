"""Admin configuration RPCs save declarations without executing them."""

from copy import deepcopy

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import record_rule_v4 as rpc
from kernel_api.rpc.registry import KernelRPCRegistry
from metadata.models import Space
from metadata.models.record_rule.v4.models import RecordRuleV4

pytestmark = pytest.mark.django_db(databases="__all__")
TENANT = "record_rule_admin_test"


@pytest.fixture
def declaration_context(mocker):
    Space.objects.create(bk_tenant_id=TENANT, space_type_id="bkcc", space_id="7722", space_name="Admin test")
    mocker.patch(
        "metadata.models.record_rule.v4.output.RecordRuleV4OutputResources.compose_vm_result_table_id",
        return_value="7722_test_output",
    )
    execute = mocker.patch.object(rpc.RecordRuleV4Operator, "execute_declaration")
    resolve = mocker.patch.object(rpc.RecordRuleV4Operator, "refresh_resolved")
    prepare = mocker.patch.object(rpc.RecordRuleV4Operator, "prepare_output_resources")
    yield
    execute.assert_not_called()
    resolve.assert_not_called()
    prepare.assert_not_called()


def create_rule():
    return rpc.create_record_rule_v4(
        {"bk_tenant_id": TENANT, "space_uid": "bkcc__7722", "config": deepcopy(rpc.CONFIG_EXAMPLE), "operator": "alice"}
    )["data"]


def test_create_and_read_config(declaration_context):
    data = create_rule()
    rule = RecordRuleV4.objects.get(pk=data["rule"]["id"])
    assert rule.generation == 1
    assert rule.current_spec.operator == "alice"
    assert rule.resolved.count() == 0
    assert rule.flows.count() == 0
    assert data["config"]["rules"] == rpc.CONFIG_EXAMPLE["rules"]
    result = rpc.get_record_rule_v4_config({"bk_tenant_id": TENANT, "id": rule.pk})
    assert result["data"] == data
    assert result["meta"]["safety_level"] == "read"


def test_metadata_then_rule_update_preserves_version_semantics(declaration_context):
    created = create_rule()
    rule_id = created["rule"]["id"]
    config = deepcopy(created["config"])
    config["bkmonitor"].update(description="changed", auto_refresh=False, desired_status="stopped")
    updated = rpc.update_record_rule_v4({"bk_tenant_id": TENANT, "id": rule_id, "config": config})
    assert updated["meta"]["safety_level"] == "write"
    assert updated["data"]["rule"]["generation"] == 1
    assert updated["data"]["config"]["bkmonitor"] == config["bkmonitor"]
    # A new spec is needed only for a declaration change, not a metadata edit.
    config["rules"][0]["expr"] = "sum(system_cpu_usage)"
    updated = rpc.update_record_rule_v4({"bk_tenant_id": TENANT, "id": rule_id, "config": config})["data"]
    assert updated["rule"]["generation"] == 2
    assert updated["config"] == config
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.events.filter(event_type="user.spec_changed").exists()
    assert rule.resolved.count() == 0


def test_query_and_promql_records_round_trip(declaration_context):
    config = deepcopy(rpc.CONFIG_EXAMPLE)
    config["rules"].append(
        {
            "record": "cpu_query",
            "query": {
                "data_source": "bk_monitor",
                "data_type": "time_series",
                "expression": "a",
                "query_configs": [{"metric": "system.cpu.usage", "method": "avg", "interval": 60, "alias": "a"}],
            },
        }
    )
    data = rpc.create_record_rule_v4({"bk_tenant_id": TENANT, "space_uid": "bkcc__7722", "config": config})["data"]
    rule = RecordRuleV4.objects.get(pk=data["rule"]["id"])
    assert [record.input_type for record in rule.current_spec.get_records()] == ["promql", "query_ts"]
    assert data["config"]["rules"][1]["query"]["query_configs"][0]["metric"] == "system.cpu.usage"


def test_requires_explicit_tenant_and_owns_space(declaration_context):
    for tenant in [None, "another_tenant"]:
        with pytest.raises(CustomException):
            rpc.create_record_rule_v4({"bk_tenant_id": tenant, "space_uid": "bkcc__7722", "config": rpc.CONFIG_EXAMPLE})
    created = create_rule()
    for function in [rpc.get_record_rule_v4_config, rpc.update_record_rule_v4]:
        with pytest.raises(CustomException):
            function({"bk_tenant_id": "another_tenant", "id": created["rule"]["id"], "config": created["config"]})


def test_rejects_renaming_and_editing_deleted_rule(declaration_context):
    created = create_rule()
    config = deepcopy(created["config"])
    config["name"] = "renamed"
    params = {"bk_tenant_id": TENANT, "id": created["rule"]["id"], "config": config}
    with pytest.raises(CustomException, match="名称不可修改"):
        rpc.update_record_rule_v4(params)
    config["name"] = created["config"]["name"]
    RecordRuleV4.objects.filter(pk=params["id"]).update(desired_status="deleted")
    with pytest.raises(CustomException, match="不能编辑"):
        rpc.update_record_rule_v4(params)
    assert rpc.get_record_rule_v4_config(params)["data"]["config"]["bkmonitor"]["desired_status"] == "deleted"


def test_bad_config_does_not_create_rule(declaration_context):
    config = deepcopy(rpc.CONFIG_EXAMPLE)
    config["rules"][0]["query"] = {}
    before = RecordRuleV4.objects.count()
    with pytest.raises(CustomException):
        rpc.create_record_rule_v4({"bk_tenant_id": TENANT, "space_uid": "bkcc__7722", "config": config})
    assert RecordRuleV4.objects.count() == before


def test_rpc_metadata_exposes_machine_readable_config_schema():
    for action in ["config", "create", "update"]:
        detail = KernelRPCRegistry._functions[f"admin.record_rule_v4.{action}"].to_detail()
        assert detail["params_schema"]["type"] == "object"
        assert "bk_tenant_id" in detail["params_schema"]["required"]
        assert detail["example_params"]["bk_tenant_id"] == "system"
