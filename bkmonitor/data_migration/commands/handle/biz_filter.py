"""业务数据过滤工具模块

该模块提供按业务ID过滤数据行的功能，支持：
- 直接包含业务ID字段的表
- 需要通过关联表推导业务归属的表
- 全局表识别（返回空数据）

使用示例：
    from data_migration.utils.biz_filter import filter_rows_by_biz

    # 过滤属于目标业务的数据
    filtered = filter_rows_by_biz(rows, "bkmonitor.UserGroup", {19074, 12345})

注意事项：
    - 该模块为独立工具，默认不加载，由调用方按需引入
    - 调用方需确保先处理依赖表，再处理关联表
    - 全局表和未知表返回空列表
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

from data_migration.utils.types import RowDict


class TableBizType(Enum):
    """表业务归属类型"""

    GLOBAL = "global"  # 全局表，无需业务过滤
    HAS_BIZ_ID = "has_biz_id"  # 有业务ID字段（自动检测）
    NEED_RELATION = "need_relation"  # 需要关联推导
    UNKNOWN = "unknown"  # 未配置且无业务ID字段


FieldSpec: TypeAlias = str | tuple[str, ...]
CacheKeyType: TypeAlias = int | str | tuple[int | str, ...]
ResolverContext: TypeAlias = "RelationResolverContext"
RelationResolver: TypeAlias = Callable[[ResolverContext], int | None]


@dataclass(frozen=True)
class RelationRule:
    """关联推导规则

    Attributes:
        foreign_key: 当前表的外键字段，支持单字段或复合字段
        cache_key: 缓存键名，用于从 _RELATION_BIZ_CACHE 中查找映射
        resolver: 自定义推导函数，优先使用
    """

    foreign_key: FieldSpec | None = None
    cache_key: str | None = None
    resolver: RelationResolver | None = None


@dataclass(frozen=True)
class RelationResolverContext:
    """自定义推导上下文

    Attributes:
        row: 当前行数据
        model_label: 模型标签
        relation_cache: 关联缓存
        rows_by_model: 预加载的模型数据（可选）
    """

    row: RowDict
    model_label: str
    relation_cache: dict[str, dict[CacheKeyType, int]]
    rows_by_model: dict[str, list[RowDict]] | None = None


@dataclass(frozen=True)
class CacheSourceConfig:
    """缓存源表配置

    Attributes:
        cache_key: 缓存键名，用于从 _RELATION_BIZ_CACHE 中查找映射
        pk_field: 主键字段，支持单字段或复合字段，默认使用 id
    """

    cache_key: str
    pk_field: FieldSpec = "id"


# =====================================================================
# 配置（先不实现 metadata 相关表）
# =====================================================================

# 支持的业务ID字段列表（按优先级排序）
BIZ_ID_FIELDS: list[str] = ["bk_biz_id", "cc_biz_id"]

# 全局表列表（无需业务过滤，返回空）
GLOBAL_TABLES: set[str] = {
    # apm 模块
    "apm.FieldNormalizerConfig",
    # bkmonitor 模块
    "bkmonitor.EventPluginV2",
    "bkmonitor.ActionPlugin",
    "bkmonitor.MonitorMigration",
    "bkmonitor.ApiAuthToken",
    # calendars 模块
    "calendars.CalendarModel",
    "calendars.CalendarItemModel",
    # fta_web 模块
    "fta_web.SearchHistory",
    "fta_web.SearchFavorite",
    "fta_web.AlertFeedback",
    # monitor_web 模块
    "monitor_web.OperatorSystem",
    "monitor_web.UploadedFileInfo",
    "monitor_web.DataTargetMapping",
}

# 需要关联推导的表 -> 关联规则
RELATION_RULES: dict[str, RelationRule] = {
    # =========================================================================
    # bkmonitor 模块
    # =========================================================================
    # 策略配置链路
    "bkmonitor.StrategyHistoryModel": RelationRule("strategy_id", "strategy"),
    "bkmonitor.QueryConfigModel": RelationRule("strategy_id", "strategy"),
    "bkmonitor.ItemModel": RelationRule("strategy_id", "strategy"),
    "bkmonitor.DetectModel": RelationRule("strategy_id", "strategy"),
    "bkmonitor.AlgorithmModel": RelationRule("strategy_id", "strategy"),
    "bkmonitor.StrategyActionConfigRelation": RelationRule("strategy_id", "strategy"),
    # 值班与用户组链路
    "bkmonitor.DutyArrange": RelationRule("user_group_id", "user_group"),
    "bkmonitor.DutyArrangeSnap": RelationRule("user_group_id", "user_group"),
    "bkmonitor.DutyPlan": RelationRule("user_group_id", "user_group"),
    "bkmonitor.DutyPlanSendRecord": RelationRule("user_group_id", "user_group"),
    "bkmonitor.DutyRuleSnap": RelationRule("duty_rule_id", "duty_rule"),
    # 报表订阅链路
    "bkmonitor.ReportChannel": RelationRule("report_id", "report"),
    # 插件实例链路
    "bkmonitor.AlertConfig": RelationRule("plugin_instance_id", "event_plugin_instance"),
    # =========================================================================
    # monitor_web 模块
    # =========================================================================
    # 自定义上报链路
    "monitor_web.CustomTSField": RelationRule("time_series_group_id", "custom_ts_table"),
    "monitor_web.CustomTSGroupingRule": RelationRule("time_series_group_id", "custom_ts_table"),
    # CustomEventItem.bk_event_group 是 ForeignKey，导出时字段名是 bk_event_group 而非 bk_event_group_id
    "monitor_web.CustomEventItem": RelationRule("bk_event_group", "custom_event_group"),
    # 采集配置链路
    "monitor_web.DeploymentConfigVersion": RelationRule("config_meta_id", "collect_config_meta"),
    # 插件信息与配置链路（需通过版本历史反查）
    "monitor_web.CollectorPluginInfo": RelationRule(resolver=lambda ctx: _resolve_collector_plugin_info(ctx)),
    "monitor_web.CollectorPluginConfig": RelationRule(resolver=lambda ctx: _resolve_collector_plugin_config(ctx)),
    # 插件版本链路
    "monitor_web.PluginVersionHistory": RelationRule(("bk_tenant_id", "plugin_id"), "collector_plugin_meta"),
    # 拨测链路
    "monitor_web.UptimeCheckTaskCollectorLog": RelationRule("task_id", "uptime_check_task"),
    # =========================================================================
    # apm_web 模块
    # =========================================================================
    # APM 应用链路
    "apm_web.ApplicationRelationInfo": RelationRule("application_id", "apm_application"),
    # APM 元数据配置链路
    "apm_web.ApmMetaConfig": RelationRule(resolver=lambda ctx: _resolve_apm_meta_config(ctx)),
    # 报表内容链路
    "bkmonitor.ReportContents": RelationRule(resolver=lambda ctx: _resolve_report_contents(ctx)),
    "bkmonitor.ReportItems": RelationRule(resolver=lambda ctx: _resolve_report_items(ctx)),
}

# 配置：哪些表需要构建缓存供其他表使用
# 格式: {model_label: CacheSourceConfig}
CACHE_SOURCE_TABLES: dict[str, CacheSourceConfig] = {
    # bkmonitor 模块
    "bkmonitor.StrategyModel": CacheSourceConfig("strategy"),
    "bkmonitor.UserGroup": CacheSourceConfig("user_group"),
    "bkmonitor.DutyRule": CacheSourceConfig("duty_rule"),
    "bkmonitor.Report": CacheSourceConfig("report"),
    "bkmonitor.EventPluginInstance": CacheSourceConfig("event_plugin_instance"),
    "bkmonitor.ActionConfig": CacheSourceConfig("action_config"),
    # monitor_web 模块
    # CustomTSTable 的主键是 time_series_group_id，不是默认的 id
    "monitor_web.CustomTSTable": CacheSourceConfig("custom_ts_table", "time_series_group_id"),
    # CustomEventGroup 的主键是 bk_event_group_id，不是默认的 id
    "monitor_web.CustomEventGroup": CacheSourceConfig("custom_event_group", "bk_event_group_id"),
    "monitor_web.CollectConfigMeta": CacheSourceConfig("collect_config_meta"),
    "monitor_web.CollectorPluginMeta": CacheSourceConfig("collector_plugin_meta", ("bk_tenant_id", "plugin_id")),
    "monitor_web.UptimeCheckTask": CacheSourceConfig("uptime_check_task"),
    # apm_web 模块
    "apm_web.Application": CacheSourceConfig("apm_application", "application_id"),
}

# 需要额外预加载的模型（用于自定义关联推导）
EXTRA_PRELOAD_MODELS: set[str] = {
    "monitor_web.PluginVersionHistory",
    "bkmonitor.ReportContents",
}


# =====================================================================
# 内部缓存机制
# =====================================================================

# 内部缓存：{cache_key: {pk_value: bk_biz_id}}
_RELATION_BIZ_CACHE: dict[str, dict[CacheKeyType, int]] = {}
_ROWS_BY_MODEL: dict[str, list[RowDict]] | None = None

_PLUGIN_CONFIG_CACHE_KEY = "collector_plugin_config"
_PLUGIN_INFO_CACHE_KEY = "collector_plugin_info"
_REPORT_ITEM_CACHE_KEY = "report_item"


# =====================================================================
# 内部工具函数
# =====================================================================


def _detect_biz_field(row: RowDict) -> str | None:
    """检测行数据中的业务ID字段

    按 BIZ_ID_FIELDS 优先级检查，返回第一个存在的字段名

    Args:
        row: 数据行

    Returns:
        业务ID字段名，如果不存在则返回 None
    """
    for field in BIZ_ID_FIELDS:
        if field in row:
            return field
    return None


def _normalize_biz_id(value: Any) -> int | None:
    """规范化业务ID值，兼容数值型和字符串

    Args:
        value: 原始值（可能是 int、str、None 等）

    Returns:
        整数类型的业务ID，无效值返回 None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _normalize_key(value: Any) -> int | str | None:
    """规范化主键值，兼容数值型和字符串

    Args:
        value: 原始值（可能是 int、str、None 等）

    Returns:
        标准化后的主键，无效值返回 None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value
    return None


def _extract_cache_key(row: RowDict, field_spec: FieldSpec) -> CacheKeyType | None:
    """从数据行中提取缓存键

    Args:
        row: 数据行
        field_spec: 字段规格，单字段或复合字段

    Returns:
        缓存键值，单字段返回单值，复合字段返回元组
    """
    if isinstance(field_spec, str):
        return _normalize_key(row.get(field_spec))
    values: list[int | str] = []
    for field in field_spec:
        normalized = _normalize_key(row.get(field))
        if normalized is None:
            return None
        values.append(normalized)
    return tuple(values)


def _build_cache_from_rows(
    rows: list[RowDict],
    cache_key: str,
    pk_field: FieldSpec,
    biz_field: str,
) -> None:
    """从数据行构建缓存

    Args:
        rows: 数据行列表
        cache_key: 缓存键名
        pk_field: 主键字段名
        biz_field: 业务ID字段名
    """
    cache_dict = _RELATION_BIZ_CACHE.setdefault(cache_key, {})
    for row in rows:
        pk = _extract_cache_key(row, pk_field)
        biz_id = _normalize_biz_id(row.get(biz_field))
        if pk is not None and biz_id is not None:
            cache_dict[pk] = biz_id


def _get_relation_cache(cache_key: str) -> dict[CacheKeyType, int]:
    """获取指定缓存键的映射数据。"""
    return _RELATION_BIZ_CACHE.setdefault(cache_key, {})


def _parse_graphs_biz_id(graphs: Any) -> int | None:
    """从 graphs 字段解析唯一业务ID。"""
    graph_list = graphs
    if isinstance(graphs, str):
        try:
            graph_list = json.loads(graphs)
        except json.JSONDecodeError:
            return None
    if not isinstance(graph_list, list):
        return None
    biz_ids: set[int] = set()
    for graph in graph_list:
        if not isinstance(graph, str):
            continue
        prefix = graph.split("-", 1)[0]
        biz_id = _normalize_biz_id(prefix)
        if biz_id is not None:
            biz_ids.add(biz_id)
    if len(biz_ids) == 1:
        return next(iter(biz_ids))
    return None


def _parse_service_level_biz_id(level_key: Any) -> int | None:
    """从服务级别 key 中解析业务ID。"""
    if not isinstance(level_key, str):
        return None
    prefix = level_key.split("-", 1)[0]
    return _normalize_biz_id(prefix)


def _build_plugin_version_relation_cache(rows_by_model: dict[str, list[RowDict]]) -> None:
    """构建插件版本到业务的反查缓存。"""
    plugin_meta_cache = _RELATION_BIZ_CACHE.get("collector_plugin_meta")
    if not plugin_meta_cache:
        return
    version_rows = rows_by_model.get("monitor_web.PluginVersionHistory")
    if not version_rows:
        return
    config_cache = _get_relation_cache(_PLUGIN_CONFIG_CACHE_KEY)
    info_cache = _get_relation_cache(_PLUGIN_INFO_CACHE_KEY)
    for row in version_rows:
        plugin_key = _extract_cache_key(row, ("bk_tenant_id", "plugin_id"))
        if plugin_key is None:
            continue
        biz_id = plugin_meta_cache.get(plugin_key)
        if biz_id is None:
            continue
        # ForeignKey 字段在导出时使用 field.name（config/info），而非 column（config_id/info_id）
        config_id = _normalize_key(row.get("config"))
        info_id = _normalize_key(row.get("info"))
        if config_id is not None:
            config_cache[config_id] = biz_id
        if info_id is not None:
            info_cache[info_id] = biz_id


def _build_report_item_relation_cache(rows_by_model: dict[str, list[RowDict]]) -> None:
    """构建报表订阅ID到业务的映射缓存。"""
    contents_rows = rows_by_model.get("bkmonitor.ReportContents")
    if not contents_rows:
        return
    report_item_cache = _get_relation_cache(_REPORT_ITEM_CACHE_KEY)
    conflicts: set[CacheKeyType] = set()
    for row in contents_rows:
        report_item_id = _normalize_key(row.get("report_item"))
        if report_item_id is None:
            continue
        biz_id = _parse_graphs_biz_id(row.get("graphs"))
        if biz_id is None:
            continue
        existing = report_item_cache.get(report_item_id)
        if existing is None and report_item_id not in conflicts:
            report_item_cache[report_item_id] = biz_id
        elif existing is not None and existing != biz_id:
            report_item_cache.pop(report_item_id, None)
            conflicts.add(report_item_id)


def _resolve_collector_plugin_config(context: RelationResolverContext) -> int | None:
    """通过版本历史反查插件配置归属。"""
    config_id = _normalize_key(context.row.get("id"))
    if config_id is None:
        return None
    return context.relation_cache.get(_PLUGIN_CONFIG_CACHE_KEY, {}).get(config_id)


def _resolve_collector_plugin_info(context: RelationResolverContext) -> int | None:
    """通过版本历史反查插件信息归属。"""
    info_id = _normalize_key(context.row.get("id"))
    if info_id is None:
        return None
    return context.relation_cache.get(_PLUGIN_INFO_CACHE_KEY, {}).get(info_id)


def _resolve_apm_meta_config(context: RelationResolverContext) -> int | None:
    """根据配置级别推导 APM 元数据配置归属。"""
    config_level = context.row.get("config_level")
    level_key = context.row.get("level_key")
    if config_level == "bk_biz_level":
        return _normalize_biz_id(level_key)
    if config_level == "application_level":
        application_id = _normalize_key(level_key)
        if application_id is None:
            return None
        return context.relation_cache.get("apm_application", {}).get(application_id)
    if config_level == "service_level":
        return _parse_service_level_biz_id(level_key)
    return None


def _resolve_report_contents(context: RelationResolverContext) -> int | None:
    """从报表内容的 graphs 字段解析业务归属。"""
    return _parse_graphs_biz_id(context.row.get("graphs"))


def _resolve_report_items(context: RelationResolverContext) -> int | None:
    """通过报表内容反查订阅报表归属。"""
    report_item_id = _normalize_key(context.row.get("id"))
    if report_item_id is None:
        return None
    return context.relation_cache.get(_REPORT_ITEM_CACHE_KEY, {}).get(report_item_id)


# =====================================================================
# 公开 API
# =====================================================================


def get_table_biz_type(model_label: str, first_row: RowDict | None = None) -> TableBizType:
    """获取表的业务归属类型

    Args:
        model_label: 模型标签（app_label.ModelName）
        first_row: 表的第一行数据（用于判断是否有业务ID字段）

    Returns:
        表的业务归属类型
    """
    if model_label in GLOBAL_TABLES:
        return TableBizType.GLOBAL
    if model_label in RELATION_RULES:
        return TableBizType.NEED_RELATION
    if first_row and _detect_biz_field(first_row):
        return TableBizType.HAS_BIZ_ID
    return TableBizType.UNKNOWN


def preload_relation_cache(rows_by_model: dict[str, list[RowDict]]) -> None:
    """预加载缓存源表的业务关系缓存。

    Args:
        rows_by_model: 模型数据映射，key 为 model_label，value 为行列表
    """
    if not rows_by_model:
        return

    global _ROWS_BY_MODEL
    _ROWS_BY_MODEL = rows_by_model

    for model_label, rows in rows_by_model.items():
        if model_label not in CACHE_SOURCE_TABLES:
            continue
        if not rows:
            continue
        biz_field = _detect_biz_field(rows[0])
        if not biz_field:
            continue
        config = CACHE_SOURCE_TABLES[model_label]
        _build_cache_from_rows(rows, config.cache_key, config.pk_field, biz_field)

    _build_plugin_version_relation_cache(rows_by_model)
    _build_report_item_relation_cache(rows_by_model)


def clear_cache() -> None:
    """清除所有缓存（可选，用于重置状态）

    在需要重新开始数据处理时调用，以清除之前构建的缓存。
    """
    _RELATION_BIZ_CACHE.clear()
    global _ROWS_BY_MODEL
    _ROWS_BY_MODEL = None


def get_cache_info() -> dict[str, int]:
    """获取当前缓存信息（调试用）

    Returns:
        各缓存键对应的条目数量
    """
    return {key: len(value) for key, value in _RELATION_BIZ_CACHE.items()}


def get_row_biz_id(row: RowDict, model_label: str | None = None) -> int | None:
    """获取行数据的业务ID

    优先从直接字段（bk_biz_id/cc_biz_id）获取，如果不存在且提供了 model_label，
    则尝试从关联缓存中获取。

    Args:
        row: 数据行
        model_label: 模型标签（app_label.ModelName），用于关联推导

    Returns:
        业务ID，如果无法确定则返回 None

    Note:
        - 如果表需要通过关联推导获取业务ID，必须确保依赖表已经处理过
          （缓存已构建）
        - 全局表返回 None
    """
    # 1. 优先从直接字段获取
    biz_field = _detect_biz_field(row)
    if biz_field:
        return _normalize_biz_id(row.get(biz_field))

    # 2. 如果提供了 model_label，尝试从关联缓存获取
    if model_label and model_label in RELATION_RULES:
        rule = RELATION_RULES[model_label]
        if rule.resolver:
            context = RelationResolverContext(
                row=row,
                model_label=model_label,
                relation_cache=_RELATION_BIZ_CACHE,
                rows_by_model=_ROWS_BY_MODEL,
            )
            resolved = rule.resolver(context)
            if resolved is not None or (rule.foreign_key is None and rule.cache_key is None):
                return resolved
        if rule.foreign_key and rule.cache_key:
            cache_dict = _RELATION_BIZ_CACHE.get(rule.cache_key, {})
            foreign_key_value = _extract_cache_key(row, rule.foreign_key)
            if foreign_key_value is not None:
                return cache_dict.get(foreign_key_value)

    return None
