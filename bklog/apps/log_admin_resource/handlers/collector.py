from apps.api import TransferApi
from apps.exceptions import ValidationError
from apps.log_databus.models import (
    BKDataClean,
    CollectorConfig,
    ContainerCollectorConfig,
    DataLinkConfig,
)
from apps.log_search.constants import CollectorScenarioEnum, IndexSetDataType, LogAccessTypeEnum
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario


SENSITIVE_KEYWORDS = ("password", "secret", "token")


def list_collectors(params):
    params = params or {}
    page = _to_positive_int(params.get("page"), default=1)
    page_size = _to_positive_int(params.get("page_size"), default=20)
    qs = CollectorConfig.objects.all()

    exact_filters = {
        "collector_config_id": "collector_config_id",
        "bk_data_id": "bk_data_id",
        "data_link_id": "data_link_id",
        "index_set_id": "index_set_id",
        "subscription_id": "subscription_id",
        "collector_scenario_id": "collector_scenario_id",
        "target_object_type": "target_object_type",
        "etl_config": "etl_config",
        "bcs_cluster_id": "bcs_cluster_id",
        "is_active": "is_active",
        "enable_v4": "enable_v4",
        "bk_biz_id": "bk_biz_id",
    }
    for param_key, model_field in exact_filters.items():
        if params.get(param_key) not in (None, ""):
            qs = qs.filter(**{model_field: params[param_key]})
    if params.get("collector_config_name"):
        qs = qs.filter(collector_config_name__icontains=params["collector_config_name"])
    if params.get("table_id"):
        qs = qs.filter(table_id__icontains=params["table_id"])

    if params.get("storage_cluster_id") not in (None, ""):
        storage_cluster_id = int(params["storage_cluster_id"])
        qs = qs.filter(collector_config_id__in=_get_collector_config_ids_by_storage_cluster(qs, storage_cluster_id))
    if params.get("log_access_type") not in (None, ""):
        qs = qs.filter(
            collector_config_id__in=_get_collector_config_ids_by_log_access_type(qs, params["log_access_type"])
        )

    ordering = params.get("ordering") or params.get("order_by") or "-updated_at"
    qs = _apply_ordering(qs, ordering)

    total = qs.count()
    start = (page - 1) * page_size
    collectors = list(qs[start : start + page_size])
    return {"items": serialize_collectors(collectors), "page": page, "page_size": page_size, "total": total}


def get_collector_detail(params):
    params = params or {}
    collector_config_id = params.get("collector_config_id")
    if not collector_config_id:
        raise ValidationError("collector_config_id is required")
    try:
        collector = CollectorConfig.objects.get(collector_config_id=collector_config_id)
    except CollectorConfig.DoesNotExist:
        raise ValidationError(f"collector_config_id does not exist: {collector_config_id}")

    summary = serialize_collector(collector)
    primary_index_set, primary_index_data = _get_primary_index_set(collector.collector_config_id)
    data_link = _get_data_link(collector.data_link_id)
    bkdata_clean = _get_bkdata_clean(collector.collector_config_id)
    index_set_relations = _get_index_set_relations(primary_index_set, primary_index_data, bkdata_clean)
    raw_params = _get_raw_params(collector)
    result_table_storage, storage_warning = _get_result_table_storage(
        table_id=collector.table_id or (primary_index_data.result_table_id if primary_index_data else None),
        storage_cluster_type=collector.storage_cluster_type,
    )

    warnings = []
    if storage_warning:
        warnings.append(storage_warning)
    if collector.data_link_id and data_link is None:
        warnings.append({"code": "data_link_not_found", "message": "data_link_id not found"})
    if not collector.data_link_id:
        warnings.append({"code": "missing_data_link_id", "message": "collector has no data_link_id"})
    if primary_index_set is None:
        warnings.append({"code": "primary_index_set_not_found", "message": "primary index set not found"})
    elif collector.index_set_id and collector.index_set_id != primary_index_set.index_set_id:
        warnings.append(
            {
                "code": "collector_index_set_id_not_synced",
                "message": "CollectorConfig.index_set_id differs from LogIndexSet.collector_config_id",
            }
        )
    if summary["storage_cluster_id"] is None and primary_index_set and primary_index_set.scenario_id == Scenario.LOG:
        warnings.append({"code": "storage_cluster_not_found", "message": "primary index set has no storage_cluster_id"})

    return {
        "collector": summary,
        "chain": {
            "collector_config_id": collector.collector_config_id,
            "bk_data_id": collector.bk_data_id,
            "table_id": collector.table_id,
            "data_link_id": collector.data_link_id,
            "primary_index_set_id": primary_index_set.index_set_id if primary_index_set else None,
            "subscription_id": collector.subscription_id,
            "etl_config": collector.etl_config,
        },
        "storage": _serialize_result_table_storage(result_table_storage),
        "relations": {
            "data_link": _serialize_data_link(data_link),
            "index_sets": index_set_relations,
            "bkdata_clean": [_serialize_bkdata_clean(item) for item in bkdata_clean],
        },
        "raw": {
            "params": mask_sensitive(raw_params or {}),
            "target_nodes": collector.target_nodes or [],
            "task_id_list": [_to_int_or_original(task_id) for task_id in (collector.task_id_list or [])],
            "environment": collector.environment,
            "bcs_cluster_id": collector.bcs_cluster_id,
            "yaml_config_enabled": collector.yaml_config_enabled,
            "rule_id": collector.rule_id,
            "enable_v4": collector.enable_v4,
        },
        "warnings": warnings,
    }


def mask_sensitive(value):
    if isinstance(value, dict):
        return {key: "******" if _is_sensitive_key(key) else mask_sensitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


def serialize_collector(collector):
    return serialize_collectors([collector])[0]


def serialize_collectors(collectors):
    collectors = list(collectors)
    collector_config_ids = [collector.collector_config_id for collector in collectors]
    primary_index_set_map = _get_primary_index_set_map(collector_config_ids)
    primary_index_data_map = _get_primary_index_data_map(primary_index_set_map.values())
    container_config_map = _get_container_config_map(collector_config_ids)

    return [
        _serialize_collector_with_relations(
            collector=collector,
            primary_index_set=primary_index_set_map.get(collector.collector_config_id),
            primary_index_data=(
                primary_index_data_map.get(primary_index_set_map[collector.collector_config_id].index_set_id)
                if collector.collector_config_id in primary_index_set_map
                else None
            ),
            container_config=container_config_map.get(collector.collector_config_id),
        )
        for collector in collectors
    ]


def _serialize_collector_with_relations(collector, primary_index_set, primary_index_data, container_config):
    container_collector_type = container_config.collector_type if container_config else ""
    log_access_type = _get_log_access_type(
        collector=collector,
        container_collector_type=container_collector_type,
    )
    storage_cluster_id = None
    if primary_index_set:
        storage_cluster_id = primary_index_set.storage_cluster_id
    if storage_cluster_id is None and primary_index_data:
        storage_cluster_id = primary_index_data.storage_cluster_id

    return {
        "collector_config_id": collector.collector_config_id,
        "bk_biz_id": int(collector.bk_biz_id),
        "collector_config_name": collector.collector_config_name,
        "collector_scenario_id": collector.collector_scenario_id,
        "collector_scenario_name": str(CollectorScenarioEnum.get_choice_label(collector.collector_scenario_id)),
        "log_access_type": log_access_type,
        "log_access_type_name": str(LogAccessTypeEnum.get_choice_label(log_access_type)) if log_access_type else "",
        "target_object_type": collector.target_object_type,
        "bk_data_id": collector.bk_data_id,
        "table_id": collector.table_id,
        "data_link_id": collector.data_link_id,
        "index_set_id": primary_index_set.index_set_id if primary_index_set else None,
        "storage_cluster_id": storage_cluster_id,
        "storage_cluster_name": None,
        "retention": None,
        "storage_shards_nums": collector.storage_shards_nums,
        "storage_shards_size": collector.storage_shards_size,
        "storage_replies": collector.storage_replies,
        "subscription_id": collector.subscription_id,
        "etl_config": collector.etl_config,
        "is_active": collector.is_active,
        "enable_v4": collector.enable_v4,
        "bcs_cluster_id": collector.bcs_cluster_id,
        "environment": collector.environment,
        "created_at": collector.created_at.isoformat() if collector.created_at else None,
        "created_by": collector.created_by,
        "updated_at": collector.updated_at.isoformat() if collector.updated_at else None,
        "updated_by": collector.updated_by,
    }


def _get_primary_index_set(collector_config_id):
    index_set = _get_primary_index_set_map([collector_config_id]).get(collector_config_id)
    if not index_set:
        return None, None
    index_data = _get_primary_index_data_map([index_set]).get(index_set.index_set_id)
    return index_set, index_data


def _get_primary_index_set_map(collector_config_ids):
    result = {}
    if not collector_config_ids:
        return result
    index_sets = LogIndexSet.objects.filter(collector_config_id__in=collector_config_ids).order_by(
        "collector_config_id", "-updated_at", "-index_set_id"
    )
    for index_set in index_sets:
        if index_set.collector_config_id not in result:
            result[index_set.collector_config_id] = index_set
    return result


def _get_primary_index_data_map(index_sets):
    result = {}
    index_set_ids = [index_set.index_set_id for index_set in index_sets]
    if not index_set_ids:
        return result
    index_data_list = LogIndexSetData.objects.filter(
        index_set_id__in=index_set_ids, type=IndexSetDataType.RESULT_TABLE.value
    ).order_by("index_set_id", "-index_id")
    for index_data in index_data_list:
        if index_data.index_set_id not in result:
            result[index_data.index_set_id] = index_data
    return result


def _get_container_config_map(collector_config_ids):
    result = {}
    if not collector_config_ids:
        return result
    container_configs = ContainerCollectorConfig.objects.filter(collector_config_id__in=collector_config_ids).order_by(
        "collector_config_id", "-updated_at", "-id"
    )
    for container_config in container_configs:
        if container_config.collector_config_id not in result:
            result[container_config.collector_config_id] = container_config
    return result


def _get_collector_config_ids_by_storage_cluster(qs, storage_cluster_id):
    collector_config_ids = list(qs.values_list("collector_config_id", flat=True))
    primary_index_set_map = _get_primary_index_set_map(collector_config_ids)
    primary_index_data_map = _get_primary_index_data_map(primary_index_set_map.values())
    matched_collector_config_ids = []

    for collector_config_id in collector_config_ids:
        primary_index_set = primary_index_set_map.get(collector_config_id)
        if not primary_index_set:
            continue
        current_storage_cluster_id = primary_index_set.storage_cluster_id
        if current_storage_cluster_id is None:
            primary_index_data = primary_index_data_map.get(primary_index_set.index_set_id)
            if primary_index_data:
                current_storage_cluster_id = primary_index_data.storage_cluster_id
        if current_storage_cluster_id == storage_cluster_id:
            matched_collector_config_ids.append(collector_config_id)

    return matched_collector_config_ids


def _get_collector_config_ids_by_log_access_type(qs, log_access_type):
    collectors = list(qs.only("collector_config_id", "collector_scenario_id", "environment"))
    collector_config_ids = [collector.collector_config_id for collector in collectors]
    container_config_map = _get_container_config_map(collector_config_ids)
    matched_collector_config_ids = []

    for collector in collectors:
        container_config = container_config_map.get(collector.collector_config_id)
        container_collector_type = container_config.collector_type if container_config else ""
        if _get_log_access_type(collector, container_collector_type) == log_access_type:
            matched_collector_config_ids.append(collector.collector_config_id)

    return matched_collector_config_ids


def _get_log_access_type(collector, container_collector_type):
    return LogAccessTypeEnum.get_log_access_type(
        scenario_id="",
        collector_scenario_id=collector.collector_scenario_id,
        environment=collector.environment or "",
        container_collector_type=container_collector_type,
    )


def _get_index_set_relations(primary_index_set, primary_index_data, bkdata_clean):
    relations = []
    seen = set()
    if primary_index_set:
        _append_index_set_relation(
            relations,
            seen,
            relation_type="primary",
            index_set=primary_index_set,
            result_table_id=primary_index_data.result_table_id if primary_index_data else None,
        )
        parent_data = LogIndexSetData.objects.filter(
            result_table_id=str(primary_index_set.index_set_id), type=IndexSetDataType.INDEX_SET.value
        ).order_by("index_set_id")
        parent_index_set_ids = [item.index_set_id for item in parent_data]
        parent_index_sets = LogIndexSet.objects.filter(index_set_id__in=parent_index_set_ids, is_group=True)
        parent_map = {item.index_set_id: item for item in parent_index_sets}
        for parent_index_set_id in parent_index_set_ids:
            parent_index_set = parent_map.get(parent_index_set_id)
            if parent_index_set:
                _append_index_set_relation(
                    relations,
                    seen,
                    relation_type="parent_group",
                    index_set=parent_index_set,
                    result_table_id=None,
                )
    clean_index_set_ids = [item.log_index_set_id for item in bkdata_clean if item.log_index_set_id]
    clean_index_sets = LogIndexSet.objects.filter(index_set_id__in=clean_index_set_ids)
    clean_index_set_map = {item.index_set_id: item for item in clean_index_sets}
    for clean in bkdata_clean:
        clean_index_set = clean_index_set_map.get(clean.log_index_set_id)
        if clean_index_set:
            _append_index_set_relation(
                relations,
                seen,
                relation_type="bkdata_clean",
                index_set=clean_index_set,
                result_table_id=clean.result_table_id,
            )
    return relations


def _append_index_set_relation(relations, seen, relation_type, index_set, result_table_id):
    key = (relation_type, index_set.index_set_id)
    if key in seen:
        return
    seen.add(key)
    relations.append(
        {
            "relation_type": relation_type,
            "index_set_id": index_set.index_set_id,
            "index_set_name": index_set.index_set_name,
            "scenario_id": index_set.scenario_id,
            "scenario_name": str(dict(Scenario.CHOICES).get(index_set.scenario_id, "")),
            "result_table_id": result_table_id,
        }
    )


def _get_data_link(data_link_id):
    if not data_link_id:
        return None
    return DataLinkConfig.objects.filter(data_link_id=data_link_id).first()


def _get_container_config(collector_config_id):
    return ContainerCollectorConfig.objects.filter(collector_config_id=collector_config_id).first()


def _get_result_table_storage(table_id, storage_cluster_type):
    if not table_id:
        return None, {"code": "missing_table_id", "message": "collector has no result table id"}
    try:
        storage_info = TransferApi.get_result_table_storage(
            {"result_table_list": table_id, "storage_type": storage_cluster_type}
        )
    except Exception as err:  # noqa: BLE001
        return None, {"code": "result_table_storage_query_failed", "message": str(err)}
    result_table_storage = storage_info.get(table_id)
    if not result_table_storage:
        return None, {"code": "result_table_storage_not_found", "message": f"{table_id} storage not found"}
    return result_table_storage, None


def _get_raw_params(collector):
    container_config = _get_container_config(collector.collector_config_id)
    if container_config and container_config.params:
        return container_config.params
    return collector.params


def _get_bkdata_clean(collector_config_id):
    return list(BKDataClean.objects.filter(collector_config_id=collector_config_id).order_by("log_index_set_id"))


def _serialize_data_link(data_link):
    if data_link is None:
        return None
    return {
        "data_link_id": data_link.data_link_id,
        "link_group_name": data_link.link_group_name,
        "bk_biz_id": data_link.bk_biz_id,
        "kafka_cluster_id": data_link.kafka_cluster_id,
        "transfer_cluster_id": data_link.transfer_cluster_id,
        "es_cluster_ids": data_link.es_cluster_ids,
        "is_active": data_link.is_active,
        "is_edge_transport": data_link.is_edge_transport,
        "bk_tenant_id": data_link.bk_tenant_id,
    }


def _serialize_result_table_storage(result_table_storage):
    if result_table_storage is None:
        return {
            "storage_cluster_id": None,
            "retention": None,
            "allocation_min_days": None,
            "storage_shards_nums": None,
            "storage_shards_size": None,
            "storage_replies": None,
        }

    cluster_config = result_table_storage.get("cluster_config") or {}
    storage_config = result_table_storage.get("storage_config") or {}
    index_settings = storage_config.get("index_settings") or {}
    return {
        "storage_cluster_id": cluster_config.get("cluster_id"),
        "retention": storage_config.get("retention"),
        "allocation_min_days": storage_config.get("warm_phase_days"),
        "storage_shards_nums": index_settings.get("number_of_shards"),
        "storage_shards_size": _first_not_none(
            storage_config.get("storage_shards_size"),
            storage_config.get("shard_size"),
        ),
        "storage_replies": index_settings.get("number_of_replicas"),
    }


def _serialize_bkdata_clean(clean):
    return {
        "status": clean.status,
        "status_en": clean.status_en,
        "raw_data_id": clean.raw_data_id,
        "result_table_id": clean.result_table_id,
        "result_table_name": clean.result_table_name,
        "storage_cluster": clean.storage_cluster,
        "collector_config_id": clean.collector_config_id,
        "log_index_set_id": clean.log_index_set_id,
        "etl_config": clean.etl_config,
        "is_authorized": clean.is_authorized,
    }


def _apply_ordering(qs, ordering):
    ordering = ordering if ordering in _allowed_ordering() else "-updated_at"
    return qs.order_by(ordering)


def _allowed_ordering():
    fields = [
        "collector_config_id",
        "collector_config_name",
        "bk_data_id",
        "table_id",
        "updated_at",
        "bk_biz_id",
    ]
    return set(fields + [f"-{field}" for field in fields])


def _to_positive_int(value, default):
    if value in (None, ""):
        return default
    value = int(value)
    if value < 1:
        raise ValidationError("pagination value must be positive")
    return value


def _to_int_or_original(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _is_sensitive_key(key):
    key = str(key).lower()
    return any(keyword in key for keyword in SENSITIVE_KEYWORDS)
