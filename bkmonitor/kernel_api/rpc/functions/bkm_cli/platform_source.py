"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

bkm-cli `query-platform-source` op 入口：单 op + 三阶段渐进披露
（discover/describe/invoke），融合 bkmonitor/api/* 中只读、有排障价值的 Resource。

CLI 端不内置任何 domain / operation 字典，所有元数据由本 catalog 提供。
"""

from __future__ import annotations

import logging
from typing import Any

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

from . import platform_catalog  # noqa: F401 (triggers catalog package load)
from .platform_catalog._catalog import OperationSpec, PlatformSourceCatalog

logger = logging.getLogger(__name__)

MODE_DISCOVER = "discover"
MODE_DESCRIBE = "describe"
MODE_INVOKE = "invoke"
VALID_MODES = (MODE_DISCOVER, MODE_DESCRIBE, MODE_INVOKE)

USAGE_FLOW = [
    '1. {"mode":"discover"} → 列域目录',
    '2. {"mode":"discover","domain":"<id>"} → 列子动作摘要',
    '3. {"mode":"describe","domain":"<id>","operation":"<id>"} → 看完整 schema',
    '4. {"mode":"invoke","domain":"<id>","operation":"<id>","params":{...}} → 执行',
]


def query_platform_source(params: dict[str, Any]) -> dict[str, Any]:
    """`bkm_cli.query_platform_source` 入口。"""
    params = params or {}
    mode = str(params.get("mode") or MODE_DISCOVER).strip().lower()
    if mode not in VALID_MODES:
        return _error(
            code="invalid_argument",
            message=f"未知 mode: {mode}; 支持 {list(VALID_MODES)}",
            next_call={"mode": "discover"},
        )

    domain_id = str(params.get("domain") or "").strip().lower()
    operation_id = str(params.get("operation") or "").strip()

    if mode == MODE_DISCOVER:
        return _discover_domains() if not domain_id else _discover_operations(domain_id)

    if mode == MODE_DESCRIBE:
        if not domain_id or not operation_id:
            return _error(
                code="invalid_argument",
                message="describe 需要 domain 与 operation",
                next_call={"mode": "discover"},
            )
        return _describe(domain_id, operation_id)

    # invoke
    if not domain_id or not operation_id:
        return _error(
            code="invalid_argument",
            message="invoke 需要 domain 与 operation",
            next_call={"mode": "discover"},
        )
    invoke_params = params.get("params") or {}
    if not isinstance(invoke_params, dict):
        return _error(code="invalid_argument", message="params 必须是 object")
    force_refresh = bool(params.get("force_refresh", False))
    return _invoke(domain_id, operation_id, invoke_params, force_refresh=force_refresh)


# ---------- internals ----------


def _meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = {
        "catalog_revision": PlatformSourceCatalog.revision(),
        "usage_flow": USAGE_FLOW,
    }
    if extra:
        meta.update(extra)
    return meta


def _error(*, code: str, message: str, next_call: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {"code": code, "message": message},
        "next_call": next_call,
        "meta": _meta(),
    }


def _discover_domains() -> dict[str, Any]:
    domains = []
    for domain_id in PlatformSourceCatalog.list_domain_ids():
        d = PlatformSourceCatalog.get_domain(domain_id)
        if d is None:
            continue
        domains.append(
            {
                "id": d.id,
                "summary": d.summary,
                "operations_count": len(d.operations),
                "audit_tags": d.audit_tags,
            }
        )
    return {
        "status": "ok",
        "kind": "discovery",
        "scope": "domains",
        "domains": domains,
        "next_call": {"mode": "discover", "domain": "<选定 domain.id>"},
        "meta": _meta(),
    }


def _discover_operations(domain_id: str) -> dict[str, Any]:
    domain = PlatformSourceCatalog.get_domain(domain_id)
    if domain is None:
        return _error(
            code="invalid_argument",
            message=f"domain 不存在: {domain_id}",
            next_call={"mode": "discover"},
        )
    operations = []
    for op_id in sorted(domain.operations.keys()):
        op = domain.operations[op_id]
        operations.append(
            {
                "id": op.id,
                "summary": op.summary,
                "required_params": list(op.required_params),
                "audit_tags": op.audit_tags,
            }
        )
    return {
        "status": "ok",
        "kind": "discovery",
        "scope": "operations",
        "domain": domain.id,
        "operations": operations,
        "next_call": {"mode": "describe", "domain": domain.id, "operation": "<选定 operation.id>"},
        "meta": _meta(),
    }


def _describe(domain_id: str, operation_id: str) -> dict[str, Any]:
    domain = PlatformSourceCatalog.get_domain(domain_id)
    if domain is None:
        return _error(
            code="invalid_argument",
            message=f"domain 不存在: {domain_id}",
            next_call={"mode": "discover"},
        )
    op = domain.operations.get(operation_id)
    if op is None:
        return _error(
            code="invalid_argument",
            message=f"operation 不存在: {operation_id}; 请先 discover 列出可用 operation",
            next_call={"mode": "discover", "domain": domain.id},
        )
    return {
        "status": "ok",
        "kind": "schema",
        "domain": domain.id,
        "operation": op.id,
        "params_schema": op.params_schema_override or _reflect_schema(op),
        "example_params": op.example_params,
        "default_fields": op.default_fields,
        "allowed_fields": op.allowed_fields,
        "audit_tags": op.audit_tags,
        "invoke_style": op.invoke_style,
        "notes": op.notes,
        "next_call": {
            "mode": "invoke",
            "domain": domain.id,
            "operation": op.id,
            "params": "<按 schema 填>",
        },
        "meta": _meta(),
    }


def _invoke(domain_id: str, operation_id: str, params: dict[str, Any], *, force_refresh: bool) -> dict[str, Any]:
    domain = PlatformSourceCatalog.get_domain(domain_id)
    if domain is None:
        return _error(
            code="unsafe_action_blocked",
            message=f"domain 未在 catalog 注册: {domain_id}",
            next_call={"mode": "discover"},
        )
    op = domain.operations.get(operation_id)
    if op is None:
        return _error(
            code="unsafe_action_blocked",
            message=f"(domain={domain_id}, operation={operation_id}) 未在 catalog 注册",
            next_call={"mode": "discover", "domain": domain.id},
        )

    invoke_params = dict(params or {})
    invoke_warnings: list[str] = []

    # cache_bypass：bk-monitor CacheResource 把 self.request 包成 using_cache wrapper（见
    # bkmonitor/utils/cache.py:217-220），wrapper 同时挂 .refresh / .cacheless 两个方法。
    # force_refresh=True 时按 op.cache_bypass_method 切换调用入口；未注册则 noop + meta warning。
    callable_to_invoke = op.handler
    if force_refresh:
        if op.cache_bypass_method is None:
            invoke_warnings.append("force_refresh=True but cache_bypass_method=None on this operation; treated as noop")
        else:
            request_method = getattr(op.handler, "request", None)
            bypassed = getattr(request_method, op.cache_bypass_method, None) if request_method else None
            if bypassed is None:
                invoke_warnings.append(
                    f"force_refresh=True but handler.request.{op.cache_bypass_method} unavailable; treated as noop"
                )
            else:
                callable_to_invoke = bypassed

    try:
        raw = (
            callable_to_invoke(invoke_params)
            if op.invoke_style == "positional_dict"
            else callable_to_invoke(**invoke_params)
        )
    except TimeoutError as e:
        logger.warning("platform_source invoke timeout: domain=%s op=%s", domain_id, operation_id)
        return _error(code="domain_unreachable", message=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("platform_source invoke failed: domain=%s op=%s", domain_id, operation_id)
        return _error(code="provider_unavailable", message=str(e))

    requested_fields = invoke_params.get("fields") or op.default_fields or None
    result = op.response_postprocess(raw, requested_fields) if op.response_postprocess else raw
    return {
        "status": "ok",
        "kind": "invocation",
        "domain": domain.id,
        "operation": op.id,
        "result": result,
        "meta": _meta({"warnings": invoke_warnings} if invoke_warnings else None),
    }


def _reflect_schema(op: OperationSpec) -> dict[str, Any]:
    """反射 handler 的 DRF RequestSerializer，包装成带语义的 schema 容器。

    ``core/drf_resource/tools.py:render_schema`` 返回 ``list[str]`` 形态的 apidoc 行，
    并非 JSON Schema。本函数把它包装成 ``{format, request_serializer, request_params, note}``，
    避免 agent 误把行列表当 JSON Schema 渲染。

    若 handler 上找不到 RequestSerializer，返回占位 dict 提示参考 example_params。
    若 catalog 需要精确 JSON Schema，注册 OperationSpec 时提供 params_schema_override。
    """
    handler = op.handler
    serializer_cls = getattr(handler, "RequestSerializer", None) or getattr(
        getattr(handler, "__class__", None), "RequestSerializer", None
    )
    if serializer_cls is None:
        return {"type": "object", "note": "无 RequestSerializer，请参考 example_params"}
    try:
        from core.drf_resource.tools import get_serializer_fields, render_schema

        return {
            "format": "apidoc_lines",
            "request_serializer": f"{serializer_cls.__module__}.{serializer_cls.__name__}",
            "request_params": render_schema(get_serializer_fields(serializer_cls)),
            "note": "行级 apidoc 形态，非 JSON Schema；如需 JSON Schema 请提供 params_schema_override",
        }
    except Exception:  # noqa: BLE001
        return {"type": "object", "note": "Serializer 反射失败，请参考 example_params"}


# ---------- registration ----------

KernelRPCRegistry.register_function(
    func_name="bkm_cli.query_platform_source",
    summary="渐进式访问 bk-monitor 后端平台 API 能力",
    description=(
        "渐进披露 op：必须先 discover（列域 → 列子动作）→ describe（看 schema）→ invoke（执行）。"
        "所有 domain/operation 元数据由后端 catalog 控制，CLI 端无内置能力字典。"
    ),
    handler=query_platform_source,
    params_schema={
        "mode": "discover | describe | invoke (默认 discover)",
        "domain": "describe/invoke 必填",
        "operation": "describe/invoke 必填",
        "params": "invoke 必填，透传给后端 handler",
        "force_refresh": (
            "可选；invoke 时按 OperationSpec.cache_bypass_method 切换调用入口绕过 CacheResource。"
            "未注册 cache_bypass_method 的 operation 视为 noop 并在 meta.warnings 提示。"
        ),
    },
    example_params={"mode": "discover"},
)

BkmCliOpRegistry.register(
    op_id="query-platform-source",
    func_name="bkm_cli.query_platform_source",
    summary="渐进式访问 bk-monitor 后端平台 API 能力",
    description=(
        "单入口 op + 三阶段渐进披露（discover/describe/invoke），融合 bkmonitor/api/* 中只读、"
        "有排障价值的 Resource。必须先 discover 才能 invoke；未在 catalog 注册的 (domain, operation) 一律拒。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["platform-api", "readonly", "discovery"],
    params_schema={
        "mode": "string (discover|describe|invoke)",
        "domain": "string",
        "operation": "string",
        "params": "object",
        "force_refresh": "boolean",
    },
    example_params={"mode": "discover"},
)
