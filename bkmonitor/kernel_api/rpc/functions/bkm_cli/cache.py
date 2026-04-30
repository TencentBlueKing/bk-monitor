"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

bkm-cli read-cache-key 后端实现。

op_id: read-cache-key
func_name: bkm_cli.read_cache_key

白名单键常量名 → 实际 Redis key 对象，类比 read-db-model 的 model 白名单。
每个键规格声明：key 对象路径、数据类型、必填参数、排障说明。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass
class CacheKeySpec:
    key_name: str
    key_type: str  # "string" | "hash" | "zset" | "list"
    required_params: set[str]
    label: str
    extra_params: set[str] = field(default_factory=set)


ALLOWED_KEY_SPECS: dict[str, CacheKeySpec] = {
    "CHECK_RESULT_CACHE_KEY": CacheKeySpec(
        key_name="CHECK_RESULT_CACHE_KEY",
        key_type="zset",
        required_params={"strategy_id", "item_id", "dimensions_md5", "level"},
        label="[detect] 检测结果缓存 — 验证某维度/级别在时间窗内是否有检测结果",
    ),
    "ACCESS_PRIORITY_KEY": CacheKeySpec(
        key_name="ACCESS_PRIORITY_KEY",
        key_type="hash",
        required_params={"priority_group_key"},
        extra_params={"field"},
        label="[access] PGK 优先级缓存 — 查看当前 PGK 组内哪些维度被高优先级策略占据",
    ),
    "STRATEGY_SNAPSHOT_KEY": CacheKeySpec(
        key_name="STRATEGY_SNAPSHOT_KEY",
        key_type="string",
        required_params={"strategy_id", "update_time"},
        label="[detect] 策略快照 — access/detect 持有的策略版本，可与 DB 版本比对同步状态",
    ),
    "STRATEGY_CHECKPOINT_KEY": CacheKeySpec(
        key_name="STRATEGY_CHECKPOINT_KEY",
        key_type="string",
        required_params={"strategy_group_key"},
        label="[access] access 数据拉取进度 — 该策略组最后一次成功处理的数据时间戳",
    ),
    "LAST_CHECKPOINTS_CACHE_KEY": CacheKeySpec(
        key_name="LAST_CHECKPOINTS_CACHE_KEY",
        key_type="hash",
        required_params={"strategy_id", "item_id"},
        extra_params={"field"},
        label="[detect] detect 最近检测窗口 — 该 item 最后一次检测到的时间点",
    ),
    "ANOMALY_LIST_KEY": CacheKeySpec(
        key_name="ANOMALY_LIST_KEY",
        key_type="list",
        required_params={"strategy_id", "item_id"},
        label="[detect] detect 异常点积压 — 等待推送到 trigger 的异常点队列",
    ),
}


def _get_key_spec(key_name: str) -> CacheKeySpec:
    spec = ALLOWED_KEY_SPECS.get(key_name)
    if spec is None:
        allowed = sorted(ALLOWED_KEY_SPECS)
        raise CustomException(message=f"key_name 不在 bkm-cli read-cache-key 白名单: {key_name}。允许: {allowed}")
    return spec


def _get_key_obj(key_name: str):
    from alarm_backends.core.cache import key as key_module

    return getattr(key_module, key_name)


def _validate_params(params: dict[str, Any], spec: CacheKeySpec) -> None:
    missing = spec.required_params - set(params)
    if missing:
        raise CustomException(message=f"缺少必填参数: {sorted(missing)}")


def _normalize_limit(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"limit 必须是整数: {value}") from exc
    if limit <= 0:
        raise CustomException(message="limit 必须大于 0")
    if limit > MAX_LIMIT:
        raise CustomException(message=f"limit 超过硬上限 {MAX_LIMIT}: {limit}")
    return limit


def _safe_decode(value: bytes | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _try_json(s: str | None) -> Any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def _read_string(key_obj, key_params: dict[str, Any]) -> dict[str, Any]:
    resolved_key = key_obj.get_key(**key_params)
    raw = key_obj.client.get(str(resolved_key))
    value = _safe_decode(raw)
    return {
        "exists": value is not None,
        "value": _try_json(value),
        "raw": value,
    }


def _read_hash(key_obj, key_params: dict[str, Any], field: str | None, limit: int) -> dict[str, Any]:
    resolved_key = key_obj.get_key(**key_params)
    client = key_obj.client
    if field:
        raw = client.hget(str(resolved_key), field)
        value = _safe_decode(raw)
        return {
            "exists": value is not None,
            "field": field,
            "value": _try_json(value),
        }
    raw_map: dict = client.hgetall(str(resolved_key))
    items = {_safe_decode(k): _try_json(_safe_decode(v)) for k, v in raw_map.items()}
    total = len(items)
    truncated_items = dict(list(items.items())[:limit])
    return {
        "exists": total > 0,
        "total_fields": total,
        "truncated": total > limit,
        "items": truncated_items,
    }


def _read_zset(
    key_obj, key_params: dict[str, Any], limit: int, score_min: float | None, score_max: float | None
) -> dict[str, Any]:
    resolved_key = key_obj.get_key(**key_params)
    client = key_obj.client
    total: int = client.zcard(str(resolved_key))
    if score_min is not None and score_max is not None:
        raw_pairs = client.zrangebyscore(str(resolved_key), score_min, score_max, withscores=True, start=0, num=limit)
    else:
        raw_pairs = client.zrange(str(resolved_key), 0, limit - 1, withscores=True)
    members = [{"score": score, "value": _try_json(_safe_decode(member))} for member, score in raw_pairs]
    return {
        "exists": total > 0,
        "total_count": total,
        "returned_count": len(members),
        "truncated": total > limit,
        "members": members,
    }


def _read_list(key_obj, key_params: dict[str, Any], limit: int) -> dict[str, Any]:
    resolved_key = key_obj.get_key(**key_params)
    client = key_obj.client
    total: int = client.llen(str(resolved_key))
    raw_items = client.lrange(str(resolved_key), 0, limit - 1)
    items = [_try_json(_safe_decode(v)) for v in raw_items]
    return {
        "exists": total > 0,
        "total_count": total,
        "returned_count": len(items),
        "truncated": total > limit,
        "items": items,
    }


def read_cache_key(params: dict[str, Any]) -> dict[str, Any]:
    key_name = str(params.get("key_name") or "").strip()
    if not key_name:
        raise CustomException(message="key_name is required")

    spec = _get_key_spec(key_name)
    key_params: dict[str, Any] = params.get("params") or {}
    if not isinstance(key_params, dict):
        raise CustomException(message="params 必须是对象")

    _validate_params(key_params, spec)
    limit = _normalize_limit(params.get("limit"))

    key_obj = _get_key_obj(key_name)
    resolved_key = str(key_obj.get_key(**key_params))

    if spec.key_type == "string":
        data = _read_string(key_obj, key_params)
    elif spec.key_type == "hash":
        data = _read_hash(key_obj, key_params, params.get("field"), limit)
    elif spec.key_type == "zset":
        score_range = params.get("score_range") or {}
        score_min = score_range.get("min") if isinstance(score_range, dict) else None
        score_max = score_range.get("max") if isinstance(score_range, dict) else None
        data = _read_zset(key_obj, key_params, limit, score_min, score_max)
    elif spec.key_type == "list":
        data = _read_list(key_obj, key_params, limit)
    else:
        raise CustomException(message=f"不支持的 key_type: {spec.key_type}")

    return {
        "key_name": key_name,
        "key_type": spec.key_type,
        "resolved_key": resolved_key,
        "label": spec.label,
        **data,
    }


KernelRPCRegistry.register_function(
    func_name="bkm_cli.read_cache_key",
    summary="运行时 Redis 缓存键只读查询",
    description=(
        "bkm-cli read-cache-key 后端函数。"
        "按白名单键常量名读取 alarm_backends 运行时 Redis 缓存，"
        f"类比 read-db-model 的 model 白名单。当前白名单: {sorted(ALLOWED_KEY_SPECS)}"
    ),
    handler=read_cache_key,
    params_schema={
        "key_name": f"白名单键常量名，可选值: {sorted(ALLOWED_KEY_SPECS)}",
        "params": "键模板变量，因 key_name 而异",
        "limit": f"最大返回条数，默认 {DEFAULT_LIMIT}，上限 {MAX_LIMIT}",
        "field": "Hash 类型指定字段（省略则 hgetall）",
        "score_range": "ZSet 类型分值区间 {min, max}",
    },
    example_params={
        "key_name": "CHECK_RESULT_CACHE_KEY",
        "params": {"strategy_id": 12345, "item_id": 67890, "dimensions_md5": "abc123", "level": 1},
        "limit": 20,
    },
)

BkmCliOpRegistry.register(
    op_id="read-cache-key",
    func_name="bkm_cli.read_cache_key",
    summary="运行时 Redis 缓存键只读查询",
    description=(
        "按白名单键常量名读取 alarm_backends 运行时 Redis 缓存。"
        "key_name 参数对应 key.py 中的键常量，类比 read-db-model 的 model 参数。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["cache", "redis", "readonly"],
    params_schema={
        "key_name": "string",
        "params": "object",
        "limit": "integer",
        "field": "string",
        "score_range": "object",
    },
    example_params={
        "key_name": "CHECK_RESULT_CACHE_KEY",
        "params": {"strategy_id": 12345, "item_id": 67890, "dimensions_md5": "abc123", "level": 1},
    },
)
