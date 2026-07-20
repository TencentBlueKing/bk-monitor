from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import (
    _get_log_access_type,
    _get_primary_index_set,
    _get_result_table_storage,
    _serialize_result_table_storage,
)
from apps.log_databus.handlers.etl.transfer import TransferEtlHandler
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import CollectorConfig


TARGET_FIELDS = (
    "storage_cluster_id",
    "retention",
    "allocation_min_days",
    "storage_shards_nums",
    "storage_replies",
)
HOT_WARM_RELATED_FIELDS = {"storage_cluster_id", "retention", "allocation_min_days"}

MIN_VALUES = {
    "storage_cluster_id": 1,
    "retention": 1,
    "allocation_min_days": 1,
    "storage_shards_nums": 1,
    "storage_replies": 0,
}

STATUS_NAMES = {
    "changeable": "可变更",
    "unchanged": "无变化",
    "blocked": "已阻断",
    "success": "执行成功",
    "failed": "执行失败",
}


def preview_collector_storage(params):
    params = params or {}
    collector_config_ids = _parse_collector_config_ids(params)
    target = _parse_target(params)
    collectors = _get_collectors(collector_config_ids)
    cluster_hot_warm_cache = {}
    items = [_build_preview_item(collector, target, cluster_hot_warm_cache) for collector in collectors]
    return {"summary": _summarize_items(items), "items": items}


def apply_collector_storage(params):
    params = params or {}
    collector_config_ids = _parse_collector_config_ids(params)
    target = _parse_target(params)
    expected_before = params.get("expected_before") or {}
    collectors = _get_collectors(collector_config_ids)
    cluster_hot_warm_cache = {}

    items = []
    for collector in collectors:
        item = _build_preview_item(collector, target, cluster_hot_warm_cache)
        expected = expected_before.get(str(collector.collector_config_id)) or expected_before.get(
            collector.collector_config_id
        )
        mismatch_fields = _get_expected_before_mismatch(item["before"], expected)
        if mismatch_fields:
            item.update(
                {
                    "status": "blocked",
                    "status_name": STATUS_NAMES["blocked"],
                    "execution_message": "expected_before mismatch: {}".format(", ".join(mismatch_fields)),
                }
            )
            items.append(item)
            continue
        if item["status"] != "changeable":
            item["execution_message"] = item["execution_message"] or "no change applied"
            items.append(item)
            continue
        try:
            _apply_one_collector(collector, target)
        except Exception as err:  # noqa: BLE001
            item.update({"status": "failed", "status_name": STATUS_NAMES["failed"], "execution_message": str(err)})
        else:
            item.update(
                {
                    "status": "success",
                    "status_name": STATUS_NAMES["success"],
                    "execution_message": "storage config updated",
                }
            )
        items.append(item)

    return {"summary": _summarize_items(items), "items": items}


def _parse_collector_config_ids(params):
    params = params or {}
    collector_config_ids = params.get("collector_config_ids") or []
    if not collector_config_ids:
        raise ValidationError("collector_config_ids is required")
    return [int(collector_config_id) for collector_config_id in collector_config_ids]


def _parse_target(params):
    target = (params or {}).get("target") or {}
    if not isinstance(target, dict):
        raise ValidationError("target must be an object")
    unsupported_fields = sorted(set(target) - set(TARGET_FIELDS))
    if unsupported_fields:
        raise ValidationError("unsupported target fields: {}".format(", ".join(unsupported_fields)))
    parsed = {}
    for field in TARGET_FIELDS:
        if target.get(field) in (None, ""):
            continue
        value = int(target[field])
        min_value = MIN_VALUES.get(field)
        if min_value is not None and value < min_value:
            raise ValidationError(f"{field} must be greater than or equal to {min_value}")
        parsed[field] = value
    if not parsed:
        raise ValidationError("target must include at least one storage field")
    return parsed


def _get_collectors(collector_config_ids):
    collectors = list(CollectorConfig.objects.filter(collector_config_id__in=collector_config_ids))
    collector_map = {collector.collector_config_id: collector for collector in collectors}
    missing_ids = [
        collector_config_id for collector_config_id in collector_config_ids if collector_config_id not in collector_map
    ]
    if missing_ids:
        raise ValidationError("collector_config_id does not exist: {}".format(", ".join(map(str, missing_ids))))
    return [collector_map[collector_config_id] for collector_config_id in collector_config_ids]


def _build_preview_item(collector, target, cluster_hot_warm_cache):
    primary_index_set, primary_index_data = _get_primary_index_set(collector.collector_config_id)
    table_id = collector.table_id or (primary_index_data.result_table_id if primary_index_data else None)
    storage, storage_warning = _get_result_table_storage(
        table_id=table_id,
        storage_cluster_type=collector.storage_cluster_type,
    )
    before = _merge_storage_snapshot(_serialize_result_table_storage(storage), collector)
    after = dict(before)
    after.update(target)
    warnings = []
    if storage_warning:
        warnings.append(storage_warning)
    if not collector.is_active:
        warnings.append({"code": "collector_not_active", "message": "collector is not active"})
    if primary_index_set is None:
        warnings.append({"code": "primary_index_set_not_found", "message": "primary index set not found"})

    storage_cluster_id = after.get("storage_cluster_id")
    if storage_cluster_id and HOT_WARM_RELATED_FIELDS.intersection(target):
        try:
            hot_warm_enabled = _get_cluster_hot_warm_enabled(storage_cluster_id, cluster_hot_warm_cache)
        except Exception as err:  # noqa: BLE001
            warnings.append({"code": "storage_cluster_query_failed", "message": str(err)})
        else:
            _apply_hot_warm_rules(before, after, target, hot_warm_enabled, warnings)

    diff = _build_diff(before, after, target)

    status = "blocked" if warnings else "unchanged"
    if status != "blocked" and diff:
        status = "changeable"

    return {
        "collector_config_id": collector.collector_config_id,
        "collector_config_name": collector.collector_config_name,
        "bk_biz_id": int(collector.bk_biz_id),
        "bk_data_id": collector.bk_data_id,
        "table_id": table_id,
        "index_set_id": primary_index_set.index_set_id if primary_index_set else None,
        "index_set_name": primary_index_set.index_set_name if primary_index_set else None,
        "log_access_type": _get_log_access_type(collector, ""),
        "collector_scenario_id": collector.collector_scenario_id,
        "is_active": collector.is_active,
        "enable_v4": collector.enable_v4,
        "status": status,
        "status_name": STATUS_NAMES[status],
        "before": before,
        "after": after,
        "diff": diff,
        "warnings": warnings,
        "execution_message": None if status == "changeable" else STATUS_NAMES[status],
    }


def _merge_storage_snapshot(storage, collector):
    return {
        "storage_cluster_id": storage.get("storage_cluster_id"),
        "retention": storage.get("retention"),
        "allocation_min_days": storage.get("allocation_min_days"),
        "storage_shards_nums": _first_not_none(storage.get("storage_shards_nums"), collector.storage_shards_nums),
        "storage_replies": _first_not_none(storage.get("storage_replies"), collector.storage_replies),
        "storage_shards_size": _first_not_none(storage.get("storage_shards_size"), collector.storage_shards_size),
    }


def _build_diff(before, after, target):
    diff = []
    changed_fields = set(target)
    if before.get("allocation_min_days") != after.get("allocation_min_days"):
        changed_fields.add("allocation_min_days")
    for field in TARGET_FIELDS:
        if field not in changed_fields:
            continue
        if before.get(field) == after.get(field):
            continue
        diff.append({"field": field, "label": field, "from": before.get(field), "to": after.get(field)})
    return diff


def _get_expected_before_mismatch(before, expected):
    if not expected:
        return []
    return [field for field, expected_value in expected.items() if before.get(field) != expected_value]


def _apply_one_collector(collector, target):
    TransferEtlHandler(collector_config_id=collector.collector_config_id).patch_update(
        storage_cluster_id=target.get("storage_cluster_id"),
        retention=target.get("retention"),
        allocation_min_days=target.get("allocation_min_days"),
        storage_replies=target.get("storage_replies"),
        es_shards=target.get("storage_shards_nums"),
    )


def _get_cluster_hot_warm_enabled(storage_cluster_id, cache):
    storage_cluster_id = int(storage_cluster_id)
    if storage_cluster_id not in cache:
        cluster_info = StorageHandler(storage_cluster_id).get_cluster_info_by_id()
        cluster_config = cluster_info.get("cluster_config") or {}
        custom_option = cluster_config.get("custom_option") or {}
        hot_warm_config = custom_option.get("hot_warm_config") or {}
        cache[storage_cluster_id] = bool(hot_warm_config.get("is_enabled", False))
    return cache[storage_cluster_id]


def _apply_hot_warm_rules(before, after, target, hot_warm_enabled, warnings):
    cluster_changed = "storage_cluster_id" in target and before.get("storage_cluster_id") != after.get(
        "storage_cluster_id"
    )
    if not hot_warm_enabled:
        if "allocation_min_days" in target:
            warnings.append(
                {
                    "code": "hot_data_days_not_supported",
                    "message": "allocation_min_days is only supported by hot-warm storage clusters",
                }
            )
        elif cluster_changed and before.get("allocation_min_days"):
            after["allocation_min_days"] = 0
        return

    allocation_min_days = after.get("allocation_min_days")
    retention = after.get("retention")
    if cluster_changed and "allocation_min_days" not in target:
        warnings.append(
            {
                "code": "hot_data_days_required",
                "message": "allocation_min_days is required when switching to a hot-warm storage cluster",
            }
        )
        return
    if not allocation_min_days:
        warnings.append(
            {
                "code": "hot_data_days_required",
                "message": "allocation_min_days is required for a hot-warm storage cluster",
            }
        )
        return
    if not retention:
        warnings.append(
            {
                "code": "retention_required_for_hot_data",
                "message": "retention is required when allocation_min_days is configured",
            }
        )
        return
    if allocation_min_days >= retention:
        warnings.append(
            {
                "code": "invalid_hot_data_days",
                "message": "allocation_min_days must be greater than or equal to 1 and less than retention",
            }
        )


def _summarize_items(items):
    summary = {
        "total": len(items),
        "changeable": 0,
        "unchanged": 0,
        "blocked": 0,
        "needs_review": 0,
        "success": 0,
        "failed": 0,
    }
    for item in items:
        if item["status"] in summary:
            summary[item["status"]] += 1
    return summary


def _first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None
