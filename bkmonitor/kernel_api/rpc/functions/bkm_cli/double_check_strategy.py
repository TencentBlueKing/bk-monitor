"""bkm-cli 二次确认策略配置查询与受控管理。"""

import json
from typing import Any

from django.conf import settings
from django.db import transaction

from bkmonitor.models.config import GlobalConfig
from bkmonitor.models.strategy import StrategyModel
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.strategy import _build_strategy_config, _is_strategy_group_eligible


CONFIG_KEY = "DOUBLE_CHECK_SUM_STRATEGY_IDS"
CACHE_PROPAGATION_MAX_SECONDS = 180

FUNC_QUERY_DOUBLE_CHECK_STRATEGIES = "bkm_cli.query_double_check_strategies"
FUNC_MANAGE_DOUBLE_CHECK_STRATEGY = "bkm_cli.manage_double_check_strategy"

QUERY_OPERATIONS = {"capabilities", "list", "impact"}
MUTATION_OPERATIONS = {"enable", "disable"}

DOUBLE_CHECK_DATA_SCOPES = {
    ("bk_monitor", "time_series"),
    ("custom", "time_series"),
    ("bk_data", "time_series"),
}
DOUBLE_CHECK_ALGORITHM_TYPES = {"IntelligentDetect", "AdvancedRingRatio", "SimpleRingRatio", "Threshold"}


def _normalize_text(value: Any, field_name: str, *, required: bool = False, max_length: int = 64) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise CustomException(message=f"{field_name} 为必填项")
    if len(text) > max_length:
        raise CustomException(message=f"{field_name} 长度不能超过 {max_length}")
    return text


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise CustomException(message=f"{field_name} 必须是正整数")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是正整数") from error
    if result <= 0 or (isinstance(value, float) and not value.is_integer()):
        raise CustomException(message=f"{field_name} 必须是正整数")
    return result


def _normalize_strategy_ids(value: Any) -> list[int]:
    if isinstance(value, str):
        value = value.replace("\n", ",").split(",")
    if value is None:
        return []
    if not isinstance(value, list | tuple | set):
        raise CustomException(message=f"{CONFIG_KEY} 必须是策略 ID 列表")

    strategy_ids = []
    for raw_strategy_id in value:
        if raw_strategy_id in (None, ""):
            continue
        strategy_id = _positive_int(raw_strategy_id, CONFIG_KEY)
        if strategy_id not in strategy_ids:
            strategy_ids.append(strategy_id)
    return strategy_ids


def _configured_strategy_ids() -> list[int]:
    config = GlobalConfig.objects.filter(key=CONFIG_KEY).last()
    value = config.value if config is not None else getattr(settings, CONFIG_KEY)
    return _normalize_strategy_ids(value)


def _serialize_strategy(strategy: StrategyModel | None, strategy_id: int) -> dict[str, Any]:
    if strategy is None:
        return {"strategy_id": strategy_id, "exists": False}
    return {
        "strategy_id": strategy.id,
        "exists": True,
        "bk_biz_id": strategy.bk_biz_id,
        "name": strategy.name,
        "is_enabled": strategy.is_enabled,
        "is_invalid": strategy.is_invalid,
        "invalid_type": strategy.invalid_type,
        "update_time": str(strategy.update_time) if strategy.update_time is not None else None,
        "update_user": strategy.update_user,
    }


def _strategy_summary(strategy_id: int) -> dict[str, Any]:
    return _serialize_strategy(StrategyModel.objects.filter(id=strategy_id).first(), strategy_id)


def _is_item_double_check_eligible(item: dict[str, Any]) -> bool:
    query_configs = item.get("query_configs") or []
    algorithms = item.get("algorithms") or []
    if len(query_configs) != 1:
        return False
    query_config = query_configs[0]
    scope = (query_config.get("data_source_label"), query_config.get("data_type_label"))
    return (
        scope in DOUBLE_CHECK_DATA_SCOPES
        and query_config.get("agg_method") == "SUM"
        and any(algorithm.get("type") in DOUBLE_CHECK_ALGORITHM_TYPES for algorithm in algorithms)
    )


def _strategy_config(strategy_id: int) -> tuple[StrategyModel | None, dict[str, Any]]:
    strategy = StrategyModel.objects.filter(id=strategy_id).first()
    if strategy is None:
        return None, {}
    return strategy, _build_strategy_config(strategy, include_user_groups=False)


def _validate_strategy_for_enable(strategy_id: int) -> dict[str, Any]:
    strategy, config = _strategy_config(strategy_id)
    if strategy is None:
        raise CustomException(message=f"策略不存在: {strategy_id}")
    if not strategy.is_enabled or strategy.is_invalid:
        raise CustomException(message=f"策略未启用或已失效，不能开启二次确认: {strategy_id}")
    if not any(_is_item_double_check_eligible(item) for item in config.get("items") or []):
        raise CustomException(message=f"策略没有适用 SUM 二次确认的监控项: {strategy_id}")
    return _serialize_strategy(strategy, strategy_id)


def _strategy_groups(strategy_id: int) -> list[dict[str, Any]]:
    """从单次 Redis hash 快照反查策略的全部运行态共享组。

    陈旧策略已经没有 StrategyModel，无法靠静态配置计算 group key。这里使用一次
    HGETALL 保证完整性并避免逐组 HGET 的 N+1；该路径仅用于低频管理 impact 查询。
    """
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    raw_groups = StrategyCacheManager.get_all_groups()
    if not isinstance(raw_groups, dict):
        raise CustomException(message="共享查询组缓存结构异常")

    groups = []
    for raw_group_key, raw_detail in raw_groups.items():
        try:
            detail = json.loads(raw_detail)
        except (TypeError, ValueError) as error:
            raise CustomException(message=f"共享查询组缓存结构异常: {raw_group_key}") from error
        if not isinstance(detail, dict):
            raise CustomException(message=f"共享查询组缓存结构异常: {raw_group_key}")
        if str(strategy_id) not in detail:
            continue

        member_strategy_ids = []
        for raw_member_strategy_id, raw_item_ids in detail.items():
            try:
                member_strategy_id = int(raw_member_strategy_id)
            except (TypeError, ValueError):
                continue
            if not isinstance(raw_item_ids, list):
                raise CustomException(message=f"共享查询组缓存结构异常: {raw_group_key}")
            member_strategy_ids.append(member_strategy_id)

        groups.append(
            {
                "strategy_group_key": str(raw_group_key),
                "runtime_group_found": True,
                "bk_biz_id": detail.get("bk_biz_id"),
                "member_strategy_ids": sorted(member_strategy_ids),
                "target_strategy_member_found": True,
            }
        )
    return sorted(groups, key=lambda group: group["strategy_group_key"])


def _access_runtime_group_expected(strategy_id: int, strategy: dict[str, Any]) -> bool:
    """判断当前有效策略是否按 access 语义应存在运行态共享组。"""
    if not strategy.get("exists") or not strategy.get("is_enabled") or strategy.get("is_invalid"):
        return False

    _, config = _strategy_config(strategy_id)
    return any(_is_strategy_group_eligible(item) for item in config.get("items") or [])


def _query_list() -> dict[str, Any]:
    configured_strategy_ids = _configured_strategy_ids()
    strategies = {strategy.id: strategy for strategy in StrategyModel.objects.filter(id__in=configured_strategy_ids)}
    items = [_serialize_strategy(strategies.get(strategy_id), strategy_id) for strategy_id in configured_strategy_ids]
    return {
        "operation": "list",
        "configured_strategy_ids": configured_strategy_ids,
        "items": items,
        "total": len(items),
        "stale_strategy_ids": [item["strategy_id"] for item in items if not item["exists"]],
    }


def _query_impact(params: dict[str, Any]) -> dict[str, Any]:
    strategy_id = _positive_int(params.get("strategy_id"), "strategy_id")
    change = _normalize_text(params.get("change"), "change", required=True)
    if change not in MUTATION_OPERATIONS:
        raise CustomException(message=f"change 仅支持: {sorted(MUTATION_OPERATIONS)}")

    strategy = _validate_strategy_for_enable(strategy_id) if change == "enable" else _strategy_summary(strategy_id)
    before_ids = _configured_strategy_ids()
    after_ids = list(before_ids)
    if change == "enable" and strategy_id not in after_ids:
        after_ids.append(strategy_id)
    if change == "disable":
        after_ids = [item for item in after_ids if item != strategy_id]

    before_set = set(before_ids)
    after_set = set(after_ids)
    groups = []
    for group in _strategy_groups(strategy_id):
        member_ids = group["member_strategy_ids"]
        configured_before = sorted(before_set.intersection(member_ids))
        configured_after = sorted(after_set.intersection(member_ids))
        groups.append(
            {
                **group,
                "configured_member_strategy_ids_before": configured_before,
                "configured_member_strategy_ids_after": configured_after,
                "access_protected_before": bool(configured_before),
                "access_protected_after": bool(configured_after),
            }
        )

    runtime_membership_missing = not groups and (
        change == "enable" or _access_runtime_group_expected(strategy_id, strategy)
    )

    return {
        "operation": "impact",
        "change": change,
        "strategy_id": strategy_id,
        "changed": before_ids != after_ids,
        "strategy": strategy,
        "detect": {"before": strategy_id in before_set, "after": strategy_id in after_set},
        "groups": groups,
        "access_impact_complete": not runtime_membership_missing
        and all(group["runtime_group_found"] and group["target_strategy_member_found"] for group in groups),
        "configured_strategy_ids_before": before_ids,
        "configured_strategy_ids_after": after_ids,
    }


@KernelRPCRegistry.register(
    FUNC_QUERY_DOUBLE_CHECK_STRATEGIES,
    summary="查询二次确认策略配置与变更影响",
    description="查询显式策略名单，并按 access 共享查询组和 detect 显式策略两种语义预览 enable/disable 影响。",
    params_schema={
        "operation": "必填，capabilities/list/impact",
        "strategy_id": "impact 必填",
        "change": "impact 必填，enable/disable",
    },
    example_params={"operation": "impact", "strategy_id": 1, "change": "enable"},
)
def query_double_check_strategies(params: dict[str, Any]) -> dict[str, Any]:
    operation = _normalize_text(params.get("operation"), "operation", required=True)
    if operation not in QUERY_OPERATIONS:
        raise CustomException(message=f"operation 仅支持: {sorted(QUERY_OPERATIONS)}")
    if operation == "capabilities":
        return {
            "operation": operation,
            "config_key": CONFIG_KEY,
            "mutations": sorted(MUTATION_OPERATIONS),
            "access_scope": "shared_query_group",
            "detect_scope": "explicit_strategy",
            "impact_requires_current_shared_group": True,
            "cache_propagation_max_seconds": CACHE_PROPAGATION_MAX_SECONDS,
        }
    if operation == "list":
        return _query_list()
    return _query_impact(params)


def _require_mutation_confirmation(params: dict[str, Any]) -> str:
    if "dry_run" in params:
        raise CustomException(message="二次确认策略管理不支持 dry_run；请先查询影响并取得人工确认")
    if params.get("confirmed") is not True:
        raise CustomException(message="写操作必须先取得人工确认，并传入 confirmed=true")
    return _normalize_text(params.get("operator"), "operator", required=True, max_length=32)


def _clear_dynamic_setting_cache(name: str) -> None:
    wrapped = getattr(settings, "_wrapped", None)
    for cache_name in ("_locmem_cache", "_redis_cache"):
        cache = getattr(wrapped, cache_name, None)
        if cache is not None:
            cache.delete(name)


@KernelRPCRegistry.register(
    FUNC_MANAGE_DOUBLE_CHECK_STRATEGY,
    summary="管理二次确认策略配置",
    description="经人工确认后启用或停用单个策略的 SUM 二次确认配置；返回 GlobalConfig 数据库回读。",
    params_schema={
        "operation": "必填，enable/disable",
        "strategy_id": "必填，正整数",
        "confirmed": "必填，必须为 true",
        "operator": "必填，最近操作人",
    },
    example_params={"operation": "enable", "strategy_id": 1, "confirmed": False, "operator": "admin"},
)
def manage_double_check_strategy(params: dict[str, Any]) -> dict[str, Any]:
    operation = _normalize_text(params.get("operation"), "operation", required=True)
    if operation not in MUTATION_OPERATIONS:
        raise CustomException(message=f"operation 仅支持: {sorted(MUTATION_OPERATIONS)}")
    strategy_id = _positive_int(params.get("strategy_id"), "strategy_id")
    operator = _require_mutation_confirmation(params)
    if operation == "enable":
        _validate_strategy_for_enable(strategy_id)

    with transaction.atomic(using=GlobalConfig.objects.db):
        config = GlobalConfig.objects.select_for_update().filter(key=CONFIG_KEY).first()
        current_ids = _normalize_strategy_ids(config.value if config is not None else getattr(settings, CONFIG_KEY))
        updated_ids = list(current_ids)
        if operation == "enable" and strategy_id not in updated_ids:
            updated_ids.append(strategy_id)
        if operation == "disable":
            updated_ids = [item for item in updated_ids if item != strategy_id]
        changed = current_ids != updated_ids

        if config is None and changed:
            config = GlobalConfig.objects.create(key=CONFIG_KEY, value=updated_ids, data_type="List")
        elif changed:
            config.value = updated_ids
            config.save(update_fields=["value", "update_at"])
        if config is not None:
            config.refresh_from_db()

    if changed:
        _clear_dynamic_setting_cache(CONFIG_KEY)

    return {
        "operation": operation,
        "strategy_id": strategy_id,
        "changed": changed,
        "configured_strategy_ids": updated_ids,
        "requested_operator": operator,
        "db_readback": (
            {"present": True, "key": config.key, "value": config.value, "update_at": config.update_at}
            if config is not None
            else {"present": False}
        ),
        "cache_propagation_max_seconds": CACHE_PROPAGATION_MAX_SECONDS,
    }


BkmCliOpRegistry.register(
    op_id="query-double-check-strategies",
    func_name=FUNC_QUERY_DOUBLE_CHECK_STRATEGIES,
    summary="查询二次确认策略配置与影响",
    description="查询显式策略名单，并分别呈现 access 共享组保护与 detect 显式策略二次确认的变更影响。",
    capability_level="admin",
    risk_level="readonly",
    requires_confirmation=False,
    audit_tags=["double-check", "strategy", "admin", "readonly"],
    params_schema={"operation": "capabilities/list/impact", "strategy_id": "impact 必填", "change": "enable/disable"},
    example_params={"operation": "impact", "strategy_id": 1, "change": "enable"},
)

BkmCliOpRegistry.register(
    op_id="manage-double-check-strategy",
    func_name=FUNC_MANAGE_DOUBLE_CHECK_STRATEGY,
    summary="启用或停用二次确认策略",
    description="二次确认策略配置写操作；必须先查询影响并取得人工明确确认。",
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["double-check", "strategy", "admin", "mutation", "human-confirmation"],
    params_schema={
        "operation": "enable/disable",
        "strategy_id": "正整数",
        "confirmed": "boolean，必须为 true",
        "operator": "string，最近操作人",
    },
    example_params={"operation": "enable", "strategy_id": 1, "confirmed": False, "operator": "admin"},
)
