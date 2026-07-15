from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import serialize_collectors
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import IndexSetDataType
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import parse_space_uid, space_uid_to_bk_biz_id


def list_index_sets(params):
    params = params or {}
    page = _to_positive_int(params.get("page"), default=1)
    page_size = _to_positive_int(params.get("page_size"), default=20)
    qs = LogIndexSet.objects.all()

    exact_filters = {
        "space_uid": "space_uid",
        "index_set_id": "index_set_id",
        "collector_config_id": "collector_config_id",
        "scenario_id": "scenario_id",
        "is_active": "is_active",
        "is_group": "is_group",
    }
    for param_key, model_field in exact_filters.items():
        if params.get(param_key) not in (None, ""):
            qs = qs.filter(**{model_field: params[param_key]})
    if params.get("index_set_name"):
        qs = qs.filter(index_set_name__icontains=params["index_set_name"])
    if params.get("result_table_id"):
        qs = qs.filter(index_set_id__in=_get_index_set_ids_by_result_table_id(params["result_table_id"]))

    ordering = params.get("ordering") or params.get("order_by") or "-updated_at"
    qs = _apply_ordering(qs, ordering)
    total = qs.count()
    start = (page - 1) * page_size
    index_sets = list(qs[start : start + page_size])
    return {"items": _serialize_index_sets(index_sets), "page": page, "page_size": page_size, "total": total}


def get_index_set_detail(params):
    params = params or {}
    index_set_id = params.get("index_set_id")
    if not index_set_id:
        raise ValidationError("index_set_id is required")
    try:
        index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
    except LogIndexSet.DoesNotExist:
        raise ValidationError(f"index_set_id does not exist: {index_set_id}")

    visible_indexes = _get_visible_indexes(index_set)
    indexes = [_serialize_index_set_data(item, index_set.index_set_id) for item in visible_indexes]
    collectors = serialize_collectors(_get_collectors(index_set))
    warnings = [
        {"code": "storage_cluster_not_found", "message": "{} has no storage_cluster_id".format(item["result_table_id"])}
        for item in indexes
        if item["scenario_id"] == Scenario.LOG and item["storage_cluster_id"] is None
    ]

    return {
        "index_set": _serialize_index_set(index_set, visible_indexes),
        "indexes": indexes,
        "collectors": collectors,
        "raw": {
            "source_id": index_set.source_id,
            "source_app_code": index_set.source_app_code,
            "target_fields": index_set.target_fields or [],
            "sort_fields": index_set.sort_fields or [],
            "query_alias_settings": index_set.query_alias_settings,
            "fields_snapshot": index_set.fields_snapshot,
        },
        "warnings": warnings,
    }


def _serialize_index_sets(index_sets):
    visible_indexes_map = _get_visible_indexes_map(index_sets)
    bk_biz_id_map = _build_bk_biz_id_map(index_sets)
    return [
        _serialize_index_set(
            index_set,
            visible_indexes_map.get(index_set.index_set_id, []),
            bk_biz_id=bk_biz_id_map.get(index_set.space_uid, 0),
        )
        for index_set in index_sets
    ]


def _serialize_index_set(index_set, indexes=None, bk_biz_id=None):
    if indexes is None:
        indexes = _get_visible_indexes(index_set)
    first_index = indexes[0] if indexes else None
    return {
        "index_set_id": index_set.index_set_id,
        "index_set_name": index_set.index_set_name,
        "space_uid": index_set.space_uid,
        "bk_biz_id": _get_bk_biz_id(index_set) if bk_biz_id is None else bk_biz_id,
        "category_id": index_set.category_id,
        "collector_config_id": index_set.collector_config_id,
        "scenario_id": index_set.scenario_id,
        "scenario_name": str(dict(Scenario.CHOICES).get(index_set.scenario_id, "")),
        "storage_cluster_id": index_set.storage_cluster_id,
        "time_field": index_set.time_field or (first_index.time_field if first_index else None),
        "time_field_type": index_set.time_field_type or (first_index.time_field_type if first_index else None),
        "time_field_unit": index_set.time_field_unit or (first_index.time_field_unit if first_index else None),
        "is_active": index_set.is_active,
        "is_editable": index_set.is_editable,
        "is_group": index_set.is_group,
        "support_doris": index_set.support_doris,
        "tag_ids": _normalize_list(index_set.tag_ids),
        "created_at": index_set.created_at.isoformat() if index_set.created_at else None,
        "created_by": index_set.created_by,
        "updated_at": index_set.updated_at.isoformat() if index_set.updated_at else None,
        "result_table_ids": [item.result_table_id for item in indexes],
        "index_count": len(indexes),
    }


def _serialize_index_set_data(index_data, display_index_set_id):
    return {
        "index_id": index_data.index_id,
        "index_set_id": display_index_set_id,
        "bk_biz_id": index_data.bk_biz_id,
        "result_table_id": index_data.result_table_id,
        "result_table_name": index_data.result_table_name,
        "scenario_id": index_data.scenario_id,
        "storage_cluster_id": index_data.storage_cluster_id,
        "time_field": index_data.time_field,
        "time_field_type": index_data.time_field_type,
        "time_field_unit": index_data.time_field_unit,
        "apply_status": index_data.apply_status,
        "apply_status_name": str(index_data.get_apply_status_display()),
        "type": index_data.type,
    }


def _get_visible_indexes(index_set):
    if index_set.is_group:
        child_ids = index_set.get_child_index_set_ids()
        return list(
            LogIndexSetData.objects.filter(
                index_set_id__in=child_ids, type=IndexSetDataType.RESULT_TABLE.value
            ).order_by("index_set_id", "index_id")
        )
    return list(
        LogIndexSetData.objects.filter(
            index_set_id=index_set.index_set_id, type=IndexSetDataType.RESULT_TABLE.value
        ).order_by("index_id")
    )


def _get_visible_indexes_map(index_sets):
    visible_indexes_map = {index_set.index_set_id: [] for index_set in index_sets}
    if not index_sets:
        return visible_indexes_map

    normal_index_set_ids = [index_set.index_set_id for index_set in index_sets if not index_set.is_group]
    group_index_set_ids = [index_set.index_set_id for index_set in index_sets if index_set.is_group]

    if normal_index_set_ids:
        normal_indexes = LogIndexSetData.objects.filter(
            index_set_id__in=normal_index_set_ids,
            type=IndexSetDataType.RESULT_TABLE.value,
        ).order_by("index_set_id", "index_id")
        for index_data in normal_indexes:
            visible_indexes_map[index_data.index_set_id].append(index_data)

    group_child_ids_map = _get_group_child_ids_map(group_index_set_ids)
    child_index_set_ids = sorted({child_id for child_ids in group_child_ids_map.values() for child_id in child_ids})
    if child_index_set_ids:
        child_index_data_map = {child_id: [] for child_id in child_index_set_ids}
        child_indexes = LogIndexSetData.objects.filter(
            index_set_id__in=child_index_set_ids,
            type=IndexSetDataType.RESULT_TABLE.value,
        ).order_by("index_set_id", "index_id")
        for index_data in child_indexes:
            child_index_data_map[index_data.index_set_id].append(index_data)
        for group_index_set_id, child_ids in group_child_ids_map.items():
            for child_id in sorted(child_ids):
                visible_indexes_map[group_index_set_id].extend(child_index_data_map.get(child_id, []))

    return visible_indexes_map


def _get_index_set_ids_by_result_table_id(result_table_id):
    matched_child_ids = set(
        LogIndexSetData.objects.filter(
            result_table_id__icontains=result_table_id,
            type=IndexSetDataType.RESULT_TABLE.value,
        ).values_list("index_set_id", flat=True)
    )
    if not matched_child_ids:
        return []

    matched_group_ids = set(
        LogIndexSetData.objects.filter(
            result_table_id__in=[str(index_set_id) for index_set_id in matched_child_ids],
            type=IndexSetDataType.INDEX_SET.value,
        ).values_list("index_set_id", flat=True)
    )
    return list(matched_child_ids | matched_group_ids)


def _get_group_child_ids_map(group_index_set_ids):
    group_child_ids_map = {group_index_set_id: [] for group_index_set_id in group_index_set_ids}
    if not group_index_set_ids:
        return group_child_ids_map

    group_links = LogIndexSetData.objects.filter(
        index_set_id__in=group_index_set_ids,
        type=IndexSetDataType.INDEX_SET.value,
    ).order_by("index_set_id", "index_id")
    for group_link in group_links:
        group_child_ids_map[group_link.index_set_id].append(int(group_link.result_table_id))
    return group_child_ids_map


def _get_collectors(index_set):
    member_index_sets = _get_member_index_sets(index_set)
    collector_config_ids = [
        member.collector_config_id for member in member_index_sets if member.collector_config_id not in (None, "")
    ]
    if not collector_config_ids:
        return []
    collector_map = {
        collector.collector_config_id: collector
        for collector in CollectorConfig.objects.filter(collector_config_id__in=collector_config_ids)
    }
    return [
        collector_map[collector_config_id]
        for collector_config_id in collector_config_ids
        if collector_config_id in collector_map
    ]


def _get_member_index_sets(index_set):
    if not index_set.is_group:
        return [index_set]
    child_ids = index_set.get_child_index_set_ids()
    child_map = {item.index_set_id: item for item in LogIndexSet.objects.filter(index_set_id__in=child_ids)}
    return [child_map[child_id] for child_id in child_ids if child_id in child_map]


def _get_bk_biz_id(index_set):
    return space_uid_to_bk_biz_id(index_set.space_uid)


def _build_bk_biz_id_map(index_sets):
    """批量构建 space_uid -> bk_biz_id 映射，避免逐行调用 SpaceApi.get_space_detail 造成 N+1。

    与 space_uid_to_bk_biz_id 语义保持一致：BKCC 空间直接解析为业务 ID，
    非 BKCC 空间通过一次性的 SpaceApi.batch_get_space_detail 解析为负的空间自增 ID，
    解析失败或空间不存在时返回 0。
    """
    bk_biz_id_map = {}
    non_bkcc_space_uids = set()
    for index_set in index_sets:
        space_uid = index_set.space_uid
        if not space_uid or space_uid in bk_biz_id_map or space_uid in non_bkcc_space_uids:
            continue
        try:
            space_type, space_id = parse_space_uid(space_uid)
        except ValueError:
            bk_biz_id_map[space_uid] = 0
            continue
        if space_type == SpaceTypeEnum.BKCC.value:
            bk_biz_id_map[space_uid] = int(space_id)
        else:
            non_bkcc_space_uids.add(space_uid)

    if non_bkcc_space_uids:
        space_detail_map = SpaceApi.batch_get_space_detail(non_bkcc_space_uids)
        for space_uid in non_bkcc_space_uids:
            space = space_detail_map.get(space_uid)
            bk_biz_id_map[space_uid] = -int(space.id) if space else 0

    return bk_biz_id_map


def _apply_ordering(qs, ordering):
    ordering = ordering if ordering in _allowed_ordering() else "-updated_at"
    return qs.order_by(ordering)


def _allowed_ordering():
    fields = ["index_set_id", "index_set_name", "updated_at", "space_uid"]
    return set(fields + [f"-{field}" for field in fields])


def _to_positive_int(value, default):
    if value in (None, ""):
        return default
    value = int(value)
    if value < 1:
        raise ValidationError("pagination value must be positive")
    return value


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [item for item in value.split(",") if item]
    return list(value)
