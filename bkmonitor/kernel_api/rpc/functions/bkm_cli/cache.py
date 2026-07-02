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
    "ISSUE_ACTIVE_CONTENT_KEY": CacheKeySpec(
        key_name="ISSUE_ACTIVE_CONTENT_KEY",
        key_type="string",
        required_params={"fingerprint"},
        label="[issue] 活跃 Issue 热缓存 — 按 fingerprint 查指定活跃 Issue 内容快照；"
        "aggregate_dimensions=[] 时 fingerprint 退化为 `strategy:{strategy_id}`",
    ),
    "ISSUE_FINGERPRINT_LOCK": CacheKeySpec(
        key_name="ISSUE_FINGERPRINT_LOCK",
        key_type="string",
        required_params={"fingerprint"},
        label="[issue] Issue 指纹级分布式锁 — 查指定 fingerprint 当前是否被某进程创建中",
    ),
    "ISSUE_ACTIVE_COUNT_KEY": CacheKeySpec(
        key_name="ISSUE_ACTIVE_COUNT_KEY",
        key_type="string",
        required_params={"strategy_id"},
        label="[issue] 单策略活跃 Issue 数缓存 — _check_active_issue_count 5min cache，"
        "high_cardinality 熔断观测；值含 ≤5min 滞后",
    ),
    "ISSUE_LEGACY_MIGRATION_DONE_KEY": CacheKeySpec(
        key_name="ISSUE_LEGACY_MIGRATION_DONE_KEY",
        key_type="string",
        required_params=set(),
        label="[issue] legacy 迁移完成全局哨兵 — 看到该哨兵则 processor 跳过 fingerprint=null "
        "全索引 fallback；migrate_legacy_active_issues 完成时 set",
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
    # 必须传 SimilarStr 原对象给 client；str() 会丢失 strategy_id 属性，
    # 导致 RedisProxy 按 strategy_id=0 路由到错误的 cache_node。
    resolved_key = key_obj.get_key(**key_params)
    raw = key_obj.client.get(resolved_key)
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
        raw = client.hget(resolved_key, field)
        value = _safe_decode(raw)
        return {
            "exists": value is not None,
            "field": field,
            "value": _try_json(value),
        }
    raw_map: dict = client.hgetall(resolved_key)
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
    total: int = client.zcard(resolved_key)
    if score_min is not None and score_max is not None:
        raw_pairs = client.zrangebyscore(resolved_key, score_min, score_max, withscores=True, start=0, num=limit)
    else:
        raw_pairs = client.zrange(resolved_key, 0, limit - 1, withscores=True)
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
    total: int = client.llen(resolved_key)
    raw_items = client.lrange(resolved_key, 0, limit - 1)
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
    total: int = client.scard(resolved_key)
    if total > _READ_SET_HARD_CAP:
        raise CustomException(
            message=f"set 成员数 {total} 超过安全读取上限 {_READ_SET_HARD_CAP}，拒绝 smembers 全量拉取"
        )
    raw_items = client.smembers(resolved_key)
    members = [_try_json(_safe_decode(v)) for v in raw_items]
    return {
        "exists": total > 0,
        "total_count": total,
        "returned_count": min(len(members), limit),
        "truncated": total > limit,
        "members": members[:limit],
    }


def _node_identity(node) -> dict[str, Any]:
    """CacheNode 身份字段（对账够用，且不含敏感信息）。

    故意不含 host/port（内部 Redis 拓扑/内网 IP，排障输出可能贴进归档/PR 触红线）
    与 password/connection_kwargs（凭据）。read-cache-key routing 与 list-cache-routing
    共用本函数，保证两条出口的脱敏纪律一致。
    """
    return {
        "id": node.id,
        "node_alias": getattr(node, "node_alias", "") or "",
        "cluster_name": node.cluster_name,
        "cache_type": node.cache_type,
        "is_default": bool(node.is_default),
        "is_enable": bool(node.is_enable),
    }


def _resolve_routing(key_obj, similar_key) -> dict[str, Any]:
    """回显本次读取实际路由到的 Redis 节点身份。

    与 RedisProxy 的路由逻辑保持一致：按 SimilarStr.strategy_id 调 get_node_by_strategy_id。
    用途：核对服务桥读到的 Redis 实例与 alarm_backends worker 写入的实例是否一致
    （定位 exists=false 是键不存在还是读错了实例）。
    仅在主读取完成后调用（路由缓存已由主读取填充，不引入新的节点解析副作用）；
    回显失败不影响主读取结果。

    前提：主读取通过 RedisProxy 以相同 strategy_id 路由，已先行触发同一 get_node_by_strategy_id
    （strategy_id=0 时其内部 default_node() 的 get_or_create 写已由主读取完成）。若将来出现绕过
    RedisProxy 的读取路径，需重新评估本函数是否会成为 default_node() 的首个调用方而引入写副作用。
    """
    try:
        from alarm_backends.core.cluster import get_cluster
        from alarm_backends.core.storage.redis import CACHE_BACKEND_CONF_MAP
        from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id

        backend = getattr(key_obj, "backend", None)
        strategy_id = int(getattr(similar_key, "strategy_id", 0) or 0)
        node = get_node_by_strategy_id(strategy_id)
        return {
            "strategy_id": strategy_id,
            "backend": backend,
            "db": CACHE_BACKEND_CONF_MAP.get(backend, {}).get("db", 0),
            "process_cluster": get_cluster().name,
            "node": _node_identity(node),
        }
    except Exception as exc:
        # 回显属于附加诊断信息，任何失败都不能影响主读取
        return {"error": str(exc)}


def _resolve_ttl_ms(key_obj, similar_key) -> int | None:
    """回显键的剩余 TTL（毫秒）。Redis PTTL 语义：-1=永不过期，-2=键不存在，>=0=剩余毫秒。

    用途：exists=false 时区分"刚过期(-2 但曾存在,无法区分)"与"持续刷新"；exists=true 时
    判断是否在被持续刷新（TTL 接近满值）还是陈旧将过期。必须传 SimilarStr 原对象以保留
    strategy_id 路由（str() 会丢路由属性）。失败兜底 None，不影响主读取。
    """
    try:
        return int(key_obj.client.pttl(similar_key))
    except Exception:
        return None


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
    similar_key = key_obj.get_key(**key_params)
    resolved_key = str(similar_key)

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
        "routing": _resolve_routing(key_obj, similar_key),
        "ttl_ms": _resolve_ttl_ms(key_obj, similar_key),
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


def _read_action_config(params: dict[str, Any]) -> dict[str, Any]:
    """读取处理/通知套餐(ActionConfig)的运行时配置缓存。

    用于「克隆/新建套餐缓存未传播被误判为已删除/禁用」类排障的缓存侧取证。缓存有三态：
    - exists=False（键不存在）：套餐尚未刷入缓存（克隆/新建竞态特征），或负缓存哨兵已过 TTL 被清；
      单看缓存无法区分「竞态未传播」与「曾真删」，须配合 read-db-model(ActionConfig, origin_objects)
      读 DB 真态对拍。
    - exists=True 且 is_negative=True（负缓存哨兵）：读路径回查 DB 也未命中，即 DB 已确认套餐
      真删/不存在——这是缓存层对「真删」的最高置信信号（来自 set_negative_cache，非真实配置）。
    - exists=True 且 is_negative=False：套餐配置已正常刷入缓存，is_enabled 为其真实启停态。

    脱敏：execute_config（执行参数，可内嵌 webhook/凭据）不透出，只回安全摘要。
    注意：config_id 命中内置默认通知套餐(DEFAULT_NOTICE_ID)时，返回硬编码默认、不读 Redis，
    故该 id 恒 exists=True、is_negative=False，与缓存实际状态无关。
    """
    config_id = params.get("config_id")
    if config_id is None:
        raise CustomException(message="params.config_id is required for cache_type=action_config")
    try:
        config_id = int(config_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"config_id must be an integer: {config_id}") from exc

    from alarm_backends.core.cache.action_config import ActionConfigCacheManager

    data = ActionConfigCacheManager.get_action_config_by_id(config_id)
    # 负缓存哨兵：非空但带 NEGATIVE_CACHE_FLAG 标记，表示 DB 已确认真删/不存在（非真实配置）。
    is_negative = bool(data) and bool(data.get(ActionConfigCacheManager.NEGATIVE_CACHE_FLAG))
    summary = None
    if data:
        # 安全摘要白名单：只回取证必要字段 + 负缓存标记；execute_config 等其余字段一律不透出。
        summary = {
            "id": data.get("id"),
            "name": data.get("name"),
            "is_enabled": data.get("is_enabled"),
            "plugin_id": data.get("plugin_id"),
            "bk_biz_id": data.get("bk_biz_id"),
            "is_negative": is_negative,
        }
    return {
        "cache_type": "action_config",
        "params": {"config_id": config_id},
        "exists": bool(data),
        "is_negative": is_negative,
        "data": summary,
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
    elif cache_type == "action_config":
        return _read_action_config(cache_params)
    else:
        raise CustomException(
            message=f"不支持的 cache_type: {cache_type}。允许: strategy, host, assign.biz, shield.biz, action_config"
        )


# ---------- list-cache-routing ----------


def list_cache_routing(params: dict[str, Any]) -> dict[str, Any]:
    """列出当前集群的 alarm_backends Redis 缓存路由表（CacheRouter）+ 默认节点。

    用途：给 read-cache-key 的 routing 回显提供独立信源做双边对账——routing 回显与实际读取
    共用 get_node_by_strategy_id（单边自指），本 op 直读 CacheRouter/CacheNode 表，可交叉核对
    strategy_id -> node 映射全貌。纯只读：不调 CacheNode.default_node()（其 get_or_create 有写
    副作用），改用 filter(is_default=True) 只读取。不回显 host/port（与 read-cache-key 一致）。

    strategy_score 是区间的开区间上界（与 redis_cluster.get_node_by_strategy_id 一致）：
    某 strategy_id 命中第一个 strategy_score > strategy_id 的路由行；strategy_id=0 走默认节点。
    """
    from alarm_backends.core.cluster import get_cluster
    from bkmonitor.models import CacheNode, CacheRouter

    cluster_name = get_cluster().name
    routers = list(
        CacheRouter.objects.filter(cluster_name=cluster_name).select_related("node").order_by("strategy_score")
    )

    items = []
    prev_floor = 0
    for router in routers:
        items.append(
            {
                "strategy_score": router.strategy_score,
                # 命中区间 [floor, ceil]：floor=上一行 score，ceil=本行 score-1
                "score_range": {"floor": prev_floor, "ceil": router.strategy_score - 1},
                "node": _node_identity(router.node),
            }
        )
        prev_floor = router.strategy_score

    # 默认节点（strategy_id=0 或路由表未命中时的落点）——只读查询，绝不触发 default_node() 的写
    default_node = CacheNode.objects.filter(is_default=True, cluster_name=cluster_name).first()

    return {
        "cluster_name": cluster_name,
        "router_count": len(items),
        "routers": items,
        "default_node": _node_identity(default_node) if default_node else None,
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
        "输出 routing 字段回显实际路由到的 Redis 节点（node.id/node_alias/cluster_name/cache_type，"
        "不含 host/port），用于核对服务桥与 alarm_backends worker 是否读写同一实例；"
        "配合 list-cache-routing 可做双边对账。输出 ttl_ms 为键剩余 TTL（-1 永不过期/-2 不存在/>=0 毫秒）。"
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
        "支持的 cache_type: strategy, host, assign.biz, shield.biz, action_config。"
    ),
    handler=read_config_cache,
    params_schema={
        "cache_type": "缓存类型: strategy | host | assign.biz | shield.biz | action_config",
        "params": "缓存查询参数，因 cache_type 而异（action_config 需 config_id）",
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

KernelRPCRegistry.register_function(
    func_name="bkm_cli.list_cache_routing",
    summary="列出 alarm_backends Redis 缓存路由表 (CacheRouter)",
    description=(
        "只读列出当前集群 CacheRouter 路由表 + 默认节点，给 read-cache-key 的 routing 回显"
        "提供独立信源做 strategy_id -> node 双边对账。不含 host/port/password。无入参。"
    ),
    handler=lambda params: list_cache_routing(params or {}),
    params_schema={},
    example_params={},
)

BkmCliOpRegistry.register(
    op_id="list-cache-routing",
    func_name="bkm_cli.list_cache_routing",
    summary="列出 alarm_backends Redis 缓存路由表 (CacheRouter)",
    description=(
        "只读列出当前集群 CacheRouter 路由表（strategy_score 区间 -> node）+ 默认节点。"
        "用于核对 read-cache-key routing 回显的 strategy_id -> node 落点（解单边自指）。"
        "node 不含 host/port/password。strategy_score 是开区间上界：strategy_id 命中第一个 "
        "strategy_score > strategy_id 的行；strategy_id=0 走 default_node。无入参。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["cache", "redis", "readonly", "routing"],
    params_schema={},
    example_params={},
)
