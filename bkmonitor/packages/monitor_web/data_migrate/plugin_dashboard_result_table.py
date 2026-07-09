from __future__ import annotations

import json
from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from django.db import transaction

from bk_dataview.models import Dashboard, Org
from monitor_web.data_migrate.plugin_strategy_result_table import (
    _list_target_plugin_result_tables,
    _match_plugin_result_table,
    _normalize_ids,
)


def repair_plugin_dashboard_result_table_id(
    bk_biz_id: int | Iterable[int] | None = None,
    dashboard_uids: str | Iterable[str] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Find and repair dashboard panel query configs that still use legacy plugin table names.

    Plugin dashboards keep query configs inside ``bk_dataview.Dashboard.data``. This helper
    rewrites only ``targets[*].query_configs[*].result_table_id`` and leaves the rest of the
    panel config untouched.
    """
    bk_biz_ids = _normalize_ids(bk_biz_id)
    normalized_dashboard_uids = _normalize_dashboard_uids(dashboard_uids)
    plugin_result_tables = _list_target_plugin_result_tables()
    plugin_result_table_map = {
        plugin.result_table_prefix: plugin for plugin in plugin_result_tables if plugin.result_table_prefix
    }

    change_records, invalid_dashboard_records = _collect_change_records(
        plugin_result_table_map=plugin_result_table_map,
        bk_biz_ids=bk_biz_ids,
        dashboard_uids=normalized_dashboard_uids,
    )
    if not dry_run:
        _apply_change_records(change_records)

    return {
        "dry_run": dry_run,
        "bk_biz_ids": bk_biz_ids,
        "dashboard_uids": normalized_dashboard_uids,
        "plugin_ids": [plugin.plugin_id for plugin in plugin_result_tables],
        "result_table_prefixes": [plugin.result_table_prefix for plugin in plugin_result_tables],
        "plugins": [plugin.to_dict() for plugin in plugin_result_tables],
        "changed_count": len(change_records),
        "applied_count": len([record for record in change_records if record.get("applied")]),
        "stale_count": len([record for record in change_records if record.get("stale")]),
        "invalid_json_count": len(invalid_dashboard_records),
        "invalid_json": deepcopy(invalid_dashboard_records),
        "changes": deepcopy(change_records),
    }


def _normalize_dashboard_uids(uids: str | Iterable[str] | None) -> list[str] | None:
    if uids is None:
        return None
    if isinstance(uids, str):
        uid = uids.strip()
        return [uid] if uid else None
    return sorted({str(uid).strip() for uid in uids if str(uid).strip()})


def _collect_change_records(
    plugin_result_table_map: dict[str, Any],
    bk_biz_ids: list[int] | None,
    dashboard_uids: list[str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not plugin_result_table_map:
        return [], []

    dashboards = _build_dashboard_queryset(bk_biz_ids=bk_biz_ids, dashboard_uids=dashboard_uids)
    change_records: list[dict[str, Any]] = []
    invalid_dashboard_records: list[dict[str, Any]] = []

    for dashboard in dashboards.iterator(chunk_size=200):
        try:
            dashboard_data = json.loads(dashboard.data or "{}")
        except (TypeError, ValueError) as error:
            invalid_dashboard_records.append(_build_invalid_dashboard_record(dashboard, error))
            continue

        for panel, panel_path in _iter_panels(dashboard_data.get("panels", [])):
            for target_index, target in enumerate(panel.get("targets") or []):
                if not isinstance(target, dict):
                    continue
                for query_config_index, query_config in enumerate(target.get("query_configs") or []):
                    if not isinstance(query_config, dict):
                        continue
                    old_result_table_id = query_config.get("result_table_id")
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
                            dashboard=dashboard,
                            panel=panel,
                            panel_path=panel_path,
                            target=target,
                            target_index=target_index,
                            query_config=query_config,
                            query_config_index=query_config_index,
                            plugin_result_table=plugin_result_table,
                            old_result_table_id=old_result_table_id,
                            new_result_table_id=new_result_table_id,
                        )
                    )

    return change_records, invalid_dashboard_records


def _build_dashboard_queryset(bk_biz_ids: list[int] | None, dashboard_uids: list[str] | None):
    dashboards = Dashboard.objects.filter(is_folder=0).only("id", "uid", "title", "org_id", "data")
    if bk_biz_ids is not None:
        org_ids = Org.objects.filter(name__in=[str(bk_biz_id) for bk_biz_id in bk_biz_ids]).values_list("id", flat=True)
        dashboards = dashboards.filter(org_id__in=org_ids)
    if dashboard_uids is not None:
        dashboards = dashboards.filter(uid__in=dashboard_uids)
    return dashboards.order_by("org_id", "id")


def _iter_panels(panels: Any, panel_path: tuple[int, ...] = ()):
    if not isinstance(panels, list):
        return
    for panel_index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        current_path = (*panel_path, panel_index)
        yield panel, current_path
        yield from _iter_panels(panel.get("panels"), current_path)


def _build_invalid_dashboard_record(dashboard: Dashboard, error: Exception) -> dict[str, Any]:
    return {
        "model": "bk_dataview.Dashboard",
        "table": Dashboard._meta.db_table,
        "dashboard_id": dashboard.pk,
        "dashboard_uid": dashboard.uid,
        "dashboard_title": dashboard.title,
        "org_id": dashboard.org_id,
        "invalid_json": True,
        "error": str(error),
    }


def _build_change_record(
    dashboard: Dashboard,
    panel: dict[str, Any],
    panel_path: tuple[int, ...],
    target: dict[str, Any],
    target_index: int,
    query_config: dict[str, Any],
    query_config_index: int,
    plugin_result_table: Any,
    old_result_table_id: str,
    new_result_table_id: str,
) -> dict[str, Any]:
    return {
        "action": "update",
        "model": "bk_dataview.Dashboard",
        "table": Dashboard._meta.db_table,
        "dashboard_id": dashboard.pk,
        "dashboard_uid": dashboard.uid,
        "dashboard_title": dashboard.title,
        "org_id": dashboard.org_id,
        "panel_id": panel.get("id"),
        "panel_title": panel.get("title"),
        "panel_type": panel.get("type"),
        "panel_path": list(panel_path),
        "target_index": target_index,
        "target_ref_id": target.get("refId"),
        "query_config_index": query_config_index,
        "query_config_ref_id": query_config.get("refId"),
        "query_config_alias": query_config.get("alias"),
        "metric_field": query_config.get("metric_field"),
        "plugin_id": plugin_result_table.plugin_id,
        "plugin_type": plugin_result_table.plugin_type,
        "plugin_bk_biz_id": plugin_result_table.bk_biz_id,
        "result_table_prefix": plugin_result_table.result_table_prefix,
        "old_result_table_id": old_result_table_id,
        "new_result_table_id": new_result_table_id,
        "applied": False,
    }


def _apply_change_records(change_records: list[dict[str, Any]]) -> None:
    if not change_records:
        return

    records_by_dashboard_id: dict[int, list[dict[str, Any]]] = {}
    for record in change_records:
        records_by_dashboard_id.setdefault(record["dashboard_id"], []).append(record)

    update_dashboards: list[Dashboard] = []
    with transaction.atomic():
        dashboards = (
            Dashboard.objects.select_for_update().filter(id__in=list(records_by_dashboard_id)).only("id", "data")
        )
        for dashboard in dashboards:
            records = records_by_dashboard_id[dashboard.pk]
            try:
                dashboard_data = json.loads(dashboard.data or "{}")
            except (TypeError, ValueError) as error:
                for record in records:
                    record["stale"] = True
                    record["invalid_json"] = True
                    record["current_error"] = str(error)
                continue

            changed = False
            for record in records:
                query_config = _get_query_config_by_record(dashboard_data, record)
                if query_config is None:
                    record["stale"] = True
                    record["current_result_table_id"] = None
                    continue
                if query_config.get("result_table_id") != record["old_result_table_id"]:
                    record["stale"] = True
                    record["current_result_table_id"] = query_config.get("result_table_id")
                    continue

                query_config["result_table_id"] = record["new_result_table_id"]
                record["applied"] = True
                changed = True

            if changed:
                dashboard.data = json.dumps(dashboard_data, ensure_ascii=False)
                update_dashboards.append(dashboard)

        if update_dashboards:
            Dashboard.objects.bulk_update(update_dashboards, fields=["data"], batch_size=200)


def _get_query_config_by_record(dashboard_data: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
    panel = _get_panel_by_path(dashboard_data.get("panels"), record["panel_path"])
    if not isinstance(panel, dict):
        return None

    targets = panel.get("targets")
    if not isinstance(targets, list) or record["target_index"] >= len(targets):
        return None
    target = targets[record["target_index"]]
    if not isinstance(target, dict):
        return None

    query_configs = target.get("query_configs")
    if not isinstance(query_configs, list) or record["query_config_index"] >= len(query_configs):
        return None
    query_config = query_configs[record["query_config_index"]]
    return query_config if isinstance(query_config, dict) else None


def _get_panel_by_path(panels: Any, panel_path: list[int]) -> dict[str, Any] | None:
    current_panels = panels
    current_panel = None
    for panel_index in panel_path:
        if not isinstance(current_panels, list) or panel_index >= len(current_panels):
            return None
        current_panel = current_panels[panel_index]
        if not isinstance(current_panel, dict):
            return None
        current_panels = current_panel.get("panels")
    return current_panel
