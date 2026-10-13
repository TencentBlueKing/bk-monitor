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

import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from jsonschema import Draft7Validator

from kernel_api.middlewares import authentication
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.platform_catalog import _authorization, cmdb
from kernel_api.rpc.functions.bkm_cli import unify_query
from kernel_api.rpc.functions.bkm_cli.unify_query import query_unify_query


@pytest.fixture(autouse=True)
def authorized_business(monkeypatch):
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query._authorize_business", lambda bk_biz_id: "system")


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


def _query_promql_params(**overrides):
    params = {
        "promql": "(vector(1)) + (vector(2))",
        "start": "1725062400",
        "end": "1725066000",
        "step": "60s",
    }
    params.update(overrides)
    return params


def _promql_outputs(count=4):
    outputs = [
        {"reference_name": "A", "expression": "vector(1)"},
        {"reference_name": "B", "expression": "vector(2)"},
        {"reference_name": "C", "expression": "vector(9)"},
        {"reference_name": "RESULT", "expression": "(vector(1)) + (vector(2))"},
    ]
    if count == 3:
        return [outputs[0], outputs[1], outputs[3]]
    return outputs[:count]


def _invoke_query_promql(**overrides):
    return query_unify_query(
        {"mode": "invoke", "operation": "query_ts_promql", "bk_biz_id": 2, "params": _query_promql_params(**overrides)}
    )


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
        "query_relation_v1beta3",
        "query_ts",
        "query_ts_promql",
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
            "target_info_show": True,
            "look_back_delta": "1440m",
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


def test_invoke_relation_v1beta3_uses_dedicated_caller_and_keeps_uq_evidence(monkeypatch):
    raw = {"trace_id": "uq-v1beta3", "data": [{"code": 200}, {"code": 400, "message": "binding missing"}]}
    query_relation = Mock(return_value=raw)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi_resource_v1_beta3",
        query_relation,
    )
    query_list = [
        {
            "timestamp": 1725066000,
            "target_type": "pod",
            "source_type": "service",
            "source_info": {"service_name": "api"},
        }
    ]

    out = query_unify_query(
        {"mode": "invoke", "operation": "query_relation_v1beta3", "bk_biz_id": 2, "params": {"query_list": query_list}}
    )

    assert out["status"] == "ok"
    assert out["partial"] is True
    assert out["result"] == raw
    query_relation.assert_called_once_with(bk_biz_ids=["2"], query_list=query_list)


def test_invoke_relation_v1beta3_rejects_unexpected_item_fields(monkeypatch):
    query_relation = Mock()
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi_resource_v1_beta3",
        query_relation,
    )
    query = {"timestamp": 1725066000, "target_type": "pod", "source_type": "service", "source_info": {}}
    for invalid_item in (
        {**query, "space_uid": "bkcc__3"},
        {key: value for key, value in query.items() if key != "source_type"},
    ):
        out = query_unify_query(
            {
                "mode": "invoke",
                "operation": "query_relation_v1beta3",
                "bk_biz_id": 2,
                "params": {"query_list": [invalid_item]},
            }
        )
        assert out["error"]["code"] == "unsafe_action_blocked"
    query_relation.assert_not_called()


def test_invoke_rechecks_nested_business_authorization(monkeypatch):
    request = SimpleNamespace(
        user=SimpleNamespace(tenant_id="tenant-a", is_authenticated=True),
        biz_id=None,
        META={"HTTP_BK_APP_CODE": "test-app"},
    )
    monkeypatch.setattr(_authorization, "get_request", lambda peaceful=True: request)
    monkeypatch.setattr(_authorization, "bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "tenant-a")
    monkeypatch.setattr(authentication, "APP_CODE_TOKENS", {"tenant-a": {"test-app": ["biz#2"]}})
    monkeypatch.setattr(authentication, "APP_CODE_UPDATE_TIME", {"tenant-a": time.time()})
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query._authorize_business", cmdb._authorize_business)
    query_relation = Mock()
    query_ts = Mock()
    query_promql = Mock()
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi_resource_v1_beta3", query_relation
    )
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_ts)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data_by_promql", query_promql
    )

    for operation, params in (
        (
            "query_relation_v1beta3",
            {
                "query_list": [
                    {"timestamp": 1725066000, "target_type": "pod", "source_type": "service", "source_info": {}}
                ]
            },
        ),
        ("query_ts", _query_ts_params()),
        ("query_ts_promql", _query_promql_params()),
    ):
        out = query_unify_query({"mode": "invoke", "operation": operation, "bk_biz_id": 3, "params": params})
        assert out["error"]["code"] == "unsafe_action_blocked"
    query_relation.assert_not_called()
    query_ts.assert_not_called()
    query_promql.assert_not_called()

    query_relation.return_value = {"trace_id": "uq-authorized", "data": []}
    allowed = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_relation_v1beta3",
            "bk_biz_id": 2,
            "params": {
                "query_list": [
                    {"timestamp": 1725066000, "target_type": "pod", "source_type": "service", "source_info": {}}
                ]
            },
        }
    )
    assert allowed["status"] == "ok"
    query_relation.assert_called_once()


def test_describe_relation_schema_includes_expand_and_lookback_fields():
    for operation in ("query_relation_v1", "query_relation_range_v1"):
        out = query_unify_query({"mode": "describe", "operation": operation})
        item_properties = out["params_schema"]["properties"]["query_list"]["items"]["properties"]
        assert "target_info_show" in item_properties
        assert item_properties["target_info_show"]["type"] == "boolean"
        assert "look_back_delta" in item_properties
        assert item_properties["look_back_delta"]["type"] == "string"
        assert out["example_params"]["params"]["query_list"][0]["target_info_show"] is True


def test_invoke_relation_forwards_expand_and_lookback_fields(monkeypatch):
    query_relation = Mock(return_value={"data": [], "trace_id": "uq-relation-expand"})
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_multi",
        query_relation,
    )

    query_list = [
        {
            "timestamp": 1725066000,
            "target_type": "container",
            "source_type": "pod",
            "source_info": {"pod": "api-0"},
            "target_info_show": True,
            "look_back_delta": "1440m",
        }
    ]
    out = query_unify_query(
        {
            "mode": "invoke",
            "operation": "query_relation_v1",
            "bk_biz_id": 2,
            "params": {"query_list": query_list},
        }
    )

    assert out["status"] == "ok"
    query_relation.assert_called_once_with(bk_biz_ids=["2"], query_list=query_list)


def test_relation_caller_serializers_keep_expand_and_lookback_fields():
    from api.unify_query.default import QueryMultiResource, QueryMultiResourceRange
    from kernel_api.resource.relation import (
        QueryMultiResourceRelationRangeResource,
        QueryMultiResourceRelationResource,
    )

    instant_item = {
        "timestamp": 1725066000,
        "target_type": "container",
        "source_info": {"pod": "api-0"},
        "target_info_show": True,
        "look_back_delta": "1440m",
    }
    range_item = {
        "start_time": 1725062400,
        "end_time": 1725066000,
        "step": "60s",
        "target_type": "container",
        "source_info": {"pod": "api-0"},
        "target_info_show": True,
        "look_back_delta": "1440m",
    }
    cases = (
        (QueryMultiResource.RequestSerializer, {"bk_biz_ids": ["2"], "query_list": [instant_item]}),
        (QueryMultiResourceRange.RequestSerializer, {"bk_biz_ids": ["2"], "query_list": [range_item]}),
        (QueryMultiResourceRelationResource.RequestSerializer, {"bk_biz_id": 2, "query_list": [instant_item]}),
        (QueryMultiResourceRelationRangeResource.RequestSerializer, {"bk_biz_id": 2, "query_list": [range_item]}),
    )
    for serializer_cls, payload in cases:
        serializer = serializer_cls(data=payload)
        assert serializer.is_valid(), serializer.errors
        item = serializer.validated_data["query_list"][0]
        assert item["target_info_show"] is True
        assert item["look_back_delta"] == "1440m"


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
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query._authorize_business", lambda bk_biz_id: "system")

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
        "kernel_api.rpc.functions.bkm_cli.unify_query._authorize_business", lambda bk_biz_id: "tenant-a"
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
        "kernel_api.rpc.functions.bkm_cli.unify_query._authorize_business", lambda bk_biz_id: "tenant-a"
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


def test_describe_promql_matches_standard_resource_fields_and_named_contract():
    from api.unify_query.default import QueryDataByPromqlResource

    out = query_unify_query({"mode": "describe", "operation": "query_ts_promql"})
    schema = out["params_schema"]
    serializer = QueryDataByPromqlResource.RequestSerializer()
    assert set(schema["properties"]) == serializer.fields.keys() - {"bk_biz_ids"}
    assert set(schema["required"]) == {name for name, field in serializer.fields.items() if field.required}
    assert out["derived_params"] == ["bk_biz_ids", "bk_tenant_id"]
    assert out["limits"]["max_time_range_seconds"] == 86400
    assert out["limits"]["max_outputs"] == 4
    validator = Draft7Validator(schema)
    assert not list(validator.iter_errors(_query_promql_params()))
    assert not list(validator.iter_errors(out["example_params"]["params"]))
    assert out["example_params"]["params"]["output_list"] == _promql_outputs()
    for field in ("legacy_output_ref", "output_list"):
        incomplete = dict(out["example_params"]["params"])
        incomplete.pop(field)
        assert list(validator.iter_errors(incomplete))
        assert list(validator.iter_errors(_query_promql_params(**{field: out["example_params"]["params"][field]})))


def test_invoke_legacy_promql_keeps_parameters_and_derives_business(monkeypatch):
    raw = {"series": [], "trace_id": "legacy-promql"}
    provider = Mock(return_value=raw)
    authorization = Mock(return_value="system")
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    monkeypatch.setattr(unify_query, "_authorize_business", authorization)

    out = _invoke_query_promql(match='{job="api"}', reference=True, is_verify_dimensions=True)

    assert out["status"] == "ok"
    assert out["result"] is raw
    assert out["partial"] is False
    authorization.assert_called_once_with(2)
    provider.assert_called_once_with(
        **_query_promql_params(match='{job="api"}', reference=True, is_verify_dimensions=True), bk_biz_ids=["2"]
    )


@pytest.mark.parametrize("count", [3, 4])
def test_invoke_named_promql_keeps_output_order_and_raw_response(monkeypatch, count):
    outputs = _promql_outputs(count)
    assert outputs[-1]["reference_name"] == "RESULT"
    assert outputs[-1]["expression"] == _query_promql_params()["promql"]
    raw = {"outputs": [{"reference_name": output["reference_name"], "state": "SUCCESS"} for output in outputs]}
    provider = Mock(return_value=raw)
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    params = {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": outputs,
    }

    out = _invoke_query_promql(**params)

    assert out["status"] == "ok"
    assert out["result"] is raw
    provider.assert_called_once_with(**_query_promql_params(**params), bk_biz_ids=["2"])


@pytest.mark.parametrize("count", [0, 3, 4])
def test_promql_real_resource_posts_standard_fields_to_promql_path(monkeypatch, count):
    from api.unify_query import default
    from django.conf import settings

    raw = {"series": [], "trace_id": "actual-resource-promql"}
    response = Mock(status_code=200)
    response.json.return_value = raw
    http = Mock(return_value=response)
    derive_space = Mock(return_value="bkcc__2")
    monkeypatch.setattr(default.requests, "request", http)
    monkeypatch.setattr(default, "get_request", lambda peaceful=True: None)
    monkeypatch.setattr(default, "bk_biz_id_to_space_uid", derive_space)
    monkeypatch.setattr(default, "space_uid_to_bk_tenant_id", lambda space_uid: "system")
    monkeypatch.setattr(
        default.SpaceApi, "get_space_detail", lambda **kwargs: SimpleNamespace(is_global=False, bk_biz_id=2)
    )
    monkeypatch.setattr(settings, "UNIFY_QUERY_URL", "http://unify-query.test")
    monkeypatch.setattr(settings, "UNIFY_QUERY_ROUTING_RULES", [])
    monkeypatch.setattr(settings, "ENABLE_RESOURCE_DATA_COLLECT", False)
    params = _query_promql_params(timezone="Asia/Shanghai", down_sample_range="", reference=True)
    if count:
        outputs = _promql_outputs(count)
        params.update(response_contract="named_outputs/v1", legacy_output_ref="RESULT", output_list=outputs)

    out = query_unify_query({"mode": "invoke", "operation": "query_ts_promql", "bk_biz_id": 2, "params": params})

    assert out["status"] == "ok", out
    assert out["result"] is raw
    derive_space.assert_called_once_with("2")
    http.assert_called_once_with(
        timeout=60,
        method="POST",
        url="http://unify-query.test/query/ts/promql",
        headers={"Bk-Query-Source": "backend", "X-Bk-Scope-Space-Uid": "bkcc__2", "X-Bk-Tenant-Id": "system"},
        json=params | {"match": "", "is_verify_dimensions": False},
    )


@pytest.mark.parametrize("field", ["space_uid", "bk_biz_ids", "bk_tenant_id", "bk_biz_id", "start_time", "func_name"])
def test_promql_rejects_scope_override_and_unknown_fields_before_provider(monkeypatch, field):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)

    out = _invoke_query_promql(**{field: "caller-supplied"})

    assert out["error"]["code"] == "unsafe_action_blocked"
    assert field in out["error"]["message"]
    assert out["next_call"] == {"mode": "describe", "operation": "query_ts_promql"}
    provider.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("promql", []),
        ("promql", {}),
        ("promql", ""),
        ("match", {}),
        ("step", "60"),
        ("step", "1.5m"),
        ("reference", []),
        ("is_verify_dimensions", {}),
    ],
)
def test_promql_uses_standard_serializer_for_field_validation(monkeypatch, field, value):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)

    out = _invoke_query_promql(**{field: value})

    assert out["error"]["code"] == "unsafe_action_blocked"
    assert field in out["error"]["message"]
    provider.assert_not_called()


@pytest.mark.parametrize("field", ["promql", "start", "end"])
def test_promql_rejects_missing_required_parameters(monkeypatch, field):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    params = _query_promql_params()
    params.pop(field)

    out = query_unify_query({"mode": "invoke", "operation": "query_ts_promql", "bk_biz_id": 2, "params": params})

    assert out["error"]["code"] == "unsafe_action_blocked"
    assert field in out["error"]["message"]
    provider.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"end": "1725148801"},
        {"start": "1725066001"},
        {"start": "nan"},
        {"end": "inf"},
        {"start": "1725062400000", "end": "1725148801000"},
    ],
)
def test_promql_time_range_guard_uses_start_and_end(monkeypatch, overrides):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)

    out = _invoke_query_promql(**overrides)

    assert out["error"]["code"] == "unsafe_action_blocked"
    provider.assert_not_called()


@pytest.mark.parametrize(
    "overrides,named",
    [
        ({"response_contract": "unsupported"}, True),
        ({"legacy_output_ref": "A"}, False),
        ({"output_list": _promql_outputs()}, False),
        ({"legacy_output_ref": "unknown"}, True),
        ({"output_list": []}, True),
        ({"output_list": _promql_outputs() + [{"reference_name": "D", "expression": "vector(4)"}]}, True),
        ({"output_list": [{"reference_name": "A", "expression": "vector(1)"}] * 2}, True),
        ({"output_list": [{"reference_name": "RESULT"}]}, True),
        ({"output_list": [{"reference_name": "RESULT", "expression": "vector(3)", "space_uid": "override"}]}, True),
    ],
)
def test_promql_named_output_contract_is_bounded_and_strict(monkeypatch, overrides, named):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    params = (
        {"response_contract": "named_outputs/v1", "legacy_output_ref": "RESULT", "output_list": _promql_outputs()}
        if named
        else {}
    )
    params.update(overrides)

    out = _invoke_query_promql(**params)

    assert out["error"]["code"] == "unsafe_action_blocked"
    provider.assert_not_called()


def test_promql_request_byte_limit_rejects_before_provider(monkeypatch):
    provider = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)

    out = _invoke_query_promql(promql="x" * unify_query.MAX_REQUEST_BYTES)

    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "字节" in out["error"]["message"]
    provider.assert_not_called()


def test_promql_response_byte_limit_rejects_after_single_provider_call(monkeypatch):
    provider = Mock(return_value={"series": ["x" * 100]})
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    monkeypatch.setattr(unify_query, "MAX_RESPONSE_BYTES", 100)

    out = _invoke_query_promql()

    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "响应" in out["error"]["message"]
    provider.assert_called_once()


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("timeout"), "provider_timeout"),
        (requests.Timeout("timeout"), "provider_timeout"),
        (RuntimeError("unavailable"), "provider_unavailable"),
    ],
)
def test_promql_provider_failures_keep_existing_classification_without_retry(monkeypatch, error, code):
    provider = Mock(side_effect=error)
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)

    out = _invoke_query_promql()

    assert out["error"]["code"] == code
    provider.assert_called_once()


def test_promql_partial_named_response_is_preserved(monkeypatch):
    raw = {
        "trace_id": "promql-partial",
        "outputs": [{"reference_name": "C", "state": "ERROR", "status": {"code": "QUERY_ERROR"}}],
    }
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", Mock(return_value=raw))

    out = _invoke_query_promql(
        response_contract="named_outputs/v1", legacy_output_ref="RESULT", output_list=_promql_outputs()
    )

    assert out["status"] == "ok"
    assert out["partial"] is True
    assert out["result"] is raw
