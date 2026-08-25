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

import json
from typing import Any

from bkmonitor.models.strategy import StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

OPERATION_DETAIL = "detail"
OPERATION_LIST_BY_PRIORITY_GROUP = "list_by_priority_group"
OPERATION_SHARED_GROUP = "shared_group"
OPERATION_LIST_ENABLED = "list_enabled"
ALLOWED_OPERATIONS = {
    OPERATION_DETAIL,
    OPERATION_LIST_BY_PRIORITY_GROUP,
    OPERATION_SHARED_GROUP,
    OPERATION_LIST_ENABLED,
}

DEFAULT_PAGE_SIZE = 500
MAX_PAGE_SIZE = 2000
# ``.strategy_group`` 的保留字段，不是策略 ID
GROUP_RESERVED_FIELDS = ("interval_list", "strategy_source", "bk_biz_id")
# CHECK_RESULT 清理任务的周期（``0 */2 * * *``，见 config/role/worker.py 的 crontab 配置）。
# 热路径 zadd 不裁剪，只有这个周期任务按 point_required 收口，因此它决定成员数的超发幅度。
CHECK_RESULT_CLEAN_INTERVAL_SECONDS = 7200
# get_strategy_by_ids 的 MGET 分块大小（core/cache/strategy.py::get_strategy_by_ids）
STRATEGY_MGET_CHUNK_SIZE = 1000


def inspect_strategy_config(params: dict[str, Any]) -> dict[str, Any]:
    operation = str(params.get("operation") or OPERATION_DETAIL).strip()
    if operation not in ALLOWED_OPERATIONS:
        raise CustomException(message=f"不支持的 inspect-strategy-config operation: {operation}")

    if operation == OPERATION_DETAIL:
        return _inspect_strategy_detail(params)
    if operation == OPERATION_SHARED_GROUP:
        return _inspect_shared_group(params)
    if operation == OPERATION_LIST_ENABLED:
        return _list_enabled(params)
    return _list_by_priority_group(params)


def _inspect_shared_group(params: dict[str, Any]) -> dict[str, Any]:
    strategy_group_key = str(params.get("strategy_group_key") or "").strip()
    if not strategy_group_key:
        raise CustomException(message="operation=shared_group 必须提供 strategy_group_key")

    from alarm_backends.core.cache.strategy import StrategyCacheManager

    detail = StrategyCacheManager.get_strategy_group_detail(strategy_group_key)
    if not isinstance(detail, dict):
        raise CustomException(message=f"共享查询组缓存结构异常: {strategy_group_key}")
    members = []
    for raw_strategy_id, raw_item_ids in detail.items():
        try:
            strategy_id = int(raw_strategy_id)
        except (TypeError, ValueError):
            continue
        if not isinstance(raw_item_ids, list):
            continue
        item_ids = sorted(
            item_id for item_id in raw_item_ids if isinstance(item_id, int) and not isinstance(item_id, bool)
        )
        members.append({"strategy_id": strategy_id, "item_ids": item_ids})

    return {
        "operation": OPERATION_SHARED_GROUP,
        "strategy_group_key": strategy_group_key,
        "found": bool(members),
        "bk_biz_id": detail.get("bk_biz_id"),
        "members": sorted(members, key=lambda item: item["strategy_id"]),
    }


def _list_enabled(params: dict[str, Any]) -> dict[str, Any]:
    """批量枚举启用策略并附带监控项映射，用于策略级 Redis 成本核算。

    Redis 读取次数与返回条数、分页页码无关：人口取一次 ``GET .strategy_ids``，策略到
    监控项的映射取一次 ``HGETALL .strategy_group``。刻意不走逐策略读 ``.strategy_{id}``
    ——按当前规模那是数千次往返，正是本操作要替代的模式。``HGETALL`` 与 access 主循环
    （``service/access/handler.py``）和 manage-double-check-strategy 的既有读法一致，
    不引入新的读取风险等级。
    """
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    intervals, filter_echo = _resolve_strategy_id_filter(params)
    page, page_size = _resolve_pagination(params)
    include_item_ids = bool(params.get("include_item_ids", True))
    include_detect_profile = bool(params.get("include_detect_profile", False))

    raw_ids = StrategyCacheManager.get_strategy_ids()
    population: list[int] = sorted({int(raw_id) for raw_id in raw_ids if _is_int_like(raw_id)})

    matched = [strategy_id for strategy_id in population if _in_intervals(strategy_id, intervals)]

    group_index, malformed_groups = _build_group_index(StrategyCacheManager.get_all_groups())
    in_group = sum(1 for strategy_id in matched if strategy_id in group_index)

    total_pages = (len(matched) + page_size - 1) // page_size if matched else 0
    start = (page - 1) * page_size
    page_ids = matched[start : start + page_size]
    strategies = [
        _serialize_enabled_strategy(strategy_id, group_index.get(strategy_id), include_item_ids=include_item_ids)
        for strategy_id in page_ids
    ]

    detect_profiles: dict[int, dict[str, Any]] = {}
    if include_detect_profile:
        detect_profiles = _build_detect_profiles(page_ids)
        for entry in strategies:
            entry["detect_profile"] = detect_profiles.get(entry["strategy_id"])

    return {
        "operation": OPERATION_LIST_ENABLED,
        "population": {
            "source": "cache:.strategy_ids",
            "total": len(population),
            # 该缓存按增量并集刷新（core/cache/strategy.py::refresh_strategy_ids），
            # 停用但未删除的策略可能残留，因此与 DB 计数只应同量级比对，不可做等值断言。
            "drift_note": "增量并集刷新，可能残留已停用策略；与 DB 计数只做同量级比对",
        },
        "filter": dict(filter_echo, matched=len(matched)),
        "page": {
            "number": page,
            "size": page_size,
            "returned": len(strategies),
            "total_pages": total_pages,
            "has_more": start + len(strategies) < len(matched),
        },
        "redis_commands": {
            "base": 2,
            "detect_profile_mget_chunks": _mget_chunks(len(page_ids)) if include_detect_profile else 0,
            "note": (
                "固定一次 GET .strategy_ids + 一次 HGETALL .strategy_group，与页码无关；"
                f"启用 include_detect_profile 时另加每 {STRATEGY_MGET_CHUNK_SIZE} 个策略一次 MGET"
            ),
        },
        "detect_profile_coverage": {
            "requested": len(page_ids) if include_detect_profile else 0,
            "resolved": len(detect_profiles),
        },
        "group_coverage": {
            "source": "cache:.strategy_group",
            "in_group": in_group,
            "not_in_group": len(matched) - in_group,
            "malformed_groups": malformed_groups,
            # 只收录 query_md5 非空的监控项（core/cache/strategy.py::handle_strategy），
            # 事件类等策略天然不在其中，缺失不代表数据异常。
            "miss_note": "仅时序/日志与自定义、自愈事件类监控项进入策略组，其余策略缺失属预期",
        },
        "strategies": strategies,
    }


def _mget_chunks(count: int) -> int:
    return (count + STRATEGY_MGET_CHUNK_SIZE - 1) // STRATEGY_MGET_CHUNK_SIZE


def _build_detect_profiles(strategy_ids: list[int]) -> dict[int, dict[str, Any]]:
    """按改造前的策略级周期清理口径生成 CHECK_RESULT 参考估算。

    只对当前页取配置，走 ``get_strategy_by_ids`` 的分块 MGET（每 ``STRATEGY_MGET_CHUNK_SIZE``
    个策略一条命令），因此命令数由页大小决定而非策略总数，不构成 N+1。

    ``point_required`` 仍取旧的策略级保留公式，用于兼容历史成本排序。普通时序、日志和
    NoData 已按 item 在写入后即时裁剪，因此这里的 ``peak`` 不再代表实际峰值或安全上界；
    Event 及裁剪失败后的周期兜底仍可参考此口径。
    """
    if not strategy_ids:
        return {}

    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from alarm_backends.core.control.item import detect_result_point_required
    from alarm_backends.core.control.strategy import Strategy as ControlStrategy

    profiles: dict[int, dict[str, Any]] = {}
    for config in StrategyCacheManager.get_strategy_by_ids(list(strategy_ids)) or []:
        if not isinstance(config, dict) or not _is_int_like(config.get("id")):
            continue
        strategy_id = int(config["id"])
        try:
            point_required = int(detect_result_point_required(config))
            interval = int(ControlStrategy(strategy_id, default_config=config).get_interval())
        except Exception as error:
            # 单个策略配置异常不影响同页其余策略，把原因带出来便于定位
            profiles[strategy_id] = {"error": str(error)}
            continue
        if interval <= 0:
            profiles[strategy_id] = {"error": f"非法周期: {interval}"}
            continue

        # 保留改造前的"基线 + 一个周期新增"公式，作为历史成本参考值。
        # 普通时序、日志和 NoData 的写后即时裁剪未纳入该策略级模型。
        growth = -(-CHECK_RESULT_CLEAN_INTERVAL_SECONDS // interval)
        peak = point_required + growth
        profiles[strategy_id] = {
            "model_scope": "legacy_periodic_reference",
            "is_safe_upper_bound": False,
            "point_required": point_required,
            "interval": interval,
            "clean_interval_seconds": CHECK_RESULT_CLEAN_INTERVAL_SECONDS,
            "growth_per_clean_cycle": growth,
            "check_result_peak_per_series": peak,
            "overshoot_ratio": round(peak / point_required, 2) if point_required else None,
        }
    return profiles


def _resolve_strategy_id_filter(params: dict[str, Any]) -> tuple[list[tuple[int, int | None]] | None, dict[str, Any]]:
    """解析策略 ID 过滤区间，返回 (闭区间列表, 回显)。``None`` 表示不过滤。"""
    node_id = _optional_int(params, "node_id")
    strategy_id_min = _optional_int(params, "strategy_id_min")
    strategy_id_max = _optional_int(params, "strategy_id_max")

    if node_id is not None and (strategy_id_min is not None or strategy_id_max is not None):
        raise CustomException(message="node_id 与 strategy_id_min/strategy_id_max 不能同时指定")

    if node_id is not None:
        intervals = _node_routing_intervals(node_id)
        return intervals, {
            "mode": "node_id",
            "node_id": node_id,
            "intervals": [{"min": low, "max": high} for low, high in intervals],
        }

    if strategy_id_min is None and strategy_id_max is None:
        return None, {"mode": "all"}

    low = strategy_id_min if strategy_id_min is not None else 0
    if strategy_id_max is not None and strategy_id_max < low:
        raise CustomException(message=f"strategy_id_max 不能小于 strategy_id_min: {strategy_id_max} < {low}")
    return [(low, strategy_id_max)], {
        "mode": "strategy_id_range",
        "intervals": [{"min": low, "max": strategy_id_max}],
    }


def _node_routing_intervals(node_id: int) -> list[tuple[int, int]]:
    """把 CacheRouter 路由表折算成指定节点承载的策略 ID 闭区间列表。

    路由判定是"第一个 ``strategy_score > strategy_id`` 的记录胜出"
    （``core/storage/redis_cluster.py::_lookup_node_in_routers``），因此按 score 升序
    排列后某记录实际覆盖 ``[上一条 score, 本条 score - 1]``。这个差一位的半开语义容易被
    调用方算错，故在服务端折算并把区间回显出来。
    区间口径与 list-cache-routing 的 ``score_range`` 严格一致：只取正数 score，下界从 1
    起（``strategy_id=0`` 被强制路由到 default_node，不属于正数路由段），``score <= 0``
    的保留记录不参与区间划分。同一节点可占多个不相邻区间，故返回列表。
    """
    from alarm_backends.core.cluster import get_cluster
    from bkmonitor.models import CacheRouter

    routes = list(
        CacheRouter.objects.filter(cluster_name=get_cluster().name, strategy_score__gt=0)
        .order_by("strategy_score")
        .values("node_id", "strategy_score")
    )
    if not routes:
        raise CustomException(message="当前集群没有正数 CacheRouter 路由记录，无法按节点过滤")

    intervals: list[tuple[int, int]] = []
    floor = 1
    for route in routes:
        ceil = route["strategy_score"] - 1
        if route["node_id"] == node_id and ceil >= floor:
            intervals.append((floor, ceil))
        floor = route["strategy_score"]

    if not intervals:
        raise CustomException(message=f"节点 {node_id} 在当前集群正数路由表中没有覆盖区间")
    return intervals


def _in_intervals(strategy_id: int, intervals: list[tuple[int, int | None]] | None) -> bool:
    if intervals is None:
        return True
    return any(low <= strategy_id and (high is None or strategy_id <= high) for low, high in intervals)


def _build_group_index(raw_groups: Any) -> tuple[dict[int, dict[str, Any]], int]:
    """把 ``.strategy_group`` 快照转成 ``strategy_id -> 聚合信息`` 索引。

    单个组的 JSON 解析失败只计数不抛错：本操作枚举全量组，一条脏数据不应让整次枚举
    失败；把坏组数量回显出来，比静默丢弃或整体报错都更利于定位。
    """
    if not isinstance(raw_groups, dict):
        raise CustomException(message="共享查询组缓存结构异常")

    index: dict[int, dict[str, Any]] = {}
    malformed = 0
    for raw_group_key, raw_detail in raw_groups.items():
        try:
            detail = json.loads(raw_detail)
        except (TypeError, ValueError):
            malformed += 1
            continue
        if not isinstance(detail, dict):
            malformed += 1
            continue

        group_key = str(raw_group_key)
        bk_biz_id = detail.get("bk_biz_id")
        interval_list = [interval for interval in (detail.get("interval_list") or []) if _is_int_like(interval)]

        for raw_strategy_id, raw_item_ids in detail.items():
            if raw_strategy_id in GROUP_RESERVED_FIELDS or not _is_int_like(raw_strategy_id):
                continue
            if not isinstance(raw_item_ids, list):
                continue
            entry = index.setdefault(
                int(raw_strategy_id),
                {"item_ids": set(), "strategy_group_keys": set(), "interval_list": set(), "bk_biz_id": bk_biz_id},
            )
            entry["strategy_group_keys"].add(group_key)
            entry["interval_list"].update(int(interval) for interval in interval_list)
            entry["item_ids"].update(
                item_id for item_id in raw_item_ids if isinstance(item_id, int) and not isinstance(item_id, bool)
            )
            if entry["bk_biz_id"] is None:
                entry["bk_biz_id"] = bk_biz_id
    return index, malformed


def _serialize_enabled_strategy(
    strategy_id: int, entry: dict[str, Any] | None, *, include_item_ids: bool
) -> dict[str, Any]:
    if entry is None:
        return {"strategy_id": strategy_id, "in_strategy_group": False}
    serialized: dict[str, Any] = {
        "strategy_id": strategy_id,
        "in_strategy_group": True,
        "bk_biz_id": entry["bk_biz_id"],
        "item_count": len(entry["item_ids"]),
        "strategy_group_keys": sorted(entry["strategy_group_keys"]),
        "interval_list": sorted(entry["interval_list"]),
    }
    if include_item_ids:
        serialized["item_ids"] = sorted(entry["item_ids"])
    return serialized


def _resolve_pagination(params: dict[str, Any]) -> tuple[int, int]:
    """解析分页参数。

    不用 ``value or default`` 兜底：那会把 0 静默当成缺省值，掩盖调用方按 0 基分页的
    差一错误——调用方拿到第 1 页却以为自己拿的是第 0 页，且没有任何提示。
    """
    page = _optional_int(params, "page")
    if page is None:
        page = 1
    elif page < 1:
        raise CustomException(message=f"page 必须大于 0: {page}")

    page_size = _optional_int(params, "page_size")
    if page_size is None:
        page_size = DEFAULT_PAGE_SIZE
    elif page_size < 1:
        raise CustomException(message=f"page_size 必须大于 0: {page_size}")
    return page, min(page_size, MAX_PAGE_SIZE)


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _inspect_strategy_detail(params: dict[str, Any]) -> dict[str, Any]:
    strategy_id = _required_int(params, "strategy_id")
    bk_biz_id = _optional_int(params, "bk_biz_id")
    include_user_groups = bool(params.get("include_user_groups", False))
    include_raw_model_ids = bool(params.get("include_raw_model_ids", False))

    try:
        if bk_biz_id is not None:
            strategy_model = StrategyModel.objects.get(bk_biz_id=bk_biz_id, id=strategy_id)
        else:
            strategy_model = StrategyModel.objects.get(id=strategy_id)
    except StrategyModel.DoesNotExist as error:
        detail = f"strategy_id={strategy_id}"
        if bk_biz_id is not None:
            detail = f"bk_biz_id={bk_biz_id}, {detail}"
        raise CustomException(message=f"策略不存在: {detail}") from error

    strategy_config = _build_strategy_config(strategy_model, include_user_groups=include_user_groups)
    return {
        "operation": OPERATION_DETAIL,
        "bk_biz_id": strategy_model.bk_biz_id,
        "strategy_id": strategy_id,
        "strategy": _select_strategy_config(strategy_config, include_raw_model_ids=include_raw_model_ids),
    }


def _list_by_priority_group(params: dict[str, Any]) -> dict[str, Any]:
    bk_biz_id = _required_int(params, "bk_biz_id")
    priority_group_key = str(params.get("priority_group_key") or "").strip()
    if not priority_group_key:
        raise CustomException(message="operation=list_by_priority_group 必须提供 priority_group_key")

    include_disabled = bool(params.get("include_disabled", False))
    include_invalid = bool(params.get("include_invalid", False))

    queryset = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, priority_group_key=priority_group_key)
    if not include_disabled:
        queryset = queryset.filter(is_enabled=True)
    if not include_invalid:
        queryset = queryset.filter(is_invalid=False)
    queryset = queryset.order_by("priority", "id")

    strategies = [_summarize_strategy_model(strategy) for strategy in queryset]
    return {
        "operation": OPERATION_LIST_BY_PRIORITY_GROUP,
        "bk_biz_id": bk_biz_id,
        "priority_group_key": priority_group_key,
        "count": len(strategies),
        "strategies": strategies,
    }


def _build_strategy_config(strategy_model: StrategyModel, *, include_user_groups: bool) -> dict[str, Any]:
    try:
        strategy_obj = Strategy.from_models([strategy_model])[0]
        strategy_obj.restore()
        config = strategy_obj.to_dict()
    except Exception as error:
        raise CustomException(message=f"策略配置解析失败: strategy_id={strategy_model.id}, 原因: {error}") from error

    _inject_strategy_group_key(strategy_model.bk_biz_id, config)

    if include_user_groups:
        try:
            Strategy.fill_user_groups([config])
        except Exception as error:
            raise CustomException(
                message=f"策略通知组填充失败: strategy_id={strategy_model.id}, 原因: {error}"
            ) from error
    return config


def _is_strategy_group_eligible(item: dict[str, Any]) -> bool:
    """判断 item 是否会被 alarm_backends 真实写入 ``STRATEGY_GROUP_CACHE_KEY``。

    复制自 ``alarm_backends/core/cache/strategy.py::StrategyCacheManager.handle_strategy``
    line 571-577。三类条件任一命中才会写入 Redis 策略组：
    - ``data_type_label in (TIME_SERIES, LOG)``
    - ``data_source_label=CUSTOM`` 且 ``data_type_label=EVENT``
    - ``data_source_label=BK_FTA`` 且 ``data_type_label=EVENT``

    与 alarm_backends 一致，**只看 ``query_configs[0]``**（line 531）。

    若 alarm_backends 未来修改此条件，本函数需同步更新——通过对应单测固化该约束。
    """
    from constants.data_source import DataSourceLabel, DataTypeLabel

    query_configs = item.get("query_configs") or []
    if not query_configs:
        return False
    first = query_configs[0] or {}
    data_source_label = first.get("data_source_label")
    data_type_label = first.get("data_type_label")
    is_series = data_type_label in (DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG)
    is_custom_event = data_source_label == DataSourceLabel.CUSTOM and data_type_label == DataTypeLabel.EVENT
    is_fta_event = data_source_label == DataSourceLabel.BK_FTA and data_type_label == DataTypeLabel.EVENT
    return any([is_series, is_custom_event, is_fta_event])


def _inject_strategy_group_key(bk_biz_id: int, config: dict[str, Any]) -> None:
    """给 config.items[i] 默认补 ``strategy_group_key``（即 alarm_backends 的 ``query_md5``）。

    DB 不存这个字段；它由 alarm_backends 运行时基于 query_configs 计算并写入 Redis
    ``STRATEGY_GROUP_CACHE_KEY`` hash。但它是 access 拉数共享 / TokenBucket 流控诊断
    必需的关键证据，agent 在排障时常需要它，因此 detail 默认补全。

    **只对 eligible item 注入**（与 alarm_backends 写入条件严格对齐，见
    ``_is_strategy_group_eligible``）。非 eligible item 在 Redis 中根本没有对应 hash
    field——若误注入会让 agent 拿假 key 查 TokenBucket / checkpoint / duplicate 被带偏。

    ``StrategyCacheManager.get_query_md5`` 是纯计算函数（deepcopy + 字段规范化 + MD5），
    不访问 Redis / DB，开销可忽略。补强字段任何失败都不阻塞 detail 主流程。
    """
    try:
        from alarm_backends.core.cache.strategy import StrategyCacheManager

        for item in config.get("items") or []:
            if not isinstance(item, dict):
                continue
            if not _is_strategy_group_eligible(item):
                continue
            item.setdefault("strategy_group_key", StrategyCacheManager.get_query_md5(bk_biz_id, item))
    except Exception:
        # 补强字段；不阻塞 detail 主路径。
        pass


def _select_strategy_config(config: dict[str, Any], *, include_raw_model_ids: bool) -> dict[str, Any]:
    selected_keys = [
        "id",
        "bk_biz_id",
        "name",
        "source",
        "scenario",
        "type",
        "is_enabled",
        "is_invalid",
        "invalid_type",
        "priority",
        "priority_group_key",
        "items",
        "detects",
        "actions",
        "notice",
        "labels",
        "issue_config",
        "update_time",
        "update_user",
        "create_time",
        "create_user",
    ]
    selected = {key: config.get(key) for key in selected_keys if key in config}
    if include_raw_model_ids:
        selected["raw_model_ids"] = _extract_raw_model_ids(config)
    return selected


def _extract_raw_model_ids(config: dict[str, Any]) -> dict[str, list[int]]:
    return {
        "items": _extract_ids(config.get("items")),
        "detects": _extract_ids(config.get("detects")),
        "actions": _extract_ids(config.get("actions")),
        "notice": _extract_ids([config.get("notice")] if isinstance(config.get("notice"), dict) else []),
    }


def _extract_ids(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_id = value.get("id")
        if isinstance(raw_id, int):
            result.append(raw_id)
    return result


def _summarize_strategy_model(strategy: StrategyModel) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "bk_biz_id": strategy.bk_biz_id,
        "name": strategy.name,
        "scenario": strategy.scenario,
        "type": strategy.type,
        "source": strategy.source,
        "is_enabled": strategy.is_enabled,
        "is_invalid": strategy.is_invalid,
        "invalid_type": strategy.invalid_type,
        "priority": strategy.priority,
        "priority_group_key": strategy.priority_group_key,
        "update_time": str(strategy.update_time) if strategy.update_time is not None else None,
        "update_user": strategy.update_user,
    }


def _required_int(params: dict[str, Any], field_name: str) -> int:
    value = params.get(field_name)
    if value in (None, ""):
        raise CustomException(message=f"inspect-strategy-config 必须提供 {field_name}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


def _optional_int(params: dict[str, Any], field_name: str) -> int | None:
    value = params.get(field_name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


_LIST_ENABLED_PARAMS_SCHEMA = {
    "node_id": "operation=list_enabled 可选，按 CacheRouter 区间过滤该节点承载的策略；与 strategy_id_min/max 互斥",
    "strategy_id_min": "operation=list_enabled 可选，闭区间下界",
    "strategy_id_max": "operation=list_enabled 可选，闭区间上界，省略表示无上界",
    "page": "operation=list_enabled 可选，页码，从 1 开始，默认 1",
    "page_size": f"operation=list_enabled 可选，默认 {DEFAULT_PAGE_SIZE}，上限 {MAX_PAGE_SIZE}",
    "include_item_ids": "operation=list_enabled 可选，是否返回 item_ids 明细，默认 true",
    "include_detect_profile": (
        "operation=list_enabled 可选，是否附带当前页各策略的 point_required / interval / "
        "CHECK_RESULT 旧周期清理口径参考估算；不代表写后即时裁剪的实际峰值或安全上界，"
        "默认 false（启用会额外产生分块 MGET）"
    ),
}

KernelRPCRegistry.register_function(
    func_name="bkm_cli.inspect_strategy_config",
    summary="读取策略聚合配置",
    description=(
        "bkm-cli inspect-strategy-config 后端函数，读取策略详情、优先级分组摘要、"
        "当前 access 共享查询组成员，或批量枚举启用策略与监控项映射。"
    ),
    handler=inspect_strategy_config,
    params_schema={
        "operation": "detail | list_by_priority_group | shared_group | list_enabled",
        "bk_biz_id": "integer",
        "strategy_id": "operation=detail 必填",
        "priority_group_key": "operation=list_by_priority_group 必填",
        "strategy_group_key": "operation=shared_group 必填",
        "include_user_groups": "boolean",
        "include_raw_model_ids": "boolean",
        "include_disabled": "boolean",
        "include_invalid": "boolean",
        **_LIST_ENABLED_PARAMS_SCHEMA,
    },
    example_params={
        "operation": "detail",
        "bk_biz_id": 7,
        "strategy_id": 121950,
        "include_user_groups": True,
    },
)

BkmCliOpRegistry.register(
    op_id="inspect-strategy-config",
    func_name="bkm_cli.inspect_strategy_config",
    summary="读取策略聚合配置",
    description=(
        "通过 monitor-api 服务桥读取策略完整配置、同 priority_group_key 策略摘要、"
        "当前 access 共享查询组成员，或批量枚举启用策略与监控项映射（用于策略级缓存成本核算）。"
    ),
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["db", "strategy", "inspect"],
    params_schema={
        "operation": "detail | list_by_priority_group | shared_group | list_enabled",
        "bk_biz_id": "integer",
        "strategy_id": "integer",
        "priority_group_key": "string",
        "strategy_group_key": "string",
        "include_user_groups": "boolean",
        "include_raw_model_ids": "boolean",
        "include_disabled": "boolean",
        "include_invalid": "boolean",
        **_LIST_ENABLED_PARAMS_SCHEMA,
    },
    example_params={
        "operation": "detail",
        "bk_biz_id": 7,
        "strategy_id": 121950,
        "include_user_groups": True,
    },
)
