"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from unittest.mock import Mock

from jsonschema import Draft7Validator

from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.unify_query import query_unify_query


def _query_ts_params(**overrides):
    params = {
        "query_list": [
            {
                "reference_name": "A",
                "data_source": "bkmonitor",
                "table_id": "system.cpu_summary",
                "field_name": "usage",
            }
        ],
        "metric_merge": "A",
        "start_time": "1725062400",
        "end_time": "1725066000",
        "step": "60s",
        "down_sample_range": "",
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "C",
        "output_list": [
            {"reference_name": "A", "expression": "A"},
            {"reference_name": "C", "expression": "A"},
        ],
    }
    params.update(overrides)
    return params


def _query_raw_params(**overrides):
    params = {
        "query_list": [
            {
                "reference_name": "A",
                "data_source": "bkmonitor",
                "table_id": "system.cpu_summary",
                "field_name": "usage",
            }
        ],
        "metric_merge": "A",
        "start_time": "1725062400",
        "end_time": "1725066000",
        "step": "60s",
        "limit": 20,
    }
    params.update(overrides)
    return params


def _invoke_discovery(**overrides):
    params = {"query": "CPU", "page": 1, "page_size": 20}
    params.update(overrides)
    return query_unify_query(
        {"mode": "invoke", "operation": "discover_query_ts_metrics", "bk_biz_id": 2, "params": params}
    )


def _invoke_query_ts(**overrides):
    return query_unify_query(
        {"mode": "invoke", "operation": "query_ts", "bk_biz_id": 2, "params": _query_ts_params(**overrides)}
    )


def _mock_query_ts_response(monkeypatch, raw):
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", Mock(return_value=raw)
    )
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2"
    )


def test_discover_lists_only_server_allowlisted_uq_operations():
    out = query_unify_query({"mode": "discover"})

    assert out["status"] == "ok"
    assert out["kind"] == "discovery"
    assert [operation["id"] for operation in out["operations"]] == [
        "check_query_ts",
        "discover_query_ts_metrics",
        "query_relation_range_v1",
        "query_relation_v1",
        "query_ts",
        "query_ts_raw",
        "query_ts_reference",
    ]
    assert out["meta"]["channel_version"] == "uq-query/v1"
    assert out["meta"]["catalog_revision"]
    discovery = next(operation for operation in out["operations"] if operation["id"] == "discover_query_ts_metrics")
    assert discovery["limits"]["max_page"] == 100
    assert discovery["limits"]["max_page_size"] == 100


def test_describe_returns_external_schema_and_server_derived_scope():
    out = query_unify_query({"mode": "describe", "operation": "query_ts"})

    assert out["status"] == "ok"
    assert out["kind"] == "schema"
    assert out["operation"] == "query_ts"
    assert out["required_params"] == ["bk_biz_id", "params"]
    assert out["derived_params"] == ["space_uid", "bk_tenant_id"]
    assert out["limits"]["max_time_range_seconds"] == 86400
    assert out["limits"]["max_outputs"] == 4
    assert out["params_schema"]["properties"]["response_contract"]["enum"] == ["named_outputs/v1"]
    query_item_schema = out["params_schema"]["properties"]["query_list"]["items"]
    assert set(query_item_schema["required"]) == {"field_name", "reference_name"}
    assert "table_id" in query_item_schema["properties"]
    assert "容器指标可为空" in query_item_schema["properties"]["table_id"]["description"]
    assert out["example_params"]["params"]["legacy_output_ref"] == "C"
    assert all(item.get("expression") for item in out["example_params"]["params"]["output_list"])
    assert out["next_call"]["mode"] == "invoke"
    assert out["next_call"]["params"]["query_list"][0]["table_id"] == "system.cpu_summary"
    query_references = {item["reference_name"] for item in out["next_call"]["params"]["query_list"]}
    assert query_references == {"A"}
    assert out["parameter_sources"]["query_list"] == {"operation": "discover_query_ts_metrics"}


def test_describe_query_ts_schema_matches_named_output_runtime_contract():
    schema = query_unify_query({"mode": "describe", "operation": "query_ts"})["params_schema"]
    validator = Draft7Validator(schema)

    named_params = _query_ts_params()
    assert not list(validator.iter_errors(named_params))
    for missing_field in ("legacy_output_ref", "output_list"):
        invalid_params = dict(named_params)
        invalid_params.pop(missing_field)
        assert list(validator.iter_errors(invalid_params))

    legacy_params = {
        key: value
        for key, value in named_params.items()
        if key not in {"response_contract", "legacy_output_ref", "output_list"}
    }
    assert not list(validator.iter_errors(legacy_params))
    for forbidden_field in ("legacy_output_ref", "output_list"):
        invalid_params = legacy_params | {forbidden_field: named_params[forbidden_field]}
        assert list(validator.iter_errors(invalid_params))


def test_discover_query_ts_metrics_projects_query_template_and_forwards_scope_and_page(monkeypatch):
    metric_resource = Mock(
        return_value={
            "metric_list": [
                {
                    "bk_biz_id": 2,
                    "result_table_id": "system.cpu_summary",
                    "metric_field": "usage",
                    "metric_field_name": "CPU 使用率",
                    "dimensions": [{"id": "bk_target_ip", "name": "目标 IP"}],
                    "data_source_label": "bk_monitor",
                }
            ],
            "count": 21,
        }
    )
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request", metric_resource)

    out = _invoke_discovery(query="CPU 使用率", page=2, page_size=10)

    assert out["status"] == "ok"
    assert out["partial"] is False
    assert "next_actions" not in out
    assert out["result"] | {"items": []} == {
        "items": [],
        "total": 21,
        "page": 2,
        "page_size": 10,
        "has_next": True,
    }
    item = out["result"]["items"][0]
    assert item | {"query_template": {}} == {
        "table_id": "system.cpu_summary",
        "field_name": "usage",
        "dimensions": ["bk_target_ip"],
        "display_name": "CPU 使用率",
        "data_source": "bkmonitor",
        "query_template": {},
    }
    assert item["query_template"]["table_id"] == "system.cpu_summary"
    assert item["query_template"]["field_name"] == "usage"
    assert item["query_template"]["reference_name"] == "A"
    metric_resource.assert_called_once_with(
        bk_biz_id=2,
        data_type_label="time_series",
        conditions=[{"key": "query", "value": ["CPU 使用率"]}],
        page=2,
        page_size=10,
    )


def test_discover_query_ts_metrics_empty_page_returns_narrower_query_guidance(monkeypatch):
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request",
        Mock(return_value={"metric_list": [], "count": 0}),
    )
    first_page = _invoke_discovery()
    later_page = _invoke_discovery(page=3, page_size=5)

    assert first_page["next_actions"] == ["缩短 query 关键词后重试 discover_query_ts_metrics。"]
    assert later_page["result"]["items"] == []
    assert "next_actions" not in later_page["result"]
    assert later_page["next_actions"] == ["减小 page 或缩短 query 后重试 discover_query_ts_metrics。"]


def test_discover_query_ts_metrics_last_allowed_page_never_advertises_next_page(monkeypatch):
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request",
        Mock(return_value={"metric_list": [], "count": 10001}),
    )

    out = _invoke_discovery(page=100, page_size=100)

    assert out["result"]["has_next"] is False


def test_discover_query_ts_metrics_rejects_non_integer_and_out_of_range_page_values(monkeypatch):
    metric_resource = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request", metric_resource)

    for field, value in (
        ("page", True),
        ("page", 1.5),
        ("page", "1"),
        ("page", 101),
        ("page_size", True),
        ("page_size", 1.5),
        ("page_size", "1"),
        ("page_size", 101),
    ):
        params = {"query": "CPU", "page": 1, "page_size": 20, field: value}
        out = _invoke_discovery(**params)

        assert out["status"] == "error"
        assert out["error"]["code"] == "unsafe_action_blocked"
        assert field in out["error"]["message"]
    metric_resource.assert_not_called()


def test_discover_query_ts_metrics_container_template_is_accepted_by_query_ts(monkeypatch):
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request",
        Mock(
            return_value={
                "metric_list": [
                    {
                        "result_table_id": "",
                        "metric_field": "container_cpu_usage_seconds_total",
                        "metric_field_name": "容器 CPU 使用量",
                        "dimensions": [{"id": "pod_name"}],
                        "data_source_label": "bk_monitor",
                    }
                ],
                "count": 1,
            }
        ),
    )
    query_data = Mock(return_value={"series": [], "is_partial": False})
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2"
    )

    discovered = _invoke_discovery(query="container_cpu")
    template = discovered["result"]["items"][0]["query_template"]
    assert template["table_id"] == ""

    out = _invoke_query_ts(query_list=[template])

    assert out["status"] == "ok"
    query_data.assert_called_once_with(**_query_ts_params(query_list=[template], space_uid="bkcc__2"))


def test_all_query_ts_descriptions_include_an_executable_standard_metric_item():
    for operation in ("query_ts", "query_ts_raw", "query_ts_reference", "check_query_ts"):
        out = query_unify_query({"mode": "describe", "operation": operation})

        assert out["status"] == "ok"
        query_item = out["next_call"]["params"]["query_list"][0]
        assert query_item["table_id"] == "system.cpu_summary"
        assert query_item["field_name"] == "usage"
        assert query_item["reference_name"] == "A"


def test_invoke_query_ts_derives_scope_and_preserves_raw_uq_response(monkeypatch):
    raw = {
        "contract_version": "named_outputs/v1",
        "outputs": [
            {
                "reference_name": "A",
                "state": "SUCCESS",
                "series": [{"name": "A", "values": [[1725066000, 1.5]]}],
                "status": {"code": 200, "message": "OK"},
                "is_partial": False,
                "invalid_points": 0,
            }
        ],
        "trace_id": "uq-trace-1",
        "is_partial": False,
    }
    query_data = Mock(return_value=raw)
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2"
    )

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts",
            "bk_biz_id": 2,
            "bk_tenant_id": "system",
            "params": _query_ts_params(),
        }
    )

    assert out["status"] == "ok"
    assert out["kind"] == "invocation"
    assert out["result"] == raw
    assert "next_actions" not in out
    assert "next_call" not in out
    query_data.assert_called_once_with(**_query_ts_params(space_uid="bkcc__2"))


def test_query_ts_partial_missing_metric_returns_server_side_discovery_recovery(monkeypatch):
    raw = {
        "is_partial": True,
        "outputs": [
            {
                "reference_name": "A",
                "state": "PARTIAL",
                "status": {"code": "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS", "message": "query route unavailable"},
            }
        ],
    }
    _mock_query_ts_response(monkeypatch, raw)

    out = _invoke_query_ts()

    assert out["status"] == "ok"
    assert out["partial"] is True
    assert "discover_query_ts_metrics" in " ".join(out["next_actions"])
    assert out["next_call"] == {
        "mode": "invoke",
        "operation": "discover_query_ts_metrics",
        "bk_biz_id": 2,
        "params": {"query": "system.cpu_summary.usage", "page": 1, "page_size": 20},
    }


def test_query_ts_partial_uses_failing_output_reference_for_discovery(monkeypatch):
    raw = {
        "is_partial": True,
        "outputs": [
            {"reference_name": "A", "state": "SUCCESS", "status": {"code": "OK"}},
            {
                "reference_name": "B",
                "state": "PARTIAL",
                "status": {"code": "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS"},
            },
        ],
    }
    _mock_query_ts_response(monkeypatch, raw)
    query_list = _query_ts_params()["query_list"] + [
        {
            "reference_name": "B",
            "data_source": "bkmonitor",
            "table_id": "system.mem",
            "field_name": "pct_used",
        }
    ]

    out = _invoke_query_ts(query_list=query_list)

    assert out["next_call"]["params"]["query"] == "system.mem.pct_used"


def test_query_ts_partial_without_locatable_reference_does_not_fabricate_next_call(monkeypatch):
    raw = {
        "is_partial": True,
        "status": {"code": "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS"},
        "outputs": 1,
    }
    _mock_query_ts_response(monkeypatch, raw)

    out = _invoke_query_ts()

    assert out["partial"] is True
    assert "next_actions" in out
    assert "next_call" not in out


def test_invoke_relation_range_derives_biz_scope(monkeypatch):
    query_relation_range = Mock(return_value={"data": [], "trace_id": "uq-relation-1"})
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi_resource_range",
        query_relation_range,
    )

    query_list = [
        {
            "start_time": 1725062400,
            "end_time": 1725066000,
            "step": "60s",
            "target_type": "pod",
            "source_type": "service",
            "source_info": {"service_name": "api"},
        }
    ]
    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_relation_range_v1",
            "bk_biz_id": 2,
            "params": {"query_list": query_list},
        }
    )

    assert out["status"] == "ok"
    query_relation_range.assert_called_once_with(bk_biz_ids=["2"], query_list=query_list)


def test_relation_partial_is_normalized_in_channel_envelope(monkeypatch):
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi",
        Mock(return_value={"data": [{"code": 200}, {"code": 400, "message": "bad item"}]}),
    )

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_relation_v1",
            "bk_biz_id": 2,
            "params": {
                "query_list": [{"timestamp": 1725066000, "target_type": "pod", "source_info": {"service_name": "api"}}]
            },
        }
    )

    assert out["status"] == "ok"
    assert out["partial"] is True
    assert "next_call" not in out


def test_invoke_rejects_operation_outside_catalog():
    out = query_unify_query({"mode": "invoke", "operation": "delete_everything", "bk_biz_id": 2, "params": {}})

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"


def test_invoke_rejects_caller_supplied_scope_fields():
    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts",
            "bk_biz_id": 2,
            "params": _query_ts_params(space_uid="bkcc__3"),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "space_uid" in out["error"]["message"]


def test_invoke_rejects_params_outside_described_schema(monkeypatch):
    query_raw = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_raw", query_raw)

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts_raw",
            "bk_biz_id": 2,
            "params": _query_raw_params(response_contract="named_outputs/v1"),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "response_contract" in out["error"]["message"]
    query_raw.assert_not_called()


def test_invoke_rejects_incomplete_named_output_contract(monkeypatch):
    query_data = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts",
            "bk_biz_id": 2,
            "params": _query_ts_params(output_list=[{"reference_name": "C"}]),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "expression" in out["error"]["message"]
    assert out["next_call"] == {"mode": "describe", "operation": "query_ts"}
    query_data.assert_not_called()


def test_service_bridge_rejects_tenant_override(monkeypatch):
    metric_resource = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request", metric_resource)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "system"
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "query-unify-query",
            "params": {
                "mode": "invoke",
                "operation": "discover_query_ts_metrics",
                "bk_biz_id": 2,
                "bk_tenant_id": "other",
                "params": {"query": "CPU", "page": 1, "page_size": 20},
            },
        }
    )

    assert result["result"]["status"] == "error"
    assert result["result"]["error"]["code"] == "unsafe_action_blocked"
    assert "bk_tenant_id" in result["result"]["error"]["message"]
    metric_resource.assert_not_called()


def test_discover_query_ts_metrics_rejects_request_tenant_conflict(monkeypatch):
    metric_resource = Mock()
    request_tenant = Mock(return_value="tenant-b")
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request", metric_resource)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "tenant-a"
    )
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.get_request_tenant_id", request_tenant)

    out = _invoke_discovery()

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "租户" in out["error"]["message"]
    request_tenant.assert_called_once_with(peaceful=True)
    metric_resource.assert_not_called()


def test_discover_query_ts_metrics_rejects_missing_request_tenant(monkeypatch):
    metric_resource = Mock(return_value={"metric_list": [], "count": 0})
    request_tenant = Mock(return_value=None)
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.GetMetricListV2Resource.request", metric_resource)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "tenant-a"
    )
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.get_request_tenant_id", request_tenant)

    out = _invoke_discovery()

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "租户" in out["error"]["message"]
    request_tenant.assert_called_once_with(peaceful=True)
    metric_resource.assert_not_called()


def test_invoke_rejects_time_range_over_24_hours(monkeypatch):
    query_data = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts",
            "bk_biz_id": 2,
            "params": _query_ts_params(end_time="1725152401"),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    query_data.assert_not_called()


def test_invoke_rejects_non_finite_timestamp(monkeypatch):
    query_data = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)

    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts",
            "bk_biz_id": 2,
            "params": _query_ts_params(start_time=float("nan")),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    query_data.assert_not_called()


def test_invoke_rejects_oversized_query_list(monkeypatch):
    query_raw = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_raw", query_raw)

    too_many_queries = [{"field_name": f"metric_{index}"} for index in range(21)]
    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_ts_raw",
            "bk_biz_id": 2,
            "params": _query_raw_params(query_list=too_many_queries),
        }
    )

    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    query_raw.assert_not_called()


def test_invoke_rejects_raw_limit_outside_schema_bounds(monkeypatch):
    query_raw = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_raw", query_raw)

    for limit in (0, 101):
        out = query_unify_query(
            {
                "mode": "invoke",
                "operation": "query_ts_raw",
                "bk_biz_id": 2,
                "params": _query_raw_params(limit=limit),
            }
        )

        assert out["status"] == "error"
        assert out["error"]["code"] == "unsafe_action_blocked"

    query_raw.assert_not_called()


def test_query_unify_query_is_registered_for_bkm_cli_service_bridge():
    op = BkmCliOpRegistry.resolve("query-unify-query")
    assert op.func_name == "bkm_cli.query_unify_query"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"

    detail = KernelRPCRegistry.get_function_detail("bkm_cli.query_unify_query")
    assert detail["func_name"] == "bkm_cli.query_unify_query"
