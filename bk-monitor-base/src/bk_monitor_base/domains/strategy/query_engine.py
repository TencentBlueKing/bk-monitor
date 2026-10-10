"""StrategyQueryEngine：策略列表筛选引擎（V2 语义迁移）。

设计原则：
- 复刻现网 `GetStrategyListV2Resource.filter_by_conditions()` 的“条件归一化 + 逐条件交集”语义
- 跨表反查统一通过 `StrategyIdResolvers`，避免上层散落 ORM 拼装
- 对于 heavy 条件（IP/屏蔽/ES/自定义分组），按约定“忽略不生效”
- 对未知/不支持 key，按约定“忽略不生效”（兼容前端乱传）

补充说明：
- 本引擎的职责是“把条件映射成一系列可复用的 strategy_id 过滤步骤”，并维护交集语义。
- 对于部分复杂条件（如自定义事件/指标分组、metric_field_name/alias），推荐由外部先解析为
  `result_table_id` / `metric_field`（列表），再传入本引擎进行交集过滤。

入参约定（推荐的条件格式，FilterSpec 风格）：
- `conditions` 为列表，每个元素形如：

  - `{"key": "<field>", "values": [...], "operator": "<op>"}`

- 字段含义：
  - **key**：字段名（支持 v2 的部分别名映射，如 `strategy_name -> name`）。
  - **values**：仅保留多值形式（即使只有一个值，也用 list 承载）。
  - **operator**：匹配方式（可选，默认 `eq`），支持：
    - `eq`：精确匹配（多值等价 IN，OR）
    - `neq`：排除匹配（多值等价 NOT IN，AND）
    - `contains`/`icontains`：子串匹配（多值按 OR）
    - `startswith`/`endswith`：前后缀匹配（多值按 OR）
"""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from collections.abc import Iterable
from functools import reduce
from typing import Any, Literal, Self, TypedDict, cast

from django.db.models import ExpressionWrapper, F, Q, QuerySet, fields

from bk_monitor_base.domains.strategy.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyLabel,
    StrategyModel,
    UserGroup,
)

# === 条件结构（FilterSpec 风格）===
FilterOperator = Literal["eq", "neq", "contains", "icontains", "startswith", "endswith"]


class FilterCondition(TypedDict, total=False):
    """FilterSpec 风格条件。

    Notes:
        - 只接受 `values + operator`；`values` 建议始终为 list（即使只有一个值）。
    """

    key: str
    values: list[Any]
    operator: FilterOperator | str


class _NormalizedCondition(TypedDict):
    key: str
    operator: FilterOperator
    values: list[Any]


class StrategyIdResolvers:
    """策略 ID 反查器。

    约定：
    - 方法统一返回 `set[int]`
    - 若传入 `candidates`，返回结果会与 candidates 求交集
    - 若筛选值为空：
      - candidates 不为空：直接返回 candidates（等价于“本条件不生效”）
      - candidates 为空：返回空集合（避免在未知全集情况下误返回“全量”）

    使用建议：
    - 上层应当以 `candidates` 作为“当前候选策略集”，每应用一个条件就做一次交集，
      这样能尽早缩小范围，降低后续模糊匹配（如 `__icontains`）的开销。
    """

    @staticmethod
    def _coerce_int(value: Any) -> int:
        """尽可能把 value 转成 int。

        说明：
        - Django values_list/JSONField 读取出来的类型在静态类型检查中往往是 Unknown/Any
        - 这里做一次集中转换，避免在各处散落 cast/ignore
        """
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(str(value))

    @staticmethod
    def _as_set(values: Iterable[int] | QuerySet[Any]) -> set[int]:
        """将 iterable/queryset 转为 set[int]。"""
        if isinstance(values, QuerySet):
            return {StrategyIdResolvers._coerce_int(v) for v in cast(Iterable[Any], values)}
        return {StrategyIdResolvers._coerce_int(v) for v in values}

    @staticmethod
    def _intersect(result: set[int], candidates: set[int] | None) -> set[int]:
        """与候选集求交集。"""
        if candidates is None:
            return result
        return result & candidates

    @classmethod
    def _resolve_strategy_ids_by_query_config_config_field(
        cls,
        *,
        field_lookup: str,
        values: Iterable[str],
        candidates: set[int] | None = None,
    ) -> set[int]:
        """通用的 QueryConfig.config[...] 反查 strategy_id 实现。

        说明：
        - `resolve_strategy_ids_by_result_table_*` 等方法的核心差异仅在于 lookup 不同
          （如 `config__result_table_id` / `config__result_table_id__startswith` / `__icontains`）。
        - 这里将“组装 OR 条件 + candidates 收敛 + values_list 转 set”统一收敛，避免重复代码。

        Args:
            field_lookup: Django ORM lookup 字符串（如 `config__result_table_id__startswith`）。
            values: 待匹配的值列表（会自动去空白/空串）。
            candidates: 可选候选策略集。

        Returns:
            命中的策略 ID 集合（已与 candidates 求交集/收敛）。
        """
        value_list = [str(v) for v in values if str(v).strip()]
        if not value_list:
            return candidates if candidates is not None else set()

        condition = reduce(lambda x, y: x | y, (Q(**{field_lookup: v}) for v in value_list))
        qs = QueryConfigModel.objects.filter(condition)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_by_metric_ids(
        cls, metric_ids: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.metric_id 反查策略 ID。

        Args:
            metric_ids: 指标 ID 列表（如 `bk_monitor.cpu_usage`）。
            candidates: 可选的候选策略集；传入时将附加 `strategy_id__in` 过滤。

        Returns:
            满足条件的策略 ID 集合。
        """
        metric_id_list = list(metric_ids)
        if not metric_id_list:
            return candidates if candidates is not None else set()

        qs = QueryConfigModel.objects.filter(metric_id__in=metric_id_list)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_by_result_table_ids(
        cls, result_table_ids: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.config.result_table_id 精确匹配反查策略 ID。

        说明：
        - 这是一种“精确匹配”能力，适合外部已将复杂条件（如自定义指标/事件组）解析为
          `table_id` 列表后，直接下发为过滤条件。

        Args:
            result_table_ids: 结果表 ID 列表（如 `2_system.cpu`）。
            candidates: 可选候选策略集。

        Returns:
            满足条件的策略 ID 集合。
        """
        return cls._resolve_strategy_ids_by_query_config_config_field(
            field_lookup="config__result_table_id",
            values=result_table_ids,
            candidates=candidates,
        )

    @classmethod
    def resolve_strategy_ids_by_result_table_id_prefixes(
        cls, prefixes: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.config.result_table_id 前缀（startswith）反查策略 ID。

        典型用途：
        - 外部将插件/采集器等维度解析为前缀（如 `<plugin_id>.`），在 base 侧进行前缀过滤；
        - 将多种 table_id 变体收敛为同一前缀，减少外部传参量。

        性能注意：
        - `startswith` 通常可比 `icontains` 更可控，但依赖实际数据库/索引情况。

        Args:
            prefixes: 前缀列表。
            candidates: 可选候选策略集。

        Returns:
            满足条件的策略 ID 集合。
        """
        return cls._resolve_strategy_ids_by_query_config_config_field(
            field_lookup="config__result_table_id__startswith",
            values=prefixes,
            candidates=candidates,
        )

    @classmethod
    def resolve_strategy_ids_by_result_table_id_contains(
        cls, keywords: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.config.result_table_id 关键字（icontains）反查策略 ID。

        说明：
        - 该能力主要用于“搜索兜底”，当外部无法准确给出 table_id 或前缀时，
          可用关键字做宽松匹配。

        性能注意：
        - `icontains` 通常意味着 LIKE %xxx%，在数据量大时可能较重；
          推荐尽量在候选集已收敛（传入 candidates）后使用。

        Args:
            keywords: 关键字列表。
            candidates: 可选候选策略集。

        Returns:
            满足条件的策略 ID 集合。
        """
        return cls._resolve_strategy_ids_by_query_config_config_field(
            field_lookup="config__result_table_id__icontains",
            values=keywords,
            candidates=candidates,
        )

    @classmethod
    def resolve_strategy_ids_by_metric_fields(
        cls, metric_fields: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.config.metric_field 精确匹配反查策略 ID。

        说明：
        - `metric_field` 是策略查询配置里用于表达“指标字段”的核心字段；
          现网 `metric_field_name/alias` 本质上也是先映射为 `metric_field` 再过滤。
        - base 侧不引入 metadata/缓存映射逻辑时，推荐由外部先完成别名映射，
          再将 `metric_field` 列表下发到本方法。

        Args:
            metric_fields: 指标字段列表（如 `cpu_usage`）。
            candidates: 可选候选策略集。

        Returns:
            满足条件的策略 ID 集合。
        """
        return cls._resolve_strategy_ids_by_query_config_config_field(
            field_lookup="config__metric_field",
            values=metric_fields,
            candidates=candidates,
        )

    @classmethod
    def resolve_strategy_ids_by_metric_field_contains(
        cls, keywords: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 QueryConfig.config.metric_field 关键字（icontains）反查策略 ID。

        说明：
        - 当外部无法提供精确的 metric_field（例如仅有关键字），可用该方法做宽松匹配。

        性能注意：
        - `icontains` 可能较重；强烈建议配合 candidates 缩小范围。

        Args:
            keywords: 关键字列表。
            candidates: 可选候选策略集。

        Returns:
            满足条件的策略 ID 集合。
        """
        return cls._resolve_strategy_ids_by_query_config_config_field(
            field_lookup="config__metric_field__icontains",
            values=keywords,
            candidates=candidates,
        )

    @classmethod
    def resolve_strategy_ids_by_data_sources(
        cls, pairs: Iterable[tuple[str, str]], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 (data_source_label, data_type_label) 反查策略 ID。"""
        pairs_list = list(pairs)
        if not pairs_list:
            return candidates if candidates is not None else set()
        condition = reduce(
            lambda x, y: x | y,
            (Q(data_source_label=ds, data_type_label=dt) for ds, dt in pairs_list),
        )
        qs = QueryConfigModel.objects.filter(condition)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_by_uptime_check_task_ids(
        cls, task_ids: Iterable[int | str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按拨测任务 ID 反查策略。

        说明：
        - 复用现网 v2 逻辑：仅扫描 `metric_id` 以 `bk_monitor.uptimecheck.` 开头的 QueryConfig
        - 从 `config.agg_condition` 里解析 `task_id` 条件（key=task_id, method=eq）
        """
        task_id_list = list(task_ids)
        if not task_id_list:
            return candidates if candidates is not None else set()

        task_id_set = {str(t) for t in task_id_list}
        qs = QueryConfigModel.objects.filter(metric_id__startswith="bk_monitor.uptimecheck.")
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)

        matched: set[int] = set()
        for query_config in qs.only("strategy_id", "config"):
            config: dict[str, Any] = query_config.config or {}
            agg_conditions_any: Any = config.get("agg_condition", [])
            if not isinstance(agg_conditions_any, list):
                continue

            agg_conditions = cast(list[Any], agg_conditions_any)
            for agg_condition_any in agg_conditions:
                if not isinstance(agg_condition_any, dict):
                    continue
                agg_condition = cast(dict[str, Any], agg_condition_any)
                if agg_condition.get("key") != "task_id" or agg_condition.get("method") != "eq":
                    continue
                value_any: Any = agg_condition.get("value")
                if isinstance(value_any, list):
                    values = {str(cast(object, v)) for v in cast(list[Any], value_any)}
                else:
                    values = {str(cast(object, value_any))}
                if values & task_id_set:
                    matched.add(int(query_config.strategy_id))
                    break

        return cls._intersect(matched, candidates)

    @classmethod
    def resolve_strategy_ids_by_algorithm_types(
        cls, types: Iterable[str], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按 Algorithm.type 反查策略 ID。"""
        type_list = list(types)
        if not type_list:
            return candidates if candidates is not None else set()

        qs = AlgorithmModel.objects.filter(type__in=type_list)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_by_levels(cls, levels: Iterable[int], *, candidates: set[int] | None = None) -> set[int]:
        """按 Detect.level 反查策略 ID。"""
        level_list = list(levels)
        if not level_list:
            return candidates if candidates is not None else set()

        qs = DetectModel.objects.filter(level__in=level_list)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_by_user_group_ids(
        cls, user_group_ids: Iterable[int], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按通知组 ID 反查策略 ID（StrategyActionConfigRelation.user_groups contains）。"""
        group_ids = {int(g) for g in user_group_ids if g}
        if not group_ids:
            return candidates if candidates is not None else set()

        condition = reduce(lambda x, y: x | y, (Q(user_groups__contains=gid) for gid in group_ids))
        qs = StrategyActionConfigRelation.objects.filter(condition)
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_with_actions(
        cls, action_config_ids: Iterable[int], *, candidates: set[int] | None = None
    ) -> set[int]:
        """按处理套餐 ID 反查策略 ID。"""
        ids = [int(i) for i in action_config_ids if int(i) > 0]
        if not ids:
            return candidates if candidates is not None else set()

        qs = StrategyActionConfigRelation.objects.filter(
            relate_type=StrategyActionConfigRelation.RelateType.ACTION,
            config_id__in=ids,
        )
        if candidates is not None:
            qs = qs.filter(strategy_id__in=candidates)
        return cls._as_set(qs.values_list("strategy_id", flat=True).distinct())

    @classmethod
    def resolve_strategy_ids_without_actions(
        cls, *, bk_biz_id: int | None = None, candidates: set[int] | None = None
    ) -> set[int]:
        """反查“未配置处理套餐”的策略 ID。"""
        strategy_qs = StrategyModel.objects.all()
        if bk_biz_id is not None:
            strategy_qs = strategy_qs.filter(bk_biz_id=bk_biz_id)
        if candidates is not None:
            strategy_qs = strategy_qs.filter(id__in=candidates)
        all_ids = cls._as_set(strategy_qs.values_list("id", flat=True).distinct())
        if not all_ids:
            return set()

        with_action_qs = StrategyActionConfigRelation.objects.filter(
            relate_type=StrategyActionConfigRelation.RelateType.ACTION,
            strategy_id__in=all_ids,
        )
        with_action_ids = cls._as_set(with_action_qs.values_list("strategy_id", flat=True).distinct())
        return all_ids - with_action_ids

    @classmethod
    def resolve_strategy_ids_by_status(
        cls, status: str, *, bk_biz_id: int | None = None, candidates: set[int] | None = None
    ) -> set[int]:
        """按策略状态反查策略 ID。

        当前仅支持：
        - ON: is_enabled=True
        - OFF: is_enabled=False
        - INVALID: is_invalid=True

        不支持（按约定暂不实现）：
        - ALERT / SHIELDED：依赖 ES 与屏蔽检测逻辑
        """
        status_upper = str(status or "").upper()
        if status_upper in {"ALERT", "SHIELDED"}:
            raise NotImplementedError("status ALERT/SHIELDED requires ES/shield logic; not implemented yet")

        qs = StrategyModel.objects.all()
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)
        if candidates is not None:
            qs = qs.filter(id__in=candidates)

        if status_upper == "INVALID":
            qs = qs.filter(is_invalid=True)
        elif status_upper == "ON":
            qs = qs.filter(is_enabled=True)
        elif status_upper == "OFF":
            qs = qs.filter(is_enabled=False)
        else:
            raise NotImplementedError(f"unsupported status '{status}'")

        return cls._as_set(qs.values_list("id", flat=True).distinct())


class StrategyQueryEngine:
    """策略筛选引擎（V2 条件归一化 + 逐条件交集）。"""

    # v2 field_mapping 复刻
    _FIELD_MAPPING: dict[str, str] = {
        "strategy_id": "id",
        "strategy_name": "name",
        "task_id": "uptime_check_task_id",
        "metric_name": "metric_field",
        "creators": "create_user",
        "updaters": "update_user",
        "data_source_list": "data_source",
        "label_name": "label",
    }

    # heavy 条件（按约定忽略）
    _HEAVY_KEYS: set[str] = {
        "ip",
        "bk_cloud_id",
        "custom_event_group_id",
        "bk_event_group_id",
        "time_series_group_id",
    }

    @classmethod
    def filter_strategies(
        cls: type[Self],
        bk_biz_id: int | None = None,
        *,
        conditions: list[FilterCondition],
        scenario: str | None = None,
        base_qs: QuerySet[StrategyModel] | None = None,
    ) -> QuerySet[StrategyModel]:
        """按条件过滤策略列表（保持 v2 的“逐条件交集”语义）。

        Args:
            bk_biz_id: 业务 ID，如果为 None，则查询所有业务ID的策略
            conditions: 条件列表。推荐每项形如 `{"key": "...", "values": [...], "operator": "eq|neq|..."}`
                详见模块顶部“入参约定（FilterSpec 风格）”。
            scenario: 可选场景过滤（与 v2 一致，作为额外过滤）。
            base_qs: 可选候选 queryset（默认 `StrategyModel.objects.filter(bk_biz_id=...)` 的语义）。

        Returns:
            过滤后的策略 queryset。

        ## 多值语义（由 operator 推断）
        - `eq`: 多值等价 IN（OR）
        - `neq`: 多值等价 NOT IN（AND）
        - `contains/icontains/startswith/endswith`: 多值按 OR（任意一个命中即可）

        ## 支持的字段与 operator（逐字段清单）
        ### StrategyModel 字段
        - `bk_biz_id`: `eq/neq`（数值）
        - `id`: `eq/neq`（数值）
        - `name`: `eq/neq/contains/icontains/startswith/endswith`（字符串）
        - `label`: `eq/neq`（字符串；会自动规范化为 `/a/b/` 形式）
        - `invalid_type`: `eq/neq`（枚举/字符串）
        - `source`: `eq/neq`（枚举/字符串；不提供模糊）
        - `app`: `eq/neq`（字符串；不提供模糊）
        - `create_user`: `eq/neq`（字符串；不提供模糊）
        - `update_user`: `eq/neq`（字符串；不提供模糊）
        - `scenario`: `eq/neq`（字符串；不提供模糊；也可通过入参 `scenario` 直接过滤）
        - `updated_after_create`: `eq/neq`（布尔；固定阈值 1 秒：`update_time - create_time > 1s`）

        ### QueryConfigModel.config(JSON) 字段（跨表反查 strategy_id）
        - `result_table_id`: `eq/neq/startswith/endswith/contains/icontains`
        - `metric_field`: `eq/neq/startswith/endswith/contains/icontains`
        - `metric_id`: `eq/neq`（QueryConfigModel.metric_id）

        ### 其它关联表（跨表反查）
        - `algorithm_type`: `eq/neq`
        - `level`: `eq/neq`（数值）
        - `strategy_status`: `eq/neq`
          - 仅支持 `ON/OFF/INVALID`；`ALERT/SHIELDED` 视为 heavy 并忽略
        - `uptime_check_task_id`: `eq/neq`（拨测任务；通过解析 QueryConfig.config.agg_condition）

        ### 通知组/处理套餐（保持 v2 语义；operator 支持较少）
        - `user_group_id`: 仅 `eq`（数值；与 `user_group_name` 合并后一次过滤）
        - `user_group_name`: `contains/icontains`（用于把名称映射为 user_group_id；与上面合并）
        - `action_id`: 仅 `eq`（数值；支持 `0` 表示 without_actions）
        - `action_name`: 仅 `eq`（字符串；内部按 `name__contains` 做匹配；与 `action_id` 合并）

        ### 特殊字段
        - `query`: 关键字搜索（OR 语义），operator 忽略
          - 命中规则：`name__icontains` OR `id=int(query)` OR `result_table_id == query`

        ## 忽略策略（兼容性）
        - 未知 key：忽略（不报错，结果可能偏大）
        - 某 key 的不支持 operator：忽略该条件（不报错）
        - heavy key：`ip/bk_cloud_id/custom_event_group_id/bk_event_group_id/time_series_group_id` 直接忽略

        ## 性能提示
        - `contains/icontains` 往往比 `eq/startswith` 更重，建议外部优先做精确解析，
          或先通过其它条件收敛候选集（本实现会尽早做交集以减少后续开销）。
        """
        qs = base_qs or StrategyModel.objects.all()
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)
        if scenario:
            qs = qs.filter(scenario=scenario)

        # 初始候选集合：以当前 qs 为准
        candidates: set[int] = cls._parse_ints(cast(Iterable[Any], qs.values_list("id", flat=True).distinct()))
        if not candidates:
            return qs.none()

        normalized = cls._normalize_conditions(conditions)
        query_keywords: list[str] = []
        # user_group/action 需要在 v2 语义下“合并后再过滤”（而不是分别过滤再求交集）
        pending_user_group_ids: set[int] = set()
        pending_user_group_names: list[str] = []
        use_user_group_name_icontains = False
        pending_action_ids: list[Any] = []
        pending_action_names: list[Any] = []

        for cond in normalized:
            # NOTE: basedpyright 在复杂控制流里会把 set 运算结果降级为 `set[int] | Unknown`；
            # 这里做一次显式锚定，避免后续 resolver / _apply_hit 调用持续产生告警。
            candidates = cast(set[int], candidates)  # pyright: ignore[reportUnnecessaryCast]
            key: str = cond["key"]
            op: FilterOperator = cond["operator"]
            values_any: list[Any] = cond["values"]

            if key in cls._HEAVY_KEYS:
                continue

            # 特殊：关键字 query 先收集，统一在末尾对候选 queryset 做 OR 过滤
            if key == "query":
                query_keywords.extend([str(v) for v in values_any if str(v).strip()])
                continue

            if key == "id":
                ids = cls._parse_ints(values_any)
                if not ids:
                    continue
                candidates = cls._apply_hit(candidates=candidates, hit=ids, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "label":
                # label 固定按 `/a/b/` 规则规范化，仅支持 eq/neq
                if op not in {"eq", "neq"}:
                    continue
                labels = [
                    f"/{str(label_value).strip('/')}/" for label_value in values_any if str(label_value).strip("/")
                ]
                if not labels:
                    continue
                label_ids = cls._parse_ints(
                    cast(
                        Iterable[Any],
                        StrategyLabel.objects.filter(label_name__in=labels, bk_biz_id=bk_biz_id)
                        .values_list("strategy_id", flat=True)
                        .distinct(),
                    )
                )
                candidates = cls._apply_hit(candidates=candidates, hit=label_ids, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "data_source":
                # 数据源：只支持 eq/neq（外部预处理成 `<data_source_label>|<data_type_label>` 或 `<ds>,<dt>`）
                if op not in {"eq", "neq"}:
                    continue
                raw_pairs = [str(v) for v in values_any if str(v).strip()]
                pairs: list[tuple[str, str]] = []
                for raw_pair in raw_pairs:
                    pair = cls._parse_data_source_pair(raw_pair)
                    if pair is not None:
                        pairs.append(pair)
                if not pairs:
                    # v2 语义：传了 data_source 但无法解析 => 空结果（eq）；neq 则无效果
                    if op == "eq":
                        return qs.none()
                    continue
                ds_hit = StrategyIdResolvers.resolve_strategy_ids_by_data_sources(pairs, candidates=candidates)
                candidates = cls._apply_hit(candidates=candidates, hit=ds_hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "result_table_id":
                # 字符串字段：支持 eq/neq/startswith/icontains/contains/endswith（多值按 OR）
                rt_values = [str(v) for v in values_any if str(v).strip()]
                if not rt_values:
                    continue
                rt_hit: set[int]
                if op == "eq":
                    rt_hit = StrategyIdResolvers.resolve_strategy_ids_by_result_table_ids(
                        rt_values, candidates=candidates
                    )
                elif op == "neq":
                    rt_hit = StrategyIdResolvers.resolve_strategy_ids_by_result_table_ids(
                        rt_values, candidates=candidates
                    )
                elif op == "startswith":
                    rt_hit = StrategyIdResolvers.resolve_strategy_ids_by_result_table_id_prefixes(
                        rt_values, candidates=candidates
                    )
                elif op in {"contains", "icontains"}:
                    rt_hit = StrategyIdResolvers.resolve_strategy_ids_by_result_table_id_contains(
                        rt_values, candidates=candidates
                    )
                elif op == "endswith":
                    q_rt = reduce(operator.or_, (Q(config__result_table_id__endswith=v) for v in rt_values))
                    rt_hit = cls._parse_ints(
                        cast(
                            Iterable[Any],
                            QueryConfigModel.objects.filter(q_rt, strategy_id__in=candidates)
                            .values_list("strategy_id", flat=True)
                            .distinct(),
                        )
                    )
                else:
                    continue
                candidates = cls._apply_hit(candidates=candidates, hit=rt_hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "metric_field":
                # 字符串字段：支持 eq/neq/icontains/contains/startswith/endswith（多值按 OR）
                metric_values = [str(v) for v in values_any if str(v).strip()]
                if not metric_values:
                    continue
                metric_hit: set[int]
                if op == "eq":
                    metric_hit = StrategyIdResolvers.resolve_strategy_ids_by_metric_fields(
                        metric_values, candidates=candidates
                    )
                elif op == "neq":
                    metric_hit = StrategyIdResolvers.resolve_strategy_ids_by_metric_fields(
                        metric_values, candidates=candidates
                    )
                elif op in {"contains", "icontains"}:
                    metric_hit = StrategyIdResolvers.resolve_strategy_ids_by_metric_field_contains(
                        metric_values, candidates=candidates
                    )
                elif op in {"startswith", "endswith"}:
                    lookup = "startswith" if op == "startswith" else "endswith"
                    q_metric = reduce(
                        operator.or_, (Q(**{f"config__metric_field__{lookup}": v}) for v in metric_values)
                    )
                    metric_hit = cls._parse_ints(
                        cast(
                            Iterable[Any],
                            QueryConfigModel.objects.filter(q_metric, strategy_id__in=candidates)
                            .values_list("strategy_id", flat=True)
                            .distinct(),
                        )
                    )
                else:
                    continue
                candidates = cls._apply_hit(candidates=candidates, hit=metric_hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "metric_id":
                if op not in {"eq", "neq"}:
                    continue
                metric_ids = [str(v) for v in values_any if str(v).strip()]
                if not metric_ids:
                    continue
                hit = StrategyIdResolvers.resolve_strategy_ids_by_metric_ids(metric_ids, candidates=candidates)
                candidates = cls._apply_hit(candidates=candidates, hit=hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "uptime_check_task_id":
                if op not in {"eq", "neq"}:
                    continue
                if not values_any:
                    continue
                hit = StrategyIdResolvers.resolve_strategy_ids_by_uptime_check_task_ids(
                    values_any, candidates=candidates
                )
                candidates = cls._apply_hit(candidates=candidates, hit=hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "algorithm_type":
                if op not in {"eq", "neq"}:
                    continue
                algo_types = [str(v) for v in values_any if str(v).strip()]
                if not algo_types:
                    continue
                hit = StrategyIdResolvers.resolve_strategy_ids_by_algorithm_types(algo_types, candidates=candidates)
                candidates = cls._apply_hit(candidates=candidates, hit=hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "level":
                if op not in {"eq", "neq"}:
                    continue
                levels = cls._parse_ints(values_any)
                if not levels:
                    continue
                hit = StrategyIdResolvers.resolve_strategy_ids_by_levels(levels, candidates=candidates)
                candidates = cls._apply_hit(candidates=candidates, hit=hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "strategy_status":
                # 状态：仅支持 ON/OFF/INVALID（ALERT/SHIELDED 视为 heavy 忽略）
                if op not in {"eq", "neq"}:
                    continue
                statuses = [str(v).upper() for v in values_any if str(v).strip()]
                supported = [s for s in statuses if s in {"ON", "OFF", "INVALID"}]
                if not supported:
                    continue
                status_union: set[int] = set()
                for s in supported:
                    status_union |= StrategyIdResolvers.resolve_strategy_ids_by_status(
                        s, bk_biz_id=bk_biz_id, candidates=candidates
                    )
                candidates = cls._apply_hit(candidates=candidates, hit=status_union, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "invalid_type":
                if op not in {"eq", "neq"}:
                    continue
                invalid_types = [str(v) for v in values_any if str(v).strip()]
                if not invalid_types:
                    continue
                invalid_qs = StrategyModel.objects.filter(id__in=candidates)
                invalid_qs = (
                    invalid_qs.filter(invalid_type__in=invalid_types)
                    if op == "eq"
                    else invalid_qs.exclude(invalid_type__in=invalid_types)
                )
                candidates = cls._parse_ints(cast(Iterable[Any], invalid_qs.values_list("id", flat=True).distinct()))
                if not candidates:
                    return qs.none()
                continue

            if key == "bk_biz_id":
                if op not in {"eq", "neq"}:
                    continue
                bk_biz_ids = cls._parse_ints(values_any)
                if not bk_biz_ids:
                    continue
                candidates = cls._apply_hit(candidates=candidates, hit=bk_biz_ids, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()

            if key in {"app", "create_user", "update_user", "scenario", "source"}:
                # 枚举/字符串字段：仅支持 eq/neq（不提供模糊）
                if op not in {"eq", "neq"}:
                    continue
                values = [str(v) for v in values_any if str(v).strip()]
                if not values:
                    continue
                field_name = key
                f_qs = StrategyModel.objects.filter(id__in=candidates)
                if op == "eq":
                    f_qs = f_qs.filter(**{f"{field_name}__in": values})
                else:
                    f_qs = f_qs.exclude(**{f"{field_name}__in": values})
                candidates = cls._parse_ints(cast(Iterable[Any], f_qs.values_list("id", flat=True).distinct()))
                if not candidates:
                    return qs.none()
                continue

            if key == "updated_after_create":
                # 判断策略“创建后有过修改”：
                # - 复刻现网思路：用数据库侧计算 update_time-create_time 的 Duration，避免拉取到 Python 计算
                # - 固定阈值 1 秒：`update_time - create_time > 1s` 视为有过修改
                if op not in {"eq", "neq"}:
                    continue
                bool_values = cls._parse_bools(values_any)
                if not bool_values:
                    continue

                # NOTE: basedpyright 在复杂控制流里可能将 candidates 推断为 Unknown；
                # 这里用一次显式 cast 锚定类型，避免后续 set 运算告警。
                candidates_set = cast(set[int], candidates)

                # 仅在当前 candidates 内计算，降低 annotate/filter 成本
                annotated_qs = StrategyModel.objects.filter(id__in=candidates_set).annotate(
                    time_difference=ExpressionWrapper(
                        F("update_time") - F("create_time"),
                        output_field=fields.DurationField(),
                    )
                )
                modified_ids = cls._parse_ints(
                    cast(
                        Iterable[Any],
                        annotated_qs.filter(time_difference__gt=datetime.timedelta(seconds=1))
                        .values_list("id", flat=True)
                        .distinct(),
                    )
                )

                hit: set[int] = set()
                if True in bool_values:
                    hit |= modified_ids
                if False in bool_values:
                    hit |= candidates_set - modified_ids

                candidates = cls._apply_hit(candidates=candidates_set, hit=hit, exclude=(op == "neq"))
                if not candidates:
                    return qs.none()
                continue

            if key == "user_group_id":
                # 告警组：仅支持 eq（合并 id/name 后一次过滤）；其它 operator 忽略
                if op == "eq":
                    pending_user_group_ids |= set(cls._parse_ints(values_any))
                continue

            if key == "user_group_name":
                # 告警组名称：仅用于把名称映射为 ID（合并后一次过滤）
                if values_any:
                    pending_user_group_names.extend([str(v) for v in values_any if str(v).strip()])
                if op == "icontains":
                    use_user_group_name_icontains = True
                continue

            if key == "action_id":
                # 动作：仅支持 eq（合并 id/name 后一次过滤）；其它 operator 忽略
                if op == "eq":
                    pending_action_ids.extend(values_any)
                continue

            if key == "action_name":
                if op == "eq":
                    pending_action_names.extend(values_any)
                continue

            if key == "name":
                # 策略名称：支持 eq/neq/contains/icontains/startswith/endswith（多值按 OR）
                name_values = [str(v) for v in values_any if str(v).strip()]
                if not name_values:
                    continue
                if op in {"eq", "neq"}:
                    name_qs = StrategyModel.objects.filter(id__in=candidates)
                    name_qs = (
                        name_qs.filter(name__in=name_values) if op == "eq" else name_qs.exclude(name__in=name_values)
                    )
                    candidates = cls._parse_ints(cast(Iterable[Any], name_qs.values_list("id", flat=True).distinct()))
                elif op in {"contains", "icontains", "startswith", "endswith"}:
                    lookup = "icontains" if op in {"contains", "icontains"} else op
                    q_name = reduce(operator.or_, (Q(**{f"name__{lookup}": n}) for n in name_values))
                    candidates = cls._parse_ints(
                        cast(
                            Iterable[Any],
                            StrategyModel.objects.filter(id__in=candidates)
                            .filter(q_name)
                            .values_list("id", flat=True)
                            .distinct(),
                        )
                    )
                else:
                    continue
                if not candidates:
                    return qs.none()
                continue

            # 未知 key：忽略（兼容策略）

        # user_group：合并 id/name 后一次过滤（v2 语义）
        if pending_user_group_ids or pending_user_group_names:
            group_ids = set(pending_user_group_ids)
            if pending_user_group_names:
                name_op = "icontains" if use_user_group_name_icontains else "contains"
                name_q = reduce(operator.or_, (Q(**{f"name__{name_op}": n}) for n in pending_user_group_names))
                group_ids |= cls._parse_ints(
                    cast(
                        Iterable[Any],
                        UserGroup.objects.filter(name_q, bk_biz_id=bk_biz_id).values_list("id", flat=True).distinct(),
                    )
                )

            # 与旧实现一致：只要出现过相关条件，但无法解析出 id，则视为无匹配
            if not group_ids:
                return qs.none()

            group_hit = StrategyIdResolvers.resolve_strategy_ids_by_user_group_ids(group_ids, candidates=candidates)
            candidates = cls._apply_hit(candidates=candidates, hit=group_hit, exclude=False)
            if not candidates:
                return qs.none()

        # action：合并 id/name 后一次过滤（v2 语义，包含 without_actions）
        if pending_action_ids or pending_action_names:
            filter_dict: defaultdict[str, list[Any]] = defaultdict(list)
            if pending_action_ids:
                filter_dict["action_id"].extend(pending_action_ids)
            if pending_action_names:
                filter_dict["action_name"].extend(pending_action_names)
            candidates = cls._apply_action_filter(bk_biz_id=bk_biz_id, filter_dict=filter_dict, candidates=candidates)
            if not candidates:
                return qs.none()

        # 基于 candidates 构造最终 queryset
        qs = qs.filter(id__in=candidates)

        # query（关键字：name icontains OR id eq OR result_table_id 命中）
        if query_keywords:
            q_parts: list[Q] = []
            rt_hit_ids: set[int] = set()
            for q in query_keywords:
                q_parts.append(Q(name__icontains=q))
                try:
                    q_parts.append(Q(id=int(q)))
                except (TypeError, ValueError):
                    pass
                rt_hit_ids |= StrategyIdResolvers.resolve_strategy_ids_by_result_table_ids([q], candidates=candidates)
            if rt_hit_ids:
                q_parts.append(Q(id__in=rt_hit_ids))
            if q_parts:
                qs = qs.filter(reduce(operator.or_, q_parts))

        return qs

    @classmethod
    def _normalize_conditions(cls, conditions: list[FilterCondition]) -> list[_NormalizedCondition]:
        """条件归一化：key mapping + values 统一 + operator 解析。

        输出是“条件列表”，而不是 dict：这样才能表达“同一 key 的多次出现”（例如用多条条件实现 AND 语义）。
        """
        normalized: list[_NormalizedCondition] = []
        for condition in conditions or []:
            raw_key = str(condition.get("key", "")).strip().lower()
            if not raw_key:
                continue

            # v2 field_mapping
            mapped_key = cls._FIELD_MAPPING.get(raw_key, raw_key)

            # 只接受 values（多值形式）；其它字段一律忽略（由上层负责转换）
            value_any: Any = condition.get("values")
            if value_any is None:
                continue

            if isinstance(value_any, list):
                values = cast(list[Any], value_any)
            else:
                values = [value_any]

            raw_operator = str(condition.get("operator", "")).strip().lower()
            operator_value: FilterOperator
            if raw_operator in {"eq", "neq", "contains", "icontains", "startswith", "endswith"}:
                operator_value = cast(FilterOperator, raw_operator)
            else:
                operator_value = "eq"

            normalized.append({"key": mapped_key, "operator": operator_value, "values": values})

        return normalized

    @staticmethod
    def _parse_data_source_pair(value: str) -> tuple[str, str] | None:
        """解析 data_source 组合值为 (data_source_label, data_type_label)。

        支持格式：
        - `<data_source_label>|<data_type_label>`
        - `<data_source_label>,<data_type_label>`
        """
        raw = str(value).strip()
        if not raw:
            return None
        if "|" in raw:
            left, right = raw.split("|", 1)
        elif "," in raw:
            left, right = raw.split(",", 1)
        else:
            return None
        ds = left.strip()
        dt = right.strip()
        if not ds or not dt:
            return None
        return ds, dt

    @staticmethod
    def _parse_ints(values: Iterable[Any]) -> set[int]:
        result: set[int] = set()
        for v in values:
            try:
                result.add(int(v))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _parse_bools(values: Iterable[Any]) -> set[bool]:
        """将 values 尽可能解析为 bool 集合。

        说明：
            - 该方法用于 FilterSpec 风格条件的 `values` 解析，兼容前端/调用方常见传参形态。
            - 仅识别以下值：
              - True/False
              - 0/1（int 或 str）
              - "true"/"false"（大小写不敏感）

        Args:
            values: 原始值列表。

        Returns:
            解析后的布尔值集合；若无可识别值则返回空集合。
        """
        result: set[bool] = set()
        for raw in values:
            if isinstance(raw, bool):
                result.add(raw)
                continue
            if isinstance(raw, int):
                if raw in {0, 1}:
                    result.add(bool(raw))
                continue
            if raw is None:
                continue
            s = str(raw).strip().lower()
            if s in {"true", "1"}:
                result.add(True)
            elif s in {"false", "0"}:
                result.add(False)
        return result

    @staticmethod
    def _apply_hit(*, candidates: set[int], hit: set[int], exclude: bool) -> set[int]:
        """对候选集应用一次交集/排除。

        Notes:
            - 用显式的入参/返回类型“锚定” set 运算，避免类型检查器在复杂控制流中将结果降级为 Unknown。
        """

        return (candidates - hit) if exclude else (candidates & hit)

    @classmethod
    def _apply_action_filter(
        cls: type[Self], *, bk_biz_id: int | None, filter_dict: dict[str, list[Any]], candidates: set[int]
    ) -> set[int]:
        """复刻 v2 的处理套餐筛选语义（包含 without_actions 特殊值）。"""
        action_id_values = filter_dict.get("action_id", [])
        action_name_values = filter_dict.get("action_name", [])

        want_without_actions = (0 in cls._parse_ints(action_id_values)) or any(str(v) == "" for v in action_name_values)
        without_actions_ids: set[int] = set()
        if want_without_actions:
            without_actions_ids = StrategyIdResolvers.resolve_strategy_ids_without_actions(
                bk_biz_id=bk_biz_id, candidates=candidates
            )

        # 组装 ActionConfig 筛选条件
        conditions: list[Q] = []
        for name in action_name_values:
            name_str = str(name)
            if name_str:
                conditions.append(Q(name__contains=name_str))
        for aid in cls._parse_ints(action_id_values):
            if aid > 0:
                conditions.append(Q(id=aid))

        if not conditions:
            # 没有 other 条件：仅应用 without_actions（若需要）
            return candidates & without_actions_ids if want_without_actions else candidates

        # ActionConfig.bk_biz_id 是 CharField：兼容存 0 与业务 ID 字符串
        action_biz_ids = ["0", str(bk_biz_id)] if bk_biz_id is not None else ["0"]
        action_qs = ActionConfig.objects.exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID).filter(
            bk_biz_id__in=action_biz_ids
        )
        action_ids = list(action_qs.filter(reduce(operator.or_, conditions)).values_list("id", flat=True).distinct())
        if not action_ids and not want_without_actions:
            # 有明确 action 条件但无匹配：空结果（与 v2 对齐）
            return set()

        relate_qs = StrategyActionConfigRelation.objects.filter(config_id__in=action_ids)
        if candidates:
            relate_qs = relate_qs.filter(strategy_id__in=candidates)
        with_action_ids = cls._parse_ints(
            cast(Iterable[Any], relate_qs.values_list("strategy_id", flat=True).distinct())
        )
        return candidates & (with_action_ids | without_actions_ids)
