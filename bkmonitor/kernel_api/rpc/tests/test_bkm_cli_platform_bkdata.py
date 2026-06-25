"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

bkdata domain 单测：params_guard 框架钩子（拦截映射 / 归一化透传 / 无 guard 回归）、
query_data SQL 防线允许/拒绝矩阵、get_result_table URL 路径值校验、
describe 输出不泄漏 RequestSerializer 隐藏参数、未注册 operation 拒绝。
"""

from __future__ import annotations

import json

import pytest

from kernel_api.rpc.functions.bkm_cli.platform_catalog import bkdata
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import (
    OperationSpec,
    ParamsGuardRejected,
    PlatformSourceCatalog,
)
from kernel_api.rpc.functions.bkm_cli.platform_source import query_platform_source


@pytest.fixture(autouse=True)
def isolated_catalog():
    """每个测试独立的 catalog 状态。"""
    snapshot = dict(PlatformSourceCatalog._domains)
    PlatformSourceCatalog.reset()
    yield
    PlatformSourceCatalog._domains = snapshot
    PlatformSourceCatalog._revision = None


def _stub_handler(**kwargs):
    return {"echoed": kwargs}


# ---------- params_guard 框架钩子 ----------


def test_params_guard_rejection_maps_to_unsafe_action_blocked():
    def deny_all(params):
        raise ParamsGuardRejected("blocked by guard")

    op = OperationSpec(id="get_thing", summary="s", handler=_stub_handler, params_guard=deny_all)
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain1", "operation": "get_thing", "params": {"x": 1}})
    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert "blocked by guard" in out["error"]["message"]


def test_params_guard_normalized_params_reach_handler():
    def normalize(params):
        return {"x": params["x"], "added": True}

    op = OperationSpec(id="get_thing", summary="s", handler=_stub_handler, params_guard=normalize)
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain1", "operation": "get_thing", "params": {"x": 1}})
    assert out["status"] == "ok"
    assert out["result"] == {"echoed": {"x": 1, "added": True}}


def test_operation_without_params_guard_passes_params_through():
    op = OperationSpec(id="get_thing", summary="s", handler=_stub_handler)
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain1", "operation": "get_thing", "params": {"x": 1}})
    assert out["status"] == "ok"
    assert out["result"] == {"echoed": {"x": 1}}


def test_non_callable_params_guard_rejected_at_registration():
    with pytest.raises(ValueError, match="params_guard"):
        OperationSpec(id="get_thing", summary="s", handler=_stub_handler, params_guard="not-callable")


# ---------- guard_query_data 允许/拒绝矩阵 ----------


def test_guard_query_data_accepts_minimal_select():
    out = bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10"})
    assert out == {"sql": "SELECT a FROM t LIMIT 10"}


def test_guard_query_data_accepts_lowercase_and_newlines():
    sql = "select dtEventTime, localTime\nfrom t\nwhere a = 1\norder by dtEventTime\nlimit\n100"
    out = bkdata.guard_query_data({"sql": sql})
    assert out["sql"].endswith("100")


def test_guard_query_data_strips_single_trailing_semicolon():
    out = bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10;"})
    assert out["sql"] == "SELECT a FROM t LIMIT 10"


def test_guard_query_data_keeps_prefer_storage():
    out = bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10", "prefer_storage": "tspider"})
    assert out["prefer_storage"] == "tspider"


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE t SET a = 1 LIMIT 10",
        "DELETE FROM t LIMIT 10",
        "DROP TABLE t LIMIT 10",
        "WITH x AS (SELECT 1) SELECT * FROM x LIMIT 10",
    ],
)
def test_guard_query_data_rejects_non_select(sql):
    with pytest.raises(ParamsGuardRejected, match="SELECT"):
        bkdata.guard_query_data({"sql": sql})


def test_guard_query_data_rejects_multi_statement():
    with pytest.raises(ParamsGuardRejected, match="单条语句"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10; DROP TABLE t"})


@pytest.mark.parametrize(
    "sql",
    ["SELECT a -- c FROM t LIMIT 10", "SELECT /*x*/ a FROM t LIMIT 10", "SELECT a FROM t WHERE b = '#tag' LIMIT 10"],
)
def test_guard_query_data_rejects_comment_tokens_even_in_string_literals(sql):
    with pytest.raises(ParamsGuardRejected, match="注释"):
        bkdata.guard_query_data({"sql": sql})


def test_guard_query_data_rejects_select_into():
    with pytest.raises(ParamsGuardRejected, match="INTO"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t INTO OUTFILE '/tmp/x' LIMIT 10"})


def test_guard_query_data_rejects_missing_trailing_limit():
    with pytest.raises(ParamsGuardRejected, match="LIMIT"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t"})


def test_guard_query_data_rejects_subquery_only_limit():
    # 子查询带 LIMIT 但外层无界，不能过关
    with pytest.raises(ParamsGuardRejected, match="LIMIT"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t WHERE x IN (SELECT y FROM u LIMIT 5)"})


def test_guard_query_data_rejects_limit_offset_forms():
    with pytest.raises(ParamsGuardRejected, match="LIMIT"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10 OFFSET 5"})


def test_guard_query_data_rejects_oversized_limit():
    with pytest.raises(ParamsGuardRejected, match=str(bkdata.MAX_SQL_LIMIT)):
        bkdata.guard_query_data({"sql": f"SELECT a FROM t LIMIT {bkdata.MAX_SQL_LIMIT + 1}"})


def test_guard_query_data_accepts_max_limit_boundary():
    out = bkdata.guard_query_data({"sql": f"SELECT a FROM t LIMIT {bkdata.MAX_SQL_LIMIT}"})
    assert out["sql"].endswith(str(bkdata.MAX_SQL_LIMIT))


@pytest.mark.parametrize("params", [{}, {"sql": ""}, {"sql": "   "}, {"sql": 123}])
def test_guard_query_data_rejects_missing_or_non_string_sql(params):
    with pytest.raises(ParamsGuardRejected, match="sql"):
        bkdata.guard_query_data(params)


@pytest.mark.parametrize(
    "params",
    [
        {"sql": "SELECT a FROM t LIMIT 10", "_user_request": True},
        {"sql": "SELECT a FROM t LIMIT 10", "bkdata_authentication_method": "user"},
        {"sql": "SELECT a FROM t LIMIT 10", "fields": ["a"]},
    ],
)
def test_guard_query_data_rejects_undeclared_keys(params):
    with pytest.raises(ParamsGuardRejected, match="未声明参数"):
        bkdata.guard_query_data(params)


def test_guard_query_data_rejects_non_string_prefer_storage():
    with pytest.raises(ParamsGuardRejected, match="prefer_storage"):
        bkdata.guard_query_data({"sql": "SELECT a FROM t LIMIT 10", "prefer_storage": ["tspider"]})


# ---------- guard_get_result_table ----------


def test_guard_get_result_table_accepts_valid_id():
    out = bkdata.guard_get_result_table({"result_table_id": "2_demo_table"})
    assert out == {"result_table_id": "2_demo_table"}


def test_guard_get_result_table_keeps_valid_related():
    out = bkdata.guard_get_result_table({"result_table_id": "2_demo_table", "related": ["fields", "storages"]})
    assert out["related"] == ["fields", "storages"]


@pytest.mark.parametrize(
    "result_table_id",
    ["../../v3/other", "a?x=1", "a/b", "a b", "{result_table_id}", "", None, 123],
)
def test_guard_get_result_table_rejects_url_unsafe_values(result_table_id):
    with pytest.raises(ParamsGuardRejected, match="result_table_id"):
        bkdata.guard_get_result_table({"result_table_id": result_table_id})


def test_guard_get_result_table_rejects_bad_related():
    with pytest.raises(ParamsGuardRejected, match="related"):
        bkdata.guard_get_result_table({"result_table_id": "2_demo_table", "related": ["fields", "a/b"]})


def test_guard_get_result_table_rejects_undeclared_keys():
    with pytest.raises(ParamsGuardRejected, match="未声明参数"):
        bkdata.guard_get_result_table({"result_table_id": "2_demo_table", "extra": 1})


# ---------- bkdata domain 注册与端到端 ----------


def test_bkdata_domain_registers_with_two_readonly_operations():
    bkdata.register()
    out = query_platform_source({"mode": "discover"})
    assert [d["id"] for d in out["domains"]] == ["bkdata"]
    assert out["domains"][0]["operations_count"] == 2
    assert "readonly" in out["domains"][0]["audit_tags"]

    ops = query_platform_source({"mode": "discover", "domain": "bkdata"})
    assert [o["id"] for o in ops["operations"]] == ["get_result_table", "query_data"]


@pytest.mark.parametrize("operation", ["query_data", "get_result_table"])
def test_bkdata_describe_does_not_expose_hidden_serializer_params(operation):
    bkdata.register()
    out = query_platform_source({"mode": "describe", "domain": "bkdata", "operation": operation})
    assert out["status"] == "ok"
    serialized = json.dumps(out, ensure_ascii=False)
    assert "_user_request" not in serialized
    assert "bkdata_authentication_method" not in serialized


def test_bkdata_invoke_write_sql_blocked_before_handler():
    bkdata.register()
    out = query_platform_source(
        {
            "mode": "invoke",
            "domain": "bkdata",
            "operation": "query_data",
            "params": {"sql": "UPDATE t SET a = 1 LIMIT 10"},
        }
    )
    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"


def test_bkdata_invoke_unregistered_operation_blocked():
    # P0 收口：未注册的能力（如 dmonitor 指标查询）由 catalog 机器强制拒绝
    bkdata.register()
    out = query_platform_source(
        {"mode": "invoke", "domain": "bkdata", "operation": "query_dmonitor_output_count", "params": {}}
    )
    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    # 锁定走的是 operation-missing 分支（domain 本身已注册），防 register 回归时假阳性
    assert "query_dmonitor_output_count" in out["error"]["message"]
