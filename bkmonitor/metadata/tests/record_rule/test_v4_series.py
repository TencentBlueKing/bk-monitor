"""下发前 series 检查与管理员许可。"""

import copy

import pytest
import requests
import yaml
from django.test import TestCase

from api.unify_query.default import QueryDataByPromqlResource, QueryDataResource
from bkmonitor.as_code import parse, recording_rule
from kernel_api.resource import recording_rule as api
from metadata import config
from metadata.models.record_rule.v4.models import RecordRuleV4
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator
from metadata.models.record_rule.v4.series import read_series_count
from metadata.task.tasks import sync_as_code_recording_rules
from metadata.tests.record_rule.test_v4_operator import (
    TENANT_ID,
    build_record,
    build_structured_query_config,
    declare_rule,
    external_api as _external_api,
    v4_base_data as _v4_base_data,
)
from metadata.tests.record_rule.test_v4_public_api import call, group, public_context as _public_context

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context
pytestmark = pytest.mark.django_db(databases="__all__")


def count_result(count):
    return {"series": [{"columns": ["_time", "_value"], "values": [[1700000000, count]]}]}


@pytest.mark.parametrize("count,allowed", [(499999, True), (500000, True), (500001, False)])
def test_series_boundaries(public_context, count, allowed):
    public_context.query_promql.return_value = count_result(count)
    result = call(api.CreateConfigResource, config=group(), apply=True)
    assert result["saved"]
    assert result["execution"]["succeeded"] is allowed
    assert public_context.apply_data_link.called is allowed
    if not allowed:
        message = result["execution"]["error"]
        for text in ("cpu", "cpu_avg", "promql_metricql", "500001", "500000", "联系监控管理员"):
            assert text in message


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"series": None},
        {"series": [], "is_partial": True},
        {"series": [], "status": {"is_partial": True}},
        {"series": [], "status": {"series_limit_reached": True}},
        count_result(None),
        count_result("NaN"),
        count_result("Inf"),
        count_result(-1),
    ],
)
def test_invalid_or_partial_result_blocks_apply(public_context, response):
    public_context.query_promql.return_value = response
    result = call(api.CreateConfigResource, config=group(), apply=True)
    assert not result["execution"]["succeeded"]
    assert "请重试" in result["execution"]["error"]
    public_context.apply_data_link.assert_not_called()


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), RuntimeError("query failed")])
def test_failed_query_can_be_retried(public_context, error):
    public_context.query_promql.side_effect = error
    result = call(api.CreateConfigResource, config=group(), apply=True)
    assert not result["execution"]["succeeded"]
    public_context.apply_data_link.assert_not_called()
    public_context.query_promql.side_effect = None
    public_context.query_promql.return_value = {"series": []}
    assert call(api.ApplyConfigResource, id=result["rule"]["id"])["execution"]["succeeded"]


def test_same_instant_and_first_over_limit_stops_group(public_context, mocker):
    mocker.patch("metadata.models.record_rule.v4.series.time.time", return_value=1700000000)
    value = group()
    value["rules"] = [{"record": f"cpu_{i}", "expr": f"sum(cpu_{i})"} for i in range(3)]
    public_context.query_promql.side_effect = [count_result(1), count_result(500001)]
    result = call(api.CreateConfigResource, config=value, apply=True)
    assert not result["execution"]["succeeded"]
    assert public_context.query_promql.call_count == 2
    for i, invocation in enumerate(public_context.query_promql.call_args_list):
        params = invocation.kwargs
        assert params["promql"] == f"count(sum(cpu_{i})\n)"
        assert params["start"] == params["end"] == "1700000000"
        assert params["instant"] is True
        assert params["space_uid"] == "bkcc__2"
        assert params["bk_tenant_id"] == TENANT_ID
        validated = QueryDataByPromqlResource().validate_request_data(params)
        assert validated["instant"] and validated["space_uid"] == "bkcc__2"
    public_context.apply_data_link.assert_not_called()


def test_structured_query_counts_complete_expression(public_context, mocker):
    mocker.patch("metadata.models.record_rule.v4.series.time.time", return_value=1700000000)
    input_config = build_structured_query_config()
    original = copy.deepcopy(input_config)
    rule = declare_rule(records=[build_record(input_config=input_config)])
    assert RecordRuleV4Operator(rule).execute_declaration()
    params = public_context.query_ts.call_args.kwargs
    assert params["metric_merge"] == "count(a / b\n)"
    assert len(params["query_list"]) == 2
    assert params["start_time"] == params["end_time"] == "1700000000"
    assert params["space_uid"] == "bkcc__2" and params["bk_tenant_id"] == TENANT_ID
    validated = QueryDataResource().validate_request_data(params)
    assert validated["instant"] and validated["bk_tenant_id"] == TENANT_ID
    assert input_config == original
    public_context.query_promql.assert_not_called()


def test_exemption_is_dynamic_and_other_limits_still_apply(public_context, settings):
    public_context.query_promql.return_value = count_result(500001)
    rule_id = call(api.CreateConfigResource, config=group())["rule"]["id"]
    settings.RECORD_RULE_V4_CONFIG = {"series_exempt_rule_ids": [rule_id]}
    assert call(api.ApplyConfigResource, id=rule_id)["execution"]["succeeded"]
    public_context.query_promql.assert_not_called()
    settings.RECORD_RULE_V4_CONFIG = {"series_exempt_rule_ids": [rule_id], "max_rules": 1}
    value = group()
    value["rules"].append({"record": "second", "expr": "sum(cpu)"})
    assert not call(api.UpdateConfigResource, id=rule_id, config=value, apply=True)["execution"]["succeeded"]
    settings.RECORD_RULE_V4_CONFIG = {"series_exempt_rule_ids": [rule_id]}
    assert call(api.ApplyConfigResource, id=rule_id)["execution"]["succeeded"]
    public_context.query_promql.assert_not_called()
    settings.RECORD_RULE_V4_CONFIG = {"series_exempt_rule_ids": []}
    assert not call(api.ApplyConfigResource, id=rule_id, series_exempt_rule_ids=[rule_id])["execution"]["succeeded"]
    settings.RECORD_RULE_V4_CONFIG = {"max_series": 500001}
    assert call(api.ApplyConfigResource, id=rule_id)["execution"]["succeeded"]


def test_save_and_preview_do_not_query(public_context):
    call(api.PreviewConfigResource, config=group())
    call(api.CreateConfigResource, config=group())
    public_context.query_promql.assert_not_called()
    public_context.query_ts.assert_not_called()


def test_rejected_update_preserves_running_flow_and_stop_delete_skip_query(public_context):
    created = call(api.CreateConfigResource, config=group(), apply=True)
    rule_id, applied_id = created["rule"]["id"], created["rule"]["applied_resolved_id"]
    public_context.query_promql.return_value = count_result(500001)
    value = group()
    value["rules"][0]["expr"] = "sum(changed_cpu)"
    updated = call(api.UpdateConfigResource, id=rule_id, config=value, apply=True)
    assert updated["saved"] and not updated["execution"]["succeeded"]
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.applied_resolved_id == applied_id
    assert rule.current_spec_id != rule.applied_resolved.spec_id
    public_context.apply_data_link.reset_mock()
    public_context.query_promql.reset_mock()
    # 运行态操作针对 applied Flow，而不是尚未成功下发的新声明。
    rule.desired_status = "stopped"
    rule.save(update_fields=["desired_status"])
    runner = RecordRuleV4Operator(rule).runner
    assert runner.apply_desired_status("stopped")
    public_context.query_promql.assert_not_called()
    rule.desired_status = "running"
    rule.save(update_fields=["desired_status"])
    assert not runner.apply_desired_status("running")
    assert public_context.query_promql.call_args.kwargs["promql"] == "count(avg(system_cpu_usage)\n)"
    public_context.query_promql.reset_mock()
    assert call(api.DeleteConfigResource, id=rule_id)["execution"]["succeeded"]
    public_context.query_promql.assert_not_called()
    public_context.delete_data_link.assert_called_once()


@pytest.mark.parametrize("entry", ["admin", "scheduler", "ascode"])
def test_all_apply_entries_enforce_series_limit(public_context, mocker, entry):
    from kernel_api.rpc.functions.admin import record_rule_v4 as admin
    from metadata.task.record_rule_v4 import refresh_record_rule_v4

    public_context.query_promql.return_value = count_result(500001)
    value = group()
    value["bkmonitor"]["auto_refresh"] = True
    if entry == "ascode":
        send_task = mocker.patch.object(recording_rule.api.metadata, "sync_as_code_recording_rules")
        with TestCase.captureOnCommitCallbacks(using=config.DATABASE_CONNECTION_NAME, execute=True):
            assert not parse.import_code_config(
                2, "series-app", {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [value]})}
            )
        sync_as_code_recording_rules(**send_task.call_args.kwargs)
    else:
        rule_id = call(api.CreateConfigResource, config=value)["rule"]["id"]
        if entry == "admin":
            admin.apply_record_rule_v4({"bk_tenant_id": TENANT_ID, "id": rule_id})
        else:
            refresh_record_rule_v4()
    rule = RecordRuleV4.objects.get(name="cpu")
    assert rule.applied_resolved_id is None
    assert "500001" in rule.events.order_by("-id").first().message
    public_context.apply_data_link.assert_not_called()


def test_count_is_sample_value_not_number_of_rows():
    assert read_series_count(count_result(500001)) == 500001
    assert read_series_count({"series": []}) == 0


def test_zero_threshold_skips_query_but_preserves_other_limits(public_context, settings):
    settings.RECORD_RULE_V4_CONFIG = {"max_series": 0, "max_rules": 1}
    public_context.query_promql.side_effect = requests.Timeout("must not query")
    created = call(api.CreateConfigResource, config=group(), apply=True)
    assert created["execution"]["succeeded"]
    public_context.query_promql.assert_not_called()
    value = group()
    value["rules"].append({"record": "second", "expr": "sum(cpu)"})
    updated = call(api.UpdateConfigResource, id=created["rule"]["id"], config=value, apply=True)
    assert not updated["execution"]["succeeded"]
    assert "max_rules" in updated["execution"]["error"]
    public_context.query_promql.assert_not_called()
