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
from datetime import datetime
from typing import Any

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass
class CacheKeySpec:
    key_name: str
    key_type: str  # "string" | "hash" | "zset" | "list" | "set"
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
    "ACCESS_DUPLICATE_KEY": CacheKeySpec(
        key_name="ACCESS_DUPLICATE_KEY",
        key_type="set",
        required_params={"strategy_group_key", "dt_event_time"},
        label="[access] 数据拉取去重 — 查看指定策略组+时间窗口内已处理的数据去重集合",
    ),
    "ALERT_DATA_POLLER_LEADER_KEY": CacheKeySpec(
        key_name="ALERT_DATA_POLLER_LEADER_KEY",
        key_type="string",
        required_params=set(),
        label="[alert] 告警生成数据拉取 Leader — 查看当前集群的 poller leader 标识",
    ),
    "ALERT_DEDUPE_CONTENT_KEY": CacheKeySpec(
        key_name="ALERT_DEDUPE_CONTENT_KEY",
        key_type="string",
        required_params={"strategy_id", "dedupe_md5"},
        label="[alert] 当前正在产生的告警内容 — 查看指定策略+去重 MD5 的告警内容缓存",
    ),
    "ALERT_DETECT_RESULT": CacheKeySpec(
        key_name="ALERT_DETECT_RESULT",
        key_type="string",
        required_params={"alert_id"},
        label="[composite] 单告警检测结果 — 查看指定 alert_id 的 composite 检测结果",
    ),
    "ALERT_HOST_DATA_ID_KEY": CacheKeySpec(
        key_name="ALERT_HOST_DATA_ID_KEY",
        key_type="hash",
        required_params=set(),
        extra_params={"field"},
        label="[alert] 告警生成数据分配 — 按 host 查看 partition 分配情况，指定 field 可查单 host",
    ),
    "ALERT_SNAPSHOT_KEY": CacheKeySpec(
        key_name="ALERT_SNAPSHOT_KEY",
        key_type="string",
        required_params={"strategy_id", "alert_id"},
        label="[alert] 告警内容快照 — 查看指定策略+告警的快照数据",
    ),
    "SERVICE_LOCK_NODATA": CacheKeySpec(
        key_name="SERVICE_LOCK_NODATA",
        key_type="string",
        required_params={"strategy_id"},
        label="[nodata] 无数据告警处理锁 — 查看指定策略当前是否被 nodata 检测占用",
    ),
}


# ---------- read-config-cache helpers ----------


def _host_to_dict(host) -> dict[str, Any]:
    """将 Host 对象序列化为 JSON 安全的 dict。"""
    result: dict[str, Any] = {}
    from api.cmdb.define import Host

    for f in Host.Fields:
        result[f] = getattr(host, f, None)
    topo_link = getattr(host, "topo_link", None)
    if topo_link:
        result["topo_link"] = {node_id: [node.to_dict() for node in nodes] for node_id, nodes in topo_link.items()}
    result["display_name"] = getattr(host, "display_name", "")
    return result


def _normalize_shield_datetimes(shields: list[dict]) -> None:
    """将 shield 字典中的 datetime 对象原地转为 ISO 格式字符串。"""
    datetime_fields = {"begin_time", "end_time", "failure_time", "create_time", "update_time"}
    for shield in shields:
        for f in datetime_fields:
            value = shield.get(f)
            if isinstance(value, datetime):
                shield[f] = value.isoformat()


# ---------- read_cache_key ----------


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


_READ_SET_HARD_CAP = 2000


def _read_set(key_obj, key_params: dict[str, Any], limit: int) -> dict[str, Any]:
    resolved_key = key_obj.get_key(**key_params)
    client = key_obj.client
    total: int = client.scard(str(resolved_key))
    if total > _READ_SET_HARD_CAP:
        raise CustomException(
            message=f"set 成员数 {total} 超过安全读取上限 {_READ_SET_HARD_CAP}，拒绝 smembers 全量拉取"
        )
    raw_items = client.smembers(str(resolved_key))
    members = [_try_json(_safe_decode(v)) for v in raw_items]
    return {
        "exists": total > 0,
        "total_count": total,
        "returned_count": min(len(members), limit),
        "truncated": total > limit,
        "members": members[:limit],
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
    elif spec.key_type == "set":
        data = _read_set(key_obj, key_params, limit)
    else:
        raise CustomException(message=f"不支持的 key_type: {spec.key_type}")

    return {
        "key_name": key_name,
        "key_type": spec.key_type,
        "resolved_key": resolved_key,
        "label": spec.label,
        **data,
    }


# ---------- read-config-cache ----------


def _read_strategy(params: dict[str, Any]) -> dict[str, Any]:
    strategy_id = params.get("strategy_id")
    if strategy_id is None:
        raise CustomException(message="params.strategy_id is required for cache_type=strategy")
    try:
        strategy_id = int(strategy_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"strategy_id must be an integer: {strategy_id}") from exc

    from alarm_backends.core.cache.strategy import StrategyCacheManager

    data = StrategyCacheManager.get_strategy_by_id(strategy_id)
    return {
        "cache_type": "strategy",
        "params": {"strategy_id": strategy_id},
        "exists": data is not None,
        "data": data,
    }


def _read_host(params: dict[str, Any]) -> dict[str, Any]:
    ip = str(params.get("ip") or "").strip()
    if not ip:
        raise CustomException(message="params.ip is required for cache_type=host")

    bk_cloud_id = params.get("bk_cloud_id", 0)
    try:
        bk_cloud_id = int(bk_cloud_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"bk_cloud_id must be an integer: {bk_cloud_id}") from exc

    bk_tenant_id = str(params.get("bk_tenant_id") or DEFAULT_TENANT_ID)

    from alarm_backends.core.cache.cmdb.host import HostManager

    host = HostManager.get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)
    return {
        "cache_type": "host",
        "params": {"ip": ip, "bk_cloud_id": bk_cloud_id, "bk_tenant_id": bk_tenant_id},
        "exists": host is not None,
        "data": _host_to_dict(host) if host else None,
    }


def _read_assign(params: dict[str, Any]) -> dict[str, Any]:
    bk_biz_id = params.get("bk_biz_id")
    if bk_biz_id is None:
        raise CustomException(message="params.bk_biz_id is required for cache_type=assign.biz")
    try:
        bk_biz_id = int(bk_biz_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"bk_biz_id must be an integer: {bk_biz_id}") from exc

    from alarm_backends.core.cache.assign import AssignCacheManager
    from bkmonitor.utils.local import local

    # AssignCacheManager 依赖 local.assign_cache（threading.local），
    # 该属性仅在 alarm_backends 模块导入线程中初始化。
    # kernel_api 请求线程可能从未初始化，按需创建 + finally 清理。
    had_assign_cache = hasattr(local, "assign_cache")
    if not had_assign_cache:
        local.assign_cache = {}

    try:
        priority_list = AssignCacheManager.get_assign_priority_by_biz_id(bk_biz_id)
        groups: dict[str, list] = {}
        for priority in priority_list:
            group_ids = AssignCacheManager.get_assign_groups_by_priority(bk_biz_id, priority)
            groups[str(priority)] = sorted(group_ids)

        all_group_ids = {gid for grp in groups.values() for gid in grp}
        rules: dict[str, list] = {}
        for group_id in all_group_ids:
            rule_list = AssignCacheManager.get_assign_rules_by_group(bk_biz_id, group_id)
            if rule_list:
                rules[str(group_id)] = rule_list

        data = {
            "source_state": "current_cache_state",
            "bk_biz_id": bk_biz_id,
            "priorities": sorted(priority_list, reverse=True),
            "groups": groups,
            "rules": rules,
        }
        return {
            "cache_type": "assign.biz",
            "source_state": "current_cache_state",
            "params": {"bk_biz_id": bk_biz_id},
            "exists": len(priority_list) > 0,
            "data": data,
        }
    finally:
        if not had_assign_cache:
            AssignCacheManager.clear()
            del local.assign_cache


def _read_shield(params: dict[str, Any]) -> dict[str, Any]:
    bk_biz_id = params.get("bk_biz_id")
    if bk_biz_id is None:
        raise CustomException(message="params.bk_biz_id is required for cache_type=shield.biz")
    try:
        bk_biz_id = int(bk_biz_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"bk_biz_id must be an integer: {bk_biz_id}") from exc

    from alarm_backends.core.cache.shield import ShieldCacheManager

    shields = ShieldCacheManager.get_shields_by_biz_id(bk_biz_id)
    _normalize_shield_datetimes(shields)
    return {
        "cache_type": "shield.biz",
        "params": {"bk_biz_id": bk_biz_id},
        "exists": len(shields) > 0,
        "data": shields,
    }


def read_config_cache(params: dict[str, Any]) -> dict[str, Any]:
    cache_type = str(params.get("cache_type") or "").strip()
    if not cache_type:
        raise CustomException(message="cache_type is required")

    cache_params = params.get("params") or {}
    if not isinstance(cache_params, dict):
        raise CustomException(message="params must be an object")

    if cache_type == "strategy":
        return _read_strategy(cache_params)
    elif cache_type == "host":
        return _read_host(cache_params)
    elif cache_type == "assign.biz":
        return _read_assign(cache_params)
    elif cache_type == "shield.biz":
        return _read_shield(cache_params)
    else:
        raise CustomException(
            message=f"不支持的 cache_type: {cache_type}。允许: strategy, host, assign.biz, shield.biz"
        )


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

KernelRPCRegistry.register_function(
    func_name="bkm_cli.read_config_cache",
    summary="告警后端配置缓存只读查询 (CacheManager)",
    description=(
        "bkm-cli read-config-cache 后端函数。"
        "按 cache_type 读取 alarm_backends CacheManager 子类管理的 Redis 配置缓存。"
        "支持的 cache_type: strategy, host, assign.biz, shield.biz。"
    ),
    handler=read_config_cache,
    params_schema={
        "cache_type": "缓存类型: strategy | host | assign.biz | shield.biz",
        "params": "缓存查询参数，因 cache_type 而异",
    },
    example_params={
        "cache_type": "strategy",
        "params": {"strategy_id": 121950},
    },
)

BkmCliOpRegistry.register(
    op_id="read-config-cache",
    func_name="bkm_cli.read_config_cache",
    summary="告警后端配置缓存只读查询 (CacheManager)",
    description=(
        "按 cache_type 读取 alarm_backends CacheManager 子类管理的 Redis 配置缓存。"
        "cache_type 映射到对应的 CacheManager 子类。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["cache", "redis", "readonly", "config"],
    params_schema={
        "cache_type": "string",
        "params": "object",
    },
    example_params={
        "cache_type": "strategy",
        "params": {"strategy_id": 121950},
    },
)
