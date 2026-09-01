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

from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.unify_query import query_unify_query


def _query_ts_params(**overrides):
    params = {
        "query_list": [{"reference_name": "A", "data_source": "bkmonitor", "field_name": "usage"}],
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
        "query_list": [{"data_source": "bkmonitor", "field_name": "usage"}],
        "metric_merge": "A",
        "start_time": "1725062400",
        "end_time": "1725066000",
        "step": "60s",
        "limit": 20,
    }
    params.update(overrides)
    return params


def test_discover_lists_only_server_allowlisted_uq_operations():
    out = query_unify_query({"mode": "discover"})

    assert out["status"] == "ok"
    assert out["kind"] == "discovery"
    assert [operation["id"] for operation in out["operations"]] == [
        "check_query_ts",
        "query_relation_range_v1",
        "query_relation_v1",
        "query_ts",
        "query_ts_raw",
        "query_ts_reference",
    ]
    assert out["meta"]["channel_version"] == "uq-query/v1"
    assert out["meta"]["catalog_revision"]


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
    assert out["example_params"]["params"]["legacy_output_ref"] == "C"
    assert all(item.get("expression") for item in out["example_params"]["params"]["output_list"])
    assert out["next_call"]["mode"] == "invoke"
    query_references = {item["reference_name"] for item in out["next_call"]["params"]["query_list"]}
    assert query_references == {"A"}


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
    query_data.assert_called_once_with(**_query_ts_params(space_uid="bkcc__2"))


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
    query_data.assert_not_called()


def test_service_bridge_rejects_tenant_override(monkeypatch):
    query_data = Mock()
    monkeypatch.setattr("kernel_api.rpc.functions.bkm_cli.unify_query.api.unify_query.query_data", query_data)
    monkeypatch.setattr(
        "kernel_api.rpc.functions.bkm_cli.unify_query.bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "system"
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "query-unify-query",
            "params": {
                "mode": "invoke",
                "operation": "query_ts",
                "bk_biz_id": 2,
                "bk_tenant_id": "other",
                "params": _query_ts_params(),
            },
        }
    )

    assert result["result"]["status"] == "error"
    assert result["result"]["error"]["code"] == "unsafe_action_blocked"
    assert "bk_tenant_id" in result["result"]["error"]["message"]
    query_data.assert_not_called()


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
