"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

bkm-cli 统一查询只读通道。客户端只持有 discover/describe/invoke 协议，具体 UQ operation、
参数合同与容量护栏全部由本模块的服务端 catalog 管理。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

logger = logging.getLogger("bkmonitor")

CHANNEL_VERSION = "uq-query/v1"
MAX_TIME_RANGE_SECONDS = 24 * 60 * 60
MAX_QUERY_REFS = 20
MAX_OUTPUTS = 4
MAX_RAW_LIMIT = 100
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
VALID_MODES = {"discover", "describe", "invoke"}
SERVER_DERIVED_FIELDS = {"space_uid", "bk_biz_ids", "bk_tenant_id"}


@dataclass(frozen=True)
class UQOperationSpec:
    id: str
    summary: str
    handler: Callable[[dict[str, Any]], Any]
    params_schema: dict[str, Any]
    example_params: dict[str, Any]
    scope_style: str
    time_range_style: str
    min_limit: int = 0
    max_limit: int | None = None

    def limits(self) -> dict[str, int]:
        limits = {
            "max_request_bytes": MAX_REQUEST_BYTES,
            "max_response_bytes": MAX_RESPONSE_BYTES,
            "max_query_refs": MAX_QUERY_REFS,
        }
        if self.time_range_style != "none":
            limits["max_time_range_seconds"] = MAX_TIME_RANGE_SECONDS
        if self.max_limit is not None:
            limits["min_limit"] = self.min_limit
            limits["max_limit"] = self.max_limit
        if "output_list" in self.params_schema.get("properties", {}):
            limits["max_outputs"] = MAX_OUTPUTS
        return limits


def _array_of_objects(description: str) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "object"}, "description": description}


def _named_output_list_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": MAX_OUTPUTS,
        "description": "命名输出声明；顺序即响应顺序",
        "items": {
            "type": "object",
            "required": ["reference_name", "expression"],
            "properties": {"reference_name": {"type": "string"}, "expression": {"type": "string"}},
            "additionalProperties": False,
        },
    }


def _query_ts_schema(*, raw: bool = False, reference: bool = False, check: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query_list": _array_of_objects("UQ 结构化查询引用；最多 20 个"),
        "metric_merge": {"type": "string"},
        "start_time": {"type": ["string", "integer"], "description": "Unix 时间戳，秒或毫秒"},
        "end_time": {"type": ["string", "integer"], "description": "Unix 时间戳，秒或毫秒"},
        "step": {"type": "string"},
        "timezone": {"type": "string"},
        "instant": {"type": "boolean"},
        "not_time_align": {"type": "boolean"},
    }
    required = ["query_list", "start_time", "end_time"]
    if not check:
        required.extend(["metric_merge", "step"])
    if raw:
        properties.update(
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RAW_LIMIT, "default": 1},
                "_from": {"type": "integer", "minimum": 0, "default": 0},
                "order_by": {"type": ["array", "null"]},
                "is_es_batch": {"type": "boolean"},
            }
        )
    elif reference:
        properties.update(
            {
                "order_by": {"type": ["array", "null"]},
                "look_back_delta": {"type": "string", "default": "1m"},
            }
        )
    elif check:
        properties.update(
            {
                "order_by": {"type": "array"},
                "reference": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 0, "maximum": MAX_RAW_LIMIT, "default": 0},
            }
        )
    else:
        properties.update(
            {
                "down_sample_range": {"type": "string"},
                "response_contract": {"type": "string", "enum": ["named_outputs/v1"]},
                "legacy_output_ref": {"type": "string"},
                "output_list": _named_output_list_schema(),
            }
        )
        required.append("down_sample_range")
    return {"type": "object", "required": required, "properties": properties, "additionalProperties": False}


def _relation_schema(*, ranged: bool) -> dict[str, Any]:
    item_properties: dict[str, Any] = {
        "target_type": {"type": "string"},
        "source_type": {"type": "string"},
        "source_info": {"type": "object"},
        "path_resource": {"type": "array", "items": {"type": "string"}},
    }
    required = ["target_type", "source_info"]
    if ranged:
        item_properties.update(
            {
                "start_time": {"type": "integer"},
                "end_time": {"type": "integer"},
                "step": {"type": "string"},
            }
        )
        required.extend(["start_time", "end_time", "step"])
    else:
        item_properties["timestamp"] = {"type": "integer"}
        required.append("timestamp")
    return {
        "type": "object",
        "required": ["query_list"],
        "properties": {
            "query_list": {
                "type": "array",
                "maxItems": MAX_QUERY_REFS,
                "items": {"type": "object", "required": required, "properties": item_properties},
            }
        },
        "additionalProperties": False,
    }


def _call_query_ts(params: dict[str, Any]) -> Any:
    return api.unify_query.query_data(**params)


def _call_query_ts_raw(params: dict[str, Any]) -> Any:
    return api.unify_query.query_raw(**params)


def _call_query_ts_reference(params: dict[str, Any]) -> Any:
    return api.unify_query.query_reference(**params)


def _call_check_query_ts(params: dict[str, Any]) -> Any:
    return api.unify_query.check_query_ts(**params)


def _call_query_relation(params: dict[str, Any]) -> Any:
    return api.unify_query.query_multi(**params)


def _call_query_relation_range(params: dict[str, Any]) -> Any:
    return api.unify_query.query_multi_resource_range(**params)


OPERATIONS = {
    spec.id: spec
    for spec in (
        UQOperationSpec(
            id="query_ts",
            summary="执行结构化 QueryTs；支持 named_outputs/v1 并原样返回 UQ 响应",
            handler=_call_query_ts,
            params_schema=_query_ts_schema(),
            example_params={
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
            },
            scope_style="space_uid",
            time_range_style="top_level",
        ),
        UQOperationSpec(
            id="query_ts_raw",
            summary="执行有界的 UQ query/ts/raw 原始数据查询",
            handler=_call_query_ts_raw,
            params_schema=_query_ts_schema(raw=True),
            example_params={
                "query_list": [{"data_source": "bkmonitor", "field_name": "usage"}],
                "metric_merge": "A",
                "start_time": "1725062400",
                "end_time": "1725066000",
                "step": "60s",
                "limit": 20,
            },
            scope_style="space_uid",
            time_range_style="top_level",
            min_limit=1,
            max_limit=MAX_RAW_LIMIT,
        ),
        UQOperationSpec(
            id="query_ts_reference",
            summary="执行 UQ query/ts/reference 引用查询",
            handler=_call_query_ts_reference,
            params_schema=_query_ts_schema(reference=True),
            example_params={
                "query_list": [{"data_source": "bkmonitor", "field_name": "usage"}],
                "metric_merge": "A",
                "start_time": "1725062400",
                "end_time": "1725066000",
                "step": "60s",
            },
            scope_style="space_uid",
            time_range_style="top_level",
        ),
        UQOperationSpec(
            id="check_query_ts",
            summary="执行结构化 QueryTs 解析预览",
            handler=_call_check_query_ts,
            params_schema=_query_ts_schema(check=True),
            example_params={
                "query_list": [{"data_source": "bkmonitor", "field_name": "usage"}],
                "start_time": "1725062400",
                "end_time": "1725066000",
            },
            scope_style="space_uid_with_tenant",
            time_range_style="top_level",
            max_limit=MAX_RAW_LIMIT,
        ),
        UQOperationSpec(
            id="query_relation_v1",
            summary="查询指定时间点的 UQ v1 资源关联关系",
            handler=_call_query_relation,
            params_schema=_relation_schema(ranged=False),
            example_params={
                "query_list": [
                    {
                        "timestamp": 1725066000,
                        "target_type": "pod",
                        "source_type": "service",
                        "source_info": {"service_name": "api"},
                    }
                ]
            },
            scope_style="bk_biz_ids",
            time_range_style="none",
        ),
        UQOperationSpec(
            id="query_relation_range_v1",
            summary="查询有界时间范围内的 UQ v1 资源关联关系",
            handler=_call_query_relation_range,
            params_schema=_relation_schema(ranged=True),
            example_params={
                "query_list": [
                    {
                        "start_time": 1725062400,
                        "end_time": 1725066000,
                        "step": "60s",
                        "target_type": "pod",
                        "source_type": "service",
                        "source_info": {"service_name": "api"},
                    }
                ]
            },
            scope_style="bk_biz_ids",
            time_range_style="query_list",
        ),
    )
}


def _catalog_revision() -> str:
    snapshot = [
        {
            "id": spec.id,
            "summary": spec.summary,
            "params_schema": spec.params_schema,
            "limits": spec.limits(),
            "scope_style": spec.scope_style,
        }
        for spec in sorted(OPERATIONS.values(), key=lambda item: item.id)
    ]
    return hashlib.sha1(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def _meta() -> dict[str, Any]:
    return {"channel_version": CHANNEL_VERSION, "catalog_revision": _catalog_revision()}


def _error(code: str, message: str, *, next_call: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {"code": code, "message": message},
        "next_call": next_call or {"mode": "discover"},
        "meta": _meta(),
    }


def _parse_timestamp(value: Any, field_name: str) -> float:
    try:
        timestamp = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} 必须是 Unix 时间戳") from error
    if not math.isfinite(timestamp):
        raise ValueError(f"{field_name} 必须是有限 Unix 时间戳")
    if abs(timestamp) >= 10**12:
        timestamp /= 1000
    return timestamp


def _guard_named_output_contract(params: dict[str, Any]) -> None:
    contract = params.get("response_contract")
    named_fields = {"legacy_output_ref", "output_list"}
    if contract is None:
        unexpected = sorted(named_fields & params.keys())
        if unexpected:
            raise ValueError(f"未指定 response_contract 时不得提交: {', '.join(unexpected)}")
        return
    if contract != "named_outputs/v1":
        raise ValueError(f"不支持的 response_contract: {contract}")

    legacy_output_ref = params.get("legacy_output_ref")
    if not isinstance(legacy_output_ref, str) or not legacy_output_ref.strip():
        raise ValueError("named_outputs/v1 需要非空 legacy_output_ref")
    output_list = params.get("output_list")
    if not isinstance(output_list, list) or not output_list:
        raise ValueError("named_outputs/v1 需要非空 output_list")
    if len(output_list) > MAX_OUTPUTS:
        raise ValueError(f"output_list 最多允许 {MAX_OUTPUTS} 项")

    reference_names: list[str] = []
    for index, output in enumerate(output_list):
        if not isinstance(output, dict):
            raise ValueError(f"output_list[{index}] 必须是 object")
        unknown = sorted(set(output) - {"reference_name", "expression"})
        if unknown:
            raise ValueError(f"output_list[{index}] 包含合同外字段: {', '.join(unknown)}")
        for field in ("reference_name", "expression"):
            if not isinstance(output.get(field), str) or not output[field].strip():
                raise ValueError(f"output_list[{index}].{field} 必须是非空字符串")
        reference_names.append(output["reference_name"])
    if len(set(reference_names)) != len(reference_names):
        raise ValueError("output_list.reference_name 不得重复")
    if legacy_output_ref not in reference_names:
        raise ValueError("legacy_output_ref 必须存在于 output_list.reference_name")


def _guard_time_range(start: Any, end: Any, prefix: str = "") -> None:
    start_seconds = _parse_timestamp(start, f"{prefix}start_time")
    end_seconds = _parse_timestamp(end, f"{prefix}end_time")
    if end_seconds < start_seconds:
        raise ValueError(f"{prefix}end_time 不能早于 start_time")
    if end_seconds - start_seconds > MAX_TIME_RANGE_SECONDS:
        raise ValueError(f"{prefix}时间范围不能超过 {MAX_TIME_RANGE_SECONDS} 秒")


def _guard_params(spec: UQOperationSpec, params: dict[str, Any]) -> dict[str, Any]:
    forbidden = sorted(SERVER_DERIVED_FIELDS & params.keys())
    if forbidden:
        raise ValueError(f"调用方不得提交服务端派生字段: {', '.join(forbidden)}")

    allowed = set(spec.params_schema.get("properties", {}))
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"params 包含 describe 合同外字段: {', '.join(unknown)}")
    missing = [field for field in spec.params_schema.get("required", []) if field not in params]
    if missing:
        raise ValueError(f"params 缺少必填字段: {', '.join(missing)}")

    try:
        request_size = len(json.dumps(params, ensure_ascii=False).encode())
    except (TypeError, ValueError) as error:
        raise ValueError("params 必须是可 JSON 序列化的 object") from error
    if request_size > MAX_REQUEST_BYTES:
        raise ValueError(f"params 大小不能超过 {MAX_REQUEST_BYTES} 字节")

    query_list = params.get("query_list")
    if not isinstance(query_list, list) or not query_list:
        raise ValueError("query_list 必须是非空数组")
    if len(query_list) > MAX_QUERY_REFS:
        raise ValueError(f"query_list 最多允许 {MAX_QUERY_REFS} 项")

    output_list = params.get("output_list")
    if output_list is not None:
        if not isinstance(output_list, list):
            raise ValueError("output_list 必须是数组")
        if len(output_list) > MAX_OUTPUTS:
            raise ValueError(f"output_list 最多允许 {MAX_OUTPUTS} 项")

    if spec.id == "query_ts":
        _guard_named_output_contract(params)

    if spec.max_limit is not None and "limit" in params:
        try:
            limit = int(params["limit"])
        except (TypeError, ValueError) as error:
            raise ValueError("limit 必须是整数") from error
        if limit < spec.min_limit or limit > spec.max_limit:
            raise ValueError(f"limit 必须在 {spec.min_limit} 到 {spec.max_limit} 之间")

    if spec.time_range_style == "top_level":
        _guard_time_range(params.get("start_time"), params.get("end_time"))
    elif spec.time_range_style == "query_list":
        for index, query in enumerate(query_list):
            if not isinstance(query, dict):
                raise ValueError(f"query_list[{index}] 必须是 object")
            _guard_time_range(query.get("start_time"), query.get("end_time"), f"query_list[{index}].")

    return dict(params)


def _build_provider_params(
    spec: UQOperationSpec, *, bk_biz_id: int, bk_tenant_id: str, params: dict[str, Any]
) -> dict[str, Any]:
    provider_params = dict(params)
    if spec.scope_style in {"space_uid", "space_uid_with_tenant"}:
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not space_uid:
            raise ValueError(f"无法根据 bk_biz_id={bk_biz_id} 解析 space_uid")
        provider_params["space_uid"] = space_uid
    if spec.scope_style == "space_uid_with_tenant":
        if not bk_tenant_id:
            raise ValueError("无法解析 bk_tenant_id")
        provider_params["bk_tenant_id"] = bk_tenant_id
    if spec.scope_style == "bk_biz_ids":
        provider_params["bk_biz_ids"] = [str(bk_biz_id)]
    return provider_params


def _response_is_partial(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if raw.get("is_partial") is True:
        return True
    status = raw.get("status")
    if isinstance(status, dict) and status.get("is_partial") is True:
        return True
    outputs = raw.get("outputs")
    if isinstance(outputs, list):
        for output in outputs:
            if not isinstance(output, dict):
                return True
            if output.get("is_partial") is True or str(output.get("state") or "").upper() in {"PARTIAL", "ERROR"}:
                return True
    data = raw.get("data")
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                return True
            code = item.get("code", 200)
            try:
                if not 200 <= int(code) < 300:
                    return True
            except (TypeError, ValueError):
                return True
    return False


def _discover() -> dict[str, Any]:
    operations = [
        {
            "id": spec.id,
            "summary": spec.summary,
            "required_params": ["bk_biz_id", "params"],
            "limits": spec.limits(),
        }
        for spec in sorted(OPERATIONS.values(), key=lambda item: item.id)
    ]
    return {
        "status": "ok",
        "kind": "discovery",
        "operations": operations,
        "next_call": {"mode": "describe", "operation": "<选定 operation.id>"},
        "meta": _meta(),
    }


def _describe(spec: UQOperationSpec) -> dict[str, Any]:
    derived_params = ["bk_tenant_id"]
    derived_params.insert(0, "bk_biz_ids" if spec.scope_style == "bk_biz_ids" else "space_uid")
    return {
        "status": "ok",
        "kind": "schema",
        "operation": spec.id,
        "summary": spec.summary,
        "required_params": ["bk_biz_id", "params"],
        "params_schema": spec.params_schema,
        "example_params": {"bk_biz_id": 2, "params": spec.example_params},
        "derived_params": derived_params,
        "limits": spec.limits(),
        "next_call": {
            "mode": "invoke",
            "operation": spec.id,
            "bk_biz_id": 2,
            "params": spec.example_params,
        },
        "meta": _meta(),
    }


def _invoke(spec: UQOperationSpec, request_params: dict[str, Any]) -> dict[str, Any]:
    try:
        bk_biz_id = int(request_params.get("bk_biz_id"))
    except (TypeError, ValueError) as error:
        return _error("invalid_argument", f"bk_biz_id 必须是整数: {error}")
    invoke_params = request_params.get("params")
    if not isinstance(invoke_params, dict):
        return _error("invalid_argument", "invoke 需要 params object")

    try:
        derived_bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        injected_bk_tenant_id = str(request_params.get("bk_tenant_id") or "").strip()
        if injected_bk_tenant_id and injected_bk_tenant_id != derived_bk_tenant_id:
            raise ValueError(
                f"bk_tenant_id 与 bk_biz_id 派生租户不一致: {injected_bk_tenant_id} != {derived_bk_tenant_id}"
            )
        guarded_params = _guard_params(spec, invoke_params)
        provider_params = _build_provider_params(
            spec,
            bk_biz_id=bk_biz_id,
            bk_tenant_id=derived_bk_tenant_id,
            params=guarded_params,
        )
    except ValueError as error:
        return _error("unsafe_action_blocked", str(error))

    try:
        raw = spec.handler(provider_params)
    except (TimeoutError, requests.Timeout) as error:
        logger.warning("bkm-cli UQ query timeout: operation=%s", spec.id)
        return _error("provider_timeout", str(error))
    except Exception as error:  # noqa: BLE001
        logger.exception("bkm-cli UQ query failed: operation=%s", spec.id)
        return _error("provider_unavailable", str(error))

    try:
        response_size = len(json.dumps(raw, ensure_ascii=False, default=str).encode())
    except (TypeError, ValueError):
        response_size = MAX_RESPONSE_BYTES + 1
    if response_size > MAX_RESPONSE_BYTES:
        return _error("unsafe_action_blocked", f"UQ 响应超过 {MAX_RESPONSE_BYTES} 字节上限")

    return {
        "status": "ok",
        "kind": "invocation",
        "operation": spec.id,
        "result": raw,
        "partial": _response_is_partial(raw),
        "meta": _meta(),
    }


def query_unify_query(params: dict[str, Any]) -> dict[str, Any]:
    params = dict(params or {})
    mode = str(params.get("mode") or "discover").strip().lower()
    if mode not in VALID_MODES:
        return _error("invalid_argument", f"未知 mode: {mode}; 支持 {sorted(VALID_MODES)}")
    if mode == "discover":
        return _discover()

    operation_id = str(params.get("operation") or "").strip()
    if not operation_id:
        return _error("invalid_argument", f"mode={mode} 需要 operation")
    spec = OPERATIONS.get(operation_id)
    if spec is None:
        code = "unsafe_action_blocked" if mode == "invoke" else "invalid_argument"
        return _error(code, f"operation 未在 UQ catalog 注册: {operation_id}")
    if mode == "describe":
        return _describe(spec)
    return _invoke(spec, params)


KernelRPCRegistry.register_function(
    func_name="bkm_cli.query_unify_query",
    summary="通过服务端目录执行受控 UQ 只读查询",
    description=(
        "使用 discover/describe/invoke 渐进披露协议访问 UQ。operation、参数合同、业务/租户派生与容量护栏"
        "均由服务端控制，客户端不能提交任意 URL、Resource 或 func_name。"
    ),
    handler=query_unify_query,
    params_schema={
        "mode": "discover | describe | invoke",
        "operation": "describe/invoke 必填；必须来自 discover",
        "bk_biz_id": "invoke 必填；服务端据此派生 space_uid/bk_biz_ids 与租户",
        "params": "invoke 必填；必须满足 describe 返回的 operation schema",
    },
    example_params={"mode": "discover"},
)

BkmCliOpRegistry.register(
    op_id="query-unify-query",
    func_name="bkm_cli.query_unify_query",
    summary="通过服务端目录执行受控 UQ 只读查询",
    description=(
        "单一 UQ 通道，按 discover/describe/invoke 使用；新增 UQ 子操作只更新服务端 catalog，"
        "不要求 bkm-cli 或 MCP 增加新的固定 operation。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["unify-query", "readonly", "discovery"],
    params_schema={
        "mode": "string (discover|describe|invoke)",
        "operation": "string",
        "bk_biz_id": "integer",
        "params": "object",
    },
    example_params={"mode": "discover"},
)
