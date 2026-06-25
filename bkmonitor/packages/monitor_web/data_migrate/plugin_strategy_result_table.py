from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from bkmonitor.models import QueryConfigModel, StrategyModel
from monitor_web.models import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import PluginType

TARGET_PLUGIN_TYPES = (
    PluginType.SCRIPT,
    PluginType.EXPORTER,
    PluginType.PUSHGATEWAY,
    PluginType.DATADOG,
    PluginType.JMX,
)
DEFAULT_TABLE_NAME = "__default__"


@dataclass(frozen=True)
class PluginResultTable:
    plugin_id: str
    plugin_type: str
    bk_biz_id: int
    result_table_prefix: str
    default_result_table_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_type": self.plugin_type,
            "bk_biz_id": self.bk_biz_id,
            "result_table_prefix": self.result_table_prefix,
            "default_result_table_id": self.default_result_table_id,
        }


def repair_plugin_strategy_result_table_id(
    bk_biz_id: int | Iterable[int] | None = None,
    strategy_ids: int | Iterable[int] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Find and repair strategy query configs that still use legacy plugin table names.

    Script / Exporter / Pushgateway / DataDog / JMX plugins use ``<plugin_type>_<plugin_id>.<table_name>``
    as result table IDs. After the migration, these plugins use single-metric
    split tables, so strategies must point to ``<plugin_type>_<plugin_id>.__default__``.

    Args:
        bk_biz_id: Optional business ID or business ID list used to limit strategies.
            Plugin definitions are still listed globally so global plugins referenced by
            the target business are not missed.
        strategy_ids: Optional strategy ID or strategy ID list used to limit query configs.
            When both ``bk_biz_id`` and ``strategy_ids`` are provided, only strategies
            matching both filters are scanned.
        dry_run: When true, only return planned changes. When false, update
            ``QueryConfigModel.config.result_table_id`` and ``QueryConfigModel.metric_id``.
    """
    bk_biz_ids = _normalize_ids(bk_biz_id)
    normalized_strategy_ids = _normalize_ids(strategy_ids)
    plugin_result_tables = _list_target_plugin_result_tables()
    plugin_result_table_map = {
        plugin.result_table_prefix: plugin for plugin in plugin_result_tables if plugin.result_table_prefix
    }

    change_records = _collect_change_records(
        plugin_result_table_map=plugin_result_table_map,
        bk_biz_ids=bk_biz_ids,
        strategy_ids=normalized_strategy_ids,
    )
    if not dry_run:
        _apply_change_records(change_records)

    return {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "strategy_ids": normalized_strategy_ids,
        "plugin_ids": [plugin.plugin_id for plugin in plugin_result_tables],
        "result_table_prefixes": [plugin.result_table_prefix for plugin in plugin_result_tables],
        "plugins": [plugin.to_dict() for plugin in plugin_result_tables],
        "changed_count": len(change_records),
        "applied_count": len([record for record in change_records if record.get("applied")]),
        "changes": deepcopy(change_records),
    }


def _normalize_ids(ids: int | str | Iterable[int] | None) -> list[int] | None:
    if ids is None:
        return None
    if isinstance(ids, int):
        return [ids]
    if isinstance(ids, str):
        ids = ids.strip()
        if not ids:
            return None
        return [int(ids)]
    return sorted({int(value) for value in ids})


def _list_target_plugin_result_tables() -> list[PluginResultTable]:
    plugins = (
        CollectorPluginMeta.objects.filter(plugin_type__in=TARGET_PLUGIN_TYPES)
        .only("plugin_id", "plugin_type", "bk_biz_id")
        .order_by("plugin_type", "plugin_id")
    )
    result_tables: list[PluginResultTable] = []
    seen_prefixes: set[str] = set()

    for plugin in plugins:
        default_result_table_id = PluginVersionHistory.get_result_table_id(plugin, DEFAULT_TABLE_NAME).lower()
        result_table_prefix = default_result_table_id.rsplit(".", 1)[0]
        if result_table_prefix in seen_prefixes:
            continue
        seen_prefixes.add(result_table_prefix)
        result_tables.append(
            PluginResultTable(
                plugin_id=plugin.plugin_id,
                plugin_type=plugin.plugin_type,
                bk_biz_id=plugin.bk_biz_id,
                result_table_prefix=result_table_prefix,
                default_result_table_id=default_result_table_id,
            )
        )

    return result_tables


def _collect_change_records(
    plugin_result_table_map: dict[str, PluginResultTable],
    bk_biz_ids: list[int] | None,
    strategy_ids: list[int] | None,
) -> list[dict[str, Any]]:
    if not plugin_result_table_map:
        return []

    strategy_queryset = StrategyModel.objects.all()
    if bk_biz_ids is not None:
        strategy_queryset = strategy_queryset.filter(bk_biz_id__in=bk_biz_ids)
    if strategy_ids is not None:
        strategy_queryset = strategy_queryset.filter(id__in=strategy_ids)

    query_configs = (
        QueryConfigModel.objects.filter(strategy_id__in=strategy_queryset.values("id"))
        .only(
            "id",
            "strategy_id",
            "item_id",
            "alias",
            "metric_id",
            "data_source_label",
            "data_type_label",
            "config",
        )
        .order_by("strategy_id", "id")
    )

    change_records: list[dict[str, Any]] = []
    for query_config in query_configs.iterator(chunk_size=1000):
        config = query_config.config or {}
        old_result_table_id = config.get("result_table_id")
        if not old_result_table_id:
            continue

        plugin_result_table = _match_plugin_result_table(old_result_table_id, plugin_result_table_map)
        if plugin_result_table is None:
            continue

        new_result_table_id = plugin_result_table.default_result_table_id
        if old_result_table_id == new_result_table_id:
            continue

        change_records.append(
            _build_change_record(
                query_config=query_config,
                plugin_result_table=plugin_result_table,
                old_result_table_id=old_result_table_id,
                new_result_table_id=new_result_table_id,
            )
        )

    _fill_strategy_info(change_records)
    return change_records


def _match_plugin_result_table(
    result_table_id: str,
    plugin_result_table_map: dict[str, PluginResultTable],
) -> PluginResultTable | None:
    result_table_id = str(result_table_id).strip()
    result_table_prefix, separator, table_name = result_table_id.partition(".")
    if not separator or table_name == DEFAULT_TABLE_NAME:
        return None
    return plugin_result_table_map.get(result_table_prefix.lower())


def _build_change_record(
    query_config: QueryConfigModel,
    plugin_result_table: PluginResultTable,
    old_result_table_id: str,
    new_result_table_id: str,
) -> dict[str, Any]:
    new_metric_id = _replace_metric_result_table_id(
        metric_id=query_config.metric_id,
        old_result_table_id=old_result_table_id,
        new_result_table_id=new_result_table_id,
    )
    return {
        "action": "update",
        "model": "bkmonitor.QueryConfigModel",
        "table": QueryConfigModel._meta.db_table,
        "query_config_id": query_config.pk,
        "strategy_id": query_config.strategy_id,
        "item_id": query_config.item_id,
        "alias": query_config.alias,
        "data_source_label": query_config.data_source_label,
        "data_type_label": query_config.data_type_label,
        "plugin_id": plugin_result_table.plugin_id,
        "plugin_type": plugin_result_table.plugin_type,
        "plugin_bk_biz_id": plugin_result_table.bk_biz_id,
        "result_table_prefix": plugin_result_table.result_table_prefix,
        "old_result_table_id": old_result_table_id,
        "new_result_table_id": new_result_table_id,
        "old_metric_id": query_config.metric_id,
        "new_metric_id": new_metric_id,
        "applied": False,
    }


def _replace_metric_result_table_id(metric_id: str, old_result_table_id: str, new_result_table_id: str) -> str:
    if not metric_id:
        return metric_id

    old_token = f".{old_result_table_id}."
    if old_token not in metric_id:
        return metric_id
    return metric_id.replace(old_token, f".{new_result_table_id}.", 1)


def _fill_strategy_info(change_records: list[dict[str, Any]]) -> None:
    strategy_ids = {record["strategy_id"] for record in change_records}
    if not strategy_ids:
        return

    strategies = {
        strategy.pk: strategy
        for strategy in StrategyModel.objects.filter(id__in=strategy_ids).only("id", "name", "bk_biz_id")
    }
    for record in change_records:
        strategy = strategies.get(record["strategy_id"])
        if strategy is None:
            continue
        record["strategy_name"] = strategy.name
        record["bk_biz_id"] = strategy.bk_biz_id


def _apply_change_records(change_records: list[dict[str, Any]]) -> None:
    if not change_records:
        return

    record_map = {record["query_config_id"]: record for record in change_records}
    update_query_configs: list[QueryConfigModel] = []

    with transaction.atomic():
        query_configs = QueryConfigModel.objects.select_for_update().filter(id__in=list(record_map))
        for query_config in query_configs:
            record = record_map[query_config.pk]
            config = query_config.config or {}
            if config.get("result_table_id") != record["old_result_table_id"]:
                record["stale"] = True
                record["current_result_table_id"] = config.get("result_table_id")
                continue

            new_config = deepcopy(config)
            new_config["result_table_id"] = record["new_result_table_id"]
            query_config.config = new_config
            query_config.metric_id = record["new_metric_id"]
            update_query_configs.append(query_config)
            record["applied"] = True

        if update_query_configs:
            QueryConfigModel.objects.bulk_update(update_query_configs, fields=["config", "metric_id"], batch_size=500)
