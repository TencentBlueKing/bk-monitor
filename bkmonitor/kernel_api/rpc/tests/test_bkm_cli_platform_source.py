"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

bkm_cli.query_platform_source 单测：覆盖 discover/describe/invoke 三阶段、错误码、
catalog 准入规则、invoke_style、force_refresh 透传。
"""

from __future__ import annotations

import pytest

from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import (
    OperationSpec,
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


# ---------- discover ----------


def test_discover_empty_catalog_returns_empty_domains():
    out = query_platform_source({"mode": "discover"})
    assert out["status"] == "ok"
    assert out["kind"] == "discovery"
    assert out["scope"] == "domains"
    assert out["domains"] == []
    assert out["next_call"]["mode"] == "discover"
    assert "catalog_revision" in out["meta"]
    assert out["meta"]["usage_flow"]


def test_default_mode_is_discover():
    out = query_platform_source({})
    assert out["status"] == "ok"
    assert out["kind"] == "discovery"


def test_discover_lists_registered_domain():
    PlatformSourceCatalog.register_domain(
        id="cmdb_test", summary="test domain", audit_tags=["readonly", "cmdb"], operations=[]
    )
    out = query_platform_source({"mode": "discover"})
    assert len(out["domains"]) == 1
    assert out["domains"][0]["id"] == "cmdb_test"
    assert out["domains"][0]["operations_count"] == 0
    assert "readonly" in out["domains"][0]["audit_tags"]


def test_discover_operations_lists_summaries():
    op = OperationSpec(
        id="get_thing",
        summary="get a thing",
        handler=_stub_handler,
        required_params=["thing_id"],
        audit_tags=["readonly"],
    )
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "discover", "domain": "domain1"})
    assert out["status"] == "ok"
    assert out["scope"] == "operations"
    assert out["operations"][0]["id"] == "get_thing"
    assert out["operations"][0]["required_params"] == ["thing_id"]


def test_domain_case_is_normalized():
    PlatformSourceCatalog.register_domain(id="cmdb_test", summary="t", audit_tags=["readonly"], operations=[])
    out = query_platform_source({"mode": "discover", "domain": "CMDB_TEST"})
    assert out["status"] == "ok"
    assert out["domain"] == "cmdb_test"


def test_discover_unknown_domain_returns_invalid_argument():
    out = query_platform_source({"mode": "discover", "domain": "nonexistent"})
    assert out["status"] == "error"
    assert out["error"]["code"] == "invalid_argument"
    assert out["next_call"]["mode"] == "discover"


# ---------- describe ----------


def test_describe_returns_full_schema():
    op = OperationSpec(
        id="get_thing",
        summary="s",
        handler=_stub_handler,
        params_schema_override={"type": "object", "properties": {"id": {"type": "string"}}},
        example_params={"id": "x"},
        default_fields=["a", "b"],
        allowed_fields=["a", "b", "c"],
        notes="some note",
    )
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "describe", "domain": "domain1", "operation": "get_thing"})
    assert out["status"] == "ok"
    assert out["kind"] == "schema"
    assert out["params_schema"]["properties"]["id"]["type"] == "string"
    assert out["example_params"] == {"id": "x"}
    assert out["default_fields"] == ["a", "b"]
    assert out["allowed_fields"] == ["a", "b", "c"]
    assert out["notes"] == "some note"


def test_describe_reflects_request_serializer_into_apidoc_container():
    """没有 params_schema_override 时，反射 handler.RequestSerializer 并包成 apidoc 容器（非 JSON Schema）。"""
    from rest_framework import serializers

    class _Serializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        name = serializers.CharField(label="名称", required=False, default="")

    class _Handler:
        RequestSerializer = _Serializer

        def __call__(self, **kw):
            return {}

    op = OperationSpec(id="get_thing", summary="s", handler=_Handler())
    PlatformSourceCatalog.register_domain(id="domain_reflect", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "describe", "domain": "domain_reflect", "operation": "get_thing"})
    schema = out["params_schema"]
    assert schema["format"] == "apidoc_lines"
    assert schema["request_serializer"].endswith("_Serializer")
    # render_schema 返回的是行级 apidoc 字符串列表，不是 JSON Schema 对象
    assert isinstance(schema["request_params"], list)
    assert all(isinstance(line, str) for line in schema["request_params"])
    assert any("bk_biz_id" in line for line in schema["request_params"])


def test_describe_missing_domain_or_operation_is_invalid_argument():
    out = query_platform_source({"mode": "describe"})
    assert out["error"]["code"] == "invalid_argument"
    out2 = query_platform_source({"mode": "describe", "domain": "d"})
    assert out2["error"]["code"] == "invalid_argument"


def test_describe_unknown_domain_is_invalid_argument():
    out = query_platform_source({"mode": "describe", "domain": "x", "operation": "y"})
    assert out["error"]["code"] == "invalid_argument"


def test_describe_unknown_operation_in_known_domain_is_invalid_argument():
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[])
    out = query_platform_source({"mode": "describe", "domain": "domain1", "operation": "z"})
    assert out["error"]["code"] == "invalid_argument"
    assert out["next_call"]["domain"] == "domain1"


# ---------- invoke ----------


def test_invoke_kwargs_handler():
    op = OperationSpec(id="get_thing", summary="s", handler=_stub_handler)
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source(
        {"mode": "invoke", "domain": "domain1", "operation": "get_thing", "params": {"foo": "bar"}}
    )
    assert out["status"] == "ok"
    assert out["kind"] == "invocation"
    assert out["result"]["echoed"]["foo"] == "bar"


def test_invoke_positional_dict_handler():
    def _h(d):
        return {"got_dict": d}

    op = OperationSpec(id="get_thing", summary="s", handler=_h, invoke_style="positional_dict")
    PlatformSourceCatalog.register_domain(id="domain2", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain2", "operation": "get_thing", "params": {"x": 1}})
    assert out["status"] == "ok"
    assert out["result"]["got_dict"] == {"x": 1}


def test_force_refresh_without_cache_bypass_method_is_noop_with_warning():
    captured = {}

    def _h(**kw):
        captured.update(kw)
        return {}

    op = OperationSpec(id="get_thing", summary="s", handler=_h)
    PlatformSourceCatalog.register_domain(id="domain3", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source(
        {
            "mode": "invoke",
            "domain": "domain3",
            "operation": "get_thing",
            "params": {},
            "force_refresh": True,
        }
    )
    # 不再误塞 request_cache=False 这种 fake kwarg；handler 入参保持纯净。
    assert "request_cache" not in captured
    assert out["status"] == "ok"
    assert any("cache_bypass_method=None" in w for w in out["meta"]["warnings"])


def test_force_refresh_calls_cache_bypass_method_on_resource_handler():
    """模拟 bk-monitor Resource：handler.request 带 .refresh / .cacheless 方法。"""

    call_log: list[str] = []

    class _Request:
        def __call__(self, **kw):
            call_log.append("default")
            return {"mode": "default"}

        def refresh(self, **kw):
            call_log.append("refresh")
            return {"mode": "refresh", "kw": kw}

        def cacheless(self, **kw):
            call_log.append("cacheless")
            return {"mode": "cacheless", "kw": kw}

    class _Handler:
        request = _Request()

        def __call__(self, **kw):
            return self.request(**kw)

    op = OperationSpec(id="get_thing", summary="s", handler=_Handler(), cache_bypass_method="refresh")
    PlatformSourceCatalog.register_domain(id="domain3b", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source(
        {
            "mode": "invoke",
            "domain": "domain3b",
            "operation": "get_thing",
            "params": {"x": 1},
            "force_refresh": True,
        }
    )
    assert out["status"] == "ok"
    assert call_log == ["refresh"]
    assert out["result"]["mode"] == "refresh"
    assert out["result"]["kw"] == {"x": 1}
    assert "warnings" not in out["meta"]


def test_force_refresh_with_unavailable_bypass_method_falls_back_with_warning():
    """cache_bypass_method 已声明但 handler.request.<method> 不存在 → noop + warning。"""

    class _Handler:
        request = object()  # 没有 refresh / cacheless 方法

        def __call__(self, **kw):
            return {"called": True}

    op = OperationSpec(id="get_thing", summary="s", handler=_Handler(), cache_bypass_method="refresh")
    PlatformSourceCatalog.register_domain(id="domain3c", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source(
        {
            "mode": "invoke",
            "domain": "domain3c",
            "operation": "get_thing",
            "params": {},
            "force_refresh": True,
        }
    )
    assert out["status"] == "ok"
    assert any("unavailable" in w for w in out["meta"]["warnings"])


def test_invoke_unknown_domain_returns_unsafe_action_blocked():
    out = query_platform_source({"mode": "invoke", "domain": "x", "operation": "y", "params": {}})
    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"
    assert out["next_call"]["mode"] == "discover"


def test_invoke_unknown_operation_returns_unsafe_action_blocked():
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[])
    out = query_platform_source({"mode": "invoke", "domain": "domain1", "operation": "z", "params": {}})
    assert out["status"] == "error"
    assert out["error"]["code"] == "unsafe_action_blocked"


def test_invoke_provider_exception_returns_provider_unavailable():
    def _broken(**_):
        raise RuntimeError("upstream 500")

    op = OperationSpec(id="get_thing", summary="s", handler=_broken)
    PlatformSourceCatalog.register_domain(id="domain4", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain4", "operation": "get_thing", "params": {}})
    assert out["status"] == "error"
    assert out["error"]["code"] == "provider_unavailable"


def test_invoke_timeout_returns_domain_unreachable():
    def _slow(**_):
        raise TimeoutError("timeout")

    op = OperationSpec(id="get_thing", summary="s", handler=_slow)
    PlatformSourceCatalog.register_domain(id="domain5", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain5", "operation": "get_thing", "params": {}})
    assert out["error"]["code"] == "domain_unreachable"


def test_invoke_postprocess_is_applied():
    def _h(**_):
        return [{"a": 1, "b": 2, "secret": "x"}, {"a": 3, "b": 4, "secret": "y"}]

    def _pp(items, fields):
        return [{k: v for k, v in row.items() if k in (fields or [])} for row in items]

    op = OperationSpec(
        id="list_things",
        summary="s",
        handler=_h,
        default_fields=["a", "b"],
        allowed_fields=["a", "b"],
        response_postprocess=_pp,
    )
    PlatformSourceCatalog.register_domain(id="domain6", summary="d", audit_tags=["readonly"], operations=[op])
    out = query_platform_source({"mode": "invoke", "domain": "domain6", "operation": "list_things", "params": {}})
    assert out["result"] == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_invoke_params_must_be_object():
    PlatformSourceCatalog.register_domain(id="domain1", summary="d", audit_tags=["readonly"], operations=[])
    out = query_platform_source({"mode": "invoke", "domain": "domain1", "operation": "x", "params": "not-an-object"})
    assert out["error"]["code"] == "invalid_argument"


# ---------- mode / params validation ----------


def test_invalid_mode_returns_invalid_argument():
    out = query_platform_source({"mode": "delete"})
    assert out["error"]["code"] == "invalid_argument"


def test_missing_domain_or_operation_in_invoke():
    out = query_platform_source({"mode": "invoke"})
    assert out["error"]["code"] == "invalid_argument"


# ---------- catalog accept rules ----------


def test_operation_id_with_write_prefix_rejected():
    with pytest.raises(ValueError, match="readonly enforcement"):
        OperationSpec(id="create_thing", summary="s", handler=_stub_handler)


def test_operation_with_lambda_handler_rejected():
    with pytest.raises(ValueError, match="lambda"):
        OperationSpec(id="get_thing", summary="s", handler=lambda **_: None)


def test_domain_missing_readonly_tag_rejected():
    with pytest.raises(ValueError, match="readonly"):
        PlatformSourceCatalog.register_domain(id="bad", summary="d", audit_tags=["write"], operations=[])


def test_invalid_invoke_style_rejected():
    with pytest.raises(ValueError, match="invoke_style"):
        OperationSpec(id="get_thing", summary="s", handler=_stub_handler, invoke_style="batch")


def test_operation_id_with_banned_substring_rejected():
    """id 起始合法但中间含写动作语义（_delete / _update 等）必须拒绝。"""
    with pytest.raises(ValueError, match="banned write-semantic substring"):
        OperationSpec(id="get_thing_delete", summary="s", handler=_stub_handler)
    with pytest.raises(ValueError, match="banned write-semantic substring"):
        OperationSpec(id="list_then_update_x", summary="s", handler=_stub_handler)


def test_invalid_cache_bypass_method_rejected():
    with pytest.raises(ValueError, match="cache_bypass_method"):
        OperationSpec(id="get_thing", summary="s", handler=_stub_handler, cache_bypass_method="purge")


def test_duplicate_domain_registration_rejected():
    PlatformSourceCatalog.register_domain(id="dup", summary="d", audit_tags=["readonly"], operations=[])
    with pytest.raises(ValueError, match="already registered"):
        PlatformSourceCatalog.register_domain(id="dup", summary="d", audit_tags=["readonly"], operations=[])


def test_catalog_revision_changes_on_registration():
    rev1 = PlatformSourceCatalog.revision()
    PlatformSourceCatalog.register_domain(id="new_domain", summary="d", audit_tags=["readonly"], operations=[])
    rev2 = PlatformSourceCatalog.revision()
    assert rev1 != rev2


# ---------- registration ----------


def test_op_id_registered_in_bkm_cli_registry():
    """确保 query-platform-source 在 BkmCliOpRegistry 中。"""
    from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

    op = BkmCliOpRegistry.resolve("query-platform-source")
    assert op.func_name == "bkm_cli.query_platform_source"
    assert "readonly" in op.audit_tags


def test_func_registered_in_kernel_rpc_registry():
    from kernel_api.rpc.registry import KernelRPCRegistry

    KernelRPCRegistry.ensure_loaded()
    detail = KernelRPCRegistry.get_function_detail("bkm_cli.query_platform_source")
    assert detail is not None
    assert detail["func_name"] == "bkm_cli.query_platform_source"
