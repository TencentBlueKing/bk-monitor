"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from typing import Any

from core.drf_resource.exceptions import CustomException
from django.db.models import Q
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    _mask_sensitive_fields,
    build_response,
    count_by_field,
    count_by_tenant_and_field,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    get_scoped_map_value,
    normalize_include,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_value,
)
from metadata import models
from metadata.utils import es_tools

FUNC_CLUSTER_INFO_LIST = "admin.cluster_info.list"
FUNC_CLUSTER_INFO_DETAIL = "admin.cluster_info.detail"
FUNC_CLUSTER_INFO_SPACE_VM_INFO_LIST = "admin.cluster_info.space_vm_info_list"
FUNC_CLUSTER_INFO_COMPONENT_CONFIG = "admin.cluster_info.component_config"
FUNC_CLUSTER_INFO_ES_OVERVIEW = "admin.cluster_info.es_overview"
FUNC_CLUSTER_INFO_ES_STORAGE_ANALYSIS = "admin.cluster_info.es_storage_analysis"
FUNC_CLUSTER_INFO_HEALTH_CHECK = "admin.cluster_info.health_check"
INSPECT_SAFETY_LEVEL = "inspect"

CLUSTER_INFO_FIELDS = [
    "cluster_id",
    "cluster_name",
    "display_name",
    "cluster_type",
    "domain_name",
    "port",
    "extranet_domain_name",
    "extranet_port",
    "description",
    "is_default_cluster",
    "schema",
    "is_ssl_verify",
    "ssl_verification_mode",
    "ssl_insecure_skip_verify",
    "is_auth",
    "sasl_mechanisms",
    "security_protocol",
    "registered_system",
    "registered_to_bkbase",
    "is_register_to_gse",
    "gse_stream_to_id",
    "label",
    "default_settings",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
    "version",
]

SENSITIVE_FIELDS = [
    "username",
    "password",
    "ssl_certificate_authorities",
    "ssl_certificate",
    "ssl_certificate_key",
]

SENSITIVE_FLAG_MAP = {f: f"has_{f}" for f in SENSITIVE_FIELDS}

ORDERING_FIELDS = {
    "cluster_id",
    "cluster_name",
    "cluster_type",
    "is_default_cluster",
    "registered_system",
    "create_time",
    "last_modify_time",
}
SPACE_VM_INFO_ORDERING_FIELDS = {"id", "space_type", "space_id", "status", "create_time", "update_time"}

CLUSTER_LIST_INCLUDE_VALUES = {"associated_counts"}
DEFAULT_LIST_INCLUDE = {"associated_counts"}
INCLUDE_VALUES = {"component_config"}
DEFAULT_DETAIL_INCLUDE = {"component_config"}

SPACE_VM_INFO_FIELDS = [
    "id",
    "space_type",
    "space_id",
    "vm_cluster_id",
    "vm_retention_time",
    "status",
    "creator",
    "create_time",
    "updater",
    "update_time",
]
SPACE_SUMMARY_FIELDS = [
    "id",
    "bk_tenant_id",
    "space_type_id",
    "space_id",
    "space_name",
    "space_code",
    "status",
    "time_zone",
    "language",
    "is_bcs_valid",
    "is_global",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]

ES_STORAGE_ANALYSIS_RESULT_TABLE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "data_label",
    "default_storage",
    "is_enable",
    "is_deleted",
]

STORAGE_MODEL_MAP: dict[str, type[Any] | None] = {
    models.ClusterInfo.TYPE_KAFKA: models.KafkaStorage,
    models.ClusterInfo.TYPE_ES: models.ESStorage,
    models.ClusterInfo.TYPE_INFLUXDB: models.InfluxDBStorage,
    models.ClusterInfo.TYPE_REDIS: models.RedisStorage,
    models.ClusterInfo.TYPE_ARGUS: models.ArgusStorage,
    models.ClusterInfo.TYPE_DORIS: models.DorisStorage,
    models.ClusterInfo.TYPE_VM: None,
    models.ClusterInfo.TYPE_BKDATA: None,
}


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_optional_int_param(params: dict[str, Any], field: str) -> int | None:
    value = params.get(field)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field} 必须是整数") from error


def _get_nested(data: dict[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _append_es_overview_warning(
    warnings: list[dict[str, Any]], code: str, message: str, error: Exception | None = None
) -> None:
    warning: dict[str, Any] = {"code": code, "message": message}
    if error is not None:
        warning["details"] = {"error": str(error)}
    warnings.append(warning)


def _run_es_overview_query(
    name: str,
    warnings: list[dict[str, Any]],
    query,
) -> Any:
    try:
        return query()
    except Exception as error:  # pylint: disable=broad-except
        _append_es_overview_warning(
            warnings,
            "ES_CLUSTER_OVERVIEW_QUERY_FAILED",
            f"ES 集群 {name} 查询失败",
            error,
        )
        return None


def _sum_allocation_bytes(allocations: list[dict[str, Any]], field: str) -> int | None:
    values = []
    for node in allocations:
        value = _parse_int(node.get(field))
        if value is not None:
            values.append(value)
    return sum(values) if values else None


def _calc_percent(used: int | None, total: int | None) -> float | None:
    if used is None or total in (None, 0):
        return None
    return round(used * 100 / total, 2)


def _extract_shard_limit(settings: dict[str, Any] | None) -> int | None:
    for scope in ("persistent", "transient", "defaults"):
        value = _get_nested(settings, [scope, "cluster", "max_shards_per_node"])
        parsed = _parse_int(value)
        if parsed is not None:
            return parsed
    return None


def _build_alias_count_summary(client: Any, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = _run_es_overview_query(
        "alias count",
        warnings,
        lambda: client.cat.aliases(format="json", params={"h": "alias", "request_timeout": 10}),
    )
    if not isinstance(aliases, list):
        return {"count": None, "relation_count": None, "index_count": None}

    alias_names = {str(alias.get("alias")) for alias in aliases if isinstance(alias, dict) and alias.get("alias")}
    return {"count": len(alias_names), "relation_count": len(aliases), "index_count": None}


def _build_es_cluster_overview(
    cluster: models.ClusterInfo, bk_tenant_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    client = es_tools.get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster.cluster_id)

    health = _run_es_overview_query("health", warnings, lambda: client.cluster.health())
    stats = _run_es_overview_query("stats", warnings, lambda: client.cluster.stats())
    settings = _run_es_overview_query(
        "settings",
        warnings,
        lambda: client.cluster.get_settings(include_defaults=True),
    )
    allocations = _run_es_overview_query(
        "allocation",
        warnings,
        lambda: client.cat.allocation(format="json", bytes="b", params={"request_timeout": 10}),
    )
    if not isinstance(allocations, list):
        allocations = []

    shard_limit_per_node = _extract_shard_limit(settings if isinstance(settings, dict) else None)
    data_node_count = _parse_int((health or {}).get("number_of_data_nodes")) if isinstance(health, dict) else None
    active_shards = _parse_int((health or {}).get("active_shards")) if isinstance(health, dict) else None
    initializing_shards = _parse_int((health or {}).get("initializing_shards")) if isinstance(health, dict) else None
    relocating_shards = _parse_int((health or {}).get("relocating_shards")) if isinstance(health, dict) else None
    unassigned_shards = _parse_int((health or {}).get("unassigned_shards")) if isinstance(health, dict) else None
    current_shards = sum(
        value or 0 for value in [active_shards, initializing_shards, relocating_shards, unassigned_shards]
    )
    max_shards = shard_limit_per_node * data_node_count if shard_limit_per_node and data_node_count else None

    disk_total = _sum_allocation_bytes(allocations, "disk.total")
    disk_available = _sum_allocation_bytes(allocations, "disk.avail")
    disk_used = _sum_allocation_bytes(allocations, "disk.used")
    if disk_used is None and disk_total is not None and disk_available is not None:
        disk_used = disk_total - disk_available

    indices_count = _parse_int(_get_nested(stats, ["indices", "count"])) if isinstance(stats, dict) else None
    indices_store_bytes = (
        _parse_int(_get_nested(stats, ["indices", "store", "size_in_bytes"])) if isinstance(stats, dict) else None
    )
    docs_count = _parse_int(_get_nested(stats, ["indices", "docs", "count"])) if isinstance(stats, dict) else None
    deleted_docs_count = (
        _parse_int(_get_nested(stats, ["indices", "docs", "deleted"])) if isinstance(stats, dict) else None
    )
    total_shards_from_stats = (
        _parse_int(_get_nested(stats, ["indices", "shards", "total"])) if isinstance(stats, dict) else None
    )

    return (
        {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "display_name": cluster.display_name,
            "cluster_type": cluster.cluster_type,
            "status": (health or {}).get("status") if isinstance(health, dict) else None,
            "timed_out": (health or {}).get("timed_out") if isinstance(health, dict) else None,
            "nodes": {
                "number_of_nodes": _parse_int((health or {}).get("number_of_nodes"))
                if isinstance(health, dict)
                else None,
                "number_of_data_nodes": data_node_count,
                "stats_total": _parse_int(_get_nested(stats, ["nodes", "count", "total"]))
                if isinstance(stats, dict)
                else None,
            },
            "storage": {
                "disk_used_bytes": disk_used,
                "disk_total_bytes": disk_total,
                "disk_available_bytes": disk_available,
                "disk_used_percent": _calc_percent(disk_used, disk_total),
                "indices_store_bytes": indices_store_bytes,
            },
            "indices": {
                "count": indices_count,
                "docs_count": docs_count,
                "deleted_docs_count": deleted_docs_count,
            },
            "aliases": _build_alias_count_summary(client, warnings),
            "shards": {
                "current": total_shards_from_stats or current_shards,
                "active": active_shards,
                "initializing": initializing_shards,
                "relocating": relocating_shards,
                "unassigned": unassigned_shards,
                "max_per_node": shard_limit_per_node,
                "max": max_shards,
                "used_percent": _calc_percent(total_shards_from_stats or current_shards, max_shards),
            },
            "health": serialize_value(health),
            "inspect": True,
        },
        warnings,
    )


def _parse_es_analysis_index_base(index_name: Any) -> str | None:
    normalized_index = str(index_name or "").strip()
    if not normalized_index:
        return None
    if normalized_index.startswith("v2_"):
        normalized_index = normalized_index[3:]

    parts = normalized_index.rsplit("_", 2)
    if len(parts) != 3:
        return None

    base_index, datetime_part, slice_part = parts
    if not base_index or not datetime_part.isdigit() or not slice_part.isdigit():
        return None
    return base_index


def _parse_es_analysis_owner(table_id: str | None) -> dict[str, Any]:
    if not table_id:
        return {"owner_type": "unknown", "bk_biz_id": None}

    biz_match = re.match(r"^(?P<biz_id>\d+)", table_id)
    if biz_match:
        return {"owner_type": "biz", "bk_biz_id": int(biz_match.group("biz_id"))}

    space_match = re.match(r"^space_(?P<space_id>\d+)(?:[_.]|$)", table_id)
    if space_match:
        return {"owner_type": "space", "bk_biz_id": -int(space_match.group("space_id"))}

    first_segment = table_id.split(".", 1)[0]
    if first_segment.startswith("space_"):
        return {"owner_type": "space", "bk_biz_id": None}

    return {"owner_type": "unknown", "bk_biz_id": None}


def _serialize_es_analysis_result_table(result_table: Any | None) -> dict[str, Any] | None:
    if result_table is None:
        return None
    return serialize_model(result_table, ES_STORAGE_ANALYSIS_RESULT_TABLE_FIELDS)


def _serialize_es_analysis_storage(es_storage: Any, result_table: Any | None) -> dict[str, Any]:
    return {
        "table_id": es_storage.table_id,
        "bk_tenant_id": es_storage.bk_tenant_id,
        "storage_cluster_id": es_storage.storage_cluster_id,
        "source_type": es_storage.source_type,
        "retention": es_storage.retention,
        "slice_size": es_storage.slice_size,
        "slice_gap": es_storage.slice_gap,
        "date_format": es_storage.date_format,
        "time_zone": es_storage.time_zone,
        "index_set": es_storage.index_set,
        "need_create_index": es_storage.need_create_index,
        "result_table": _serialize_es_analysis_result_table(result_table),
    }


def _build_es_analysis_storage_index(
    es_storages: list[Any], result_table_map: dict[str, Any], warnings: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    storage_by_base: dict[str, dict[str, Any]] = {}
    ambiguous_bases: set[str] = set()
    conflict_candidates: dict[str, list[str]] = {}

    for es_storage in es_storages:
        base_index = str(es_storage.table_id).replace(".", "_")
        item = {
            "base_index": base_index,
            "table_id": es_storage.table_id,
            "storage": _serialize_es_analysis_storage(es_storage, result_table_map.get(es_storage.table_id)),
        }

        if base_index in storage_by_base:
            ambiguous_bases.add(base_index)
            conflict_candidates.setdefault(base_index, [storage_by_base[base_index]["table_id"]]).append(
                es_storage.table_id
            )
            storage_by_base.pop(base_index, None)
            continue

        if base_index in ambiguous_bases:
            conflict_candidates.setdefault(base_index, []).append(es_storage.table_id)
            continue

        storage_by_base[base_index] = item

    for base_index, table_ids in sorted(conflict_candidates.items()):
        warnings.append(
            {
                "code": "ES_STORAGE_BASE_INDEX_CONFLICT",
                "message": f"多个 ESStorage 映射到相同 base_index，相关索引将归类为 other: base_index={base_index}",
                "details": {"base_index": base_index, "table_ids": sorted(set(table_ids))},
            }
        )

    return storage_by_base, ambiguous_bases


def _serialize_es_analysis_index_row(
    row: dict[str, Any], storage_by_base: dict[str, dict[str, Any]], ambiguous_bases: set[str]
) -> dict[str, Any]:
    index_name = str(row.get("index") or "")
    base_index = _parse_es_analysis_index_base(index_name)
    store_bytes = _parse_int(row.get("store.size")) or 0
    docs_count = _parse_int(row.get("docs.count"))
    primary_shards = _parse_int(row.get("pri"))
    replica_factor = _parse_int(row.get("rep"))
    replica_shards = (
        primary_shards * replica_factor if primary_shards is not None and replica_factor is not None else None
    )
    shards = primary_shards + replica_shards if primary_shards is not None and replica_shards is not None else None

    matched = storage_by_base.get(base_index) if base_index is not None else None
    if matched is not None:
        match_status = "matched"
        match_reason = "base_index"
        matched_table_id = matched["table_id"]
        matched_storage = matched["storage"]
    elif base_index in ambiguous_bases:
        match_status = "other"
        match_reason = "ambiguous_base_index"
        matched_table_id = None
        matched_storage = None
    elif base_index is None:
        match_status = "other"
        match_reason = "unrecognized_index_name"
        matched_table_id = None
        matched_storage = None
    else:
        match_status = "other"
        match_reason = "unmatched_base_index"
        matched_table_id = None
        matched_storage = None

    owner = _parse_es_analysis_owner(matched_table_id)
    return {
        "index": index_name,
        "base_index": base_index,
        "store_bytes": store_bytes,
        "docs_count": docs_count,
        "health": row.get("health"),
        "status": row.get("status"),
        "primary_shards": primary_shards,
        "replica_shards": replica_shards,
        "replica_factor": replica_factor,
        "shards": shards,
        "match_status": match_status,
        "match_reason": match_reason,
        "matched_table_id": matched_table_id,
        "matched_storage": matched_storage,
        **owner,
    }


def _build_es_storage_analysis(
    cluster: models.ClusterInfo, bk_tenant_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    client = es_tools.get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster.cluster_id)

    index_rows = _run_es_overview_query(
        "index analysis",
        warnings,
        lambda: client.cat.indices(
            index="*",
            h="index,health,status,docs.count,store.size,pri,rep",
            format="json",
            bytes="b",
            params={"request_timeout": 30},
        ),
    )
    if not isinstance(index_rows, list):
        index_rows = []
        _append_es_overview_warning(
            warnings,
            "ES_STORAGE_ANALYSIS_INDEX_ROWS_UNAVAILABLE",
            "ES 索引列表不可用，无法计算存储占用明细",
        )

    es_storages = list(
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, storage_cluster_id=cluster.cluster_id)
        .filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
        .order_by("table_id")
    )
    result_table_map = {
        result_table.table_id: result_table
        for result_table in models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=[storage.table_id for storage in es_storages]
        )
    }
    storage_by_base, ambiguous_bases = _build_es_analysis_storage_index(es_storages, result_table_map, warnings)

    indices = [
        _serialize_es_analysis_index_row(row, storage_by_base, ambiguous_bases)
        for row in index_rows
        if isinstance(row, dict)
    ]
    indices.sort(key=lambda item: item["store_bytes"], reverse=True)

    total_store_bytes = sum(item["store_bytes"] for item in indices)
    matched_indices = [item for item in indices if item["match_status"] == "matched"]
    other_indices = [item for item in indices if item["match_status"] != "matched"]
    matched_store_bytes = sum(item["store_bytes"] for item in matched_indices)
    other_store_bytes = sum(item["store_bytes"] for item in other_indices)

    return (
        {
            "cluster": {
                "cluster_id": cluster.cluster_id,
                "cluster_name": cluster.cluster_name,
                "display_name": cluster.display_name,
                "cluster_type": cluster.cluster_type,
            },
            "summary": {
                "index_count": len(indices),
                "total_store_bytes": total_store_bytes,
                "matched_index_count": len(matched_indices),
                "matched_store_bytes": matched_store_bytes,
                "other_index_count": len(other_indices),
                "other_store_bytes": other_store_bytes,
                "es_storage_count": len(es_storages),
            },
            "indices": indices,
            "inspect": True,
        },
        warnings,
    )


def _serialize_cluster_info(cluster: models.ClusterInfo) -> dict[str, Any]:
    item = {field: serialize_value(getattr(cluster, field, None)) for field in CLUSTER_INFO_FIELDS}
    for sensitive_field, flag_field in SENSITIVE_FLAG_MAP.items():
        raw_value = getattr(cluster, sensitive_field, None)
        item[flag_field] = bool(raw_value)
    return item


def _get_storage_model_for_cluster_type(cluster_type: str) -> type[Any] | None:
    return STORAGE_MODEL_MAP.get(cluster_type)


def _build_cluster_info_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.ClusterInfo.objects.all(), bk_tenant_id)

    cluster_id = _parse_optional_int_param(params, "cluster_id")
    if cluster_id is not None:
        queryset = queryset.filter(cluster_id=cluster_id)
    if params.get("cluster_type") not in (None, ""):
        queryset = queryset.filter(cluster_type=str(params["cluster_type"]).strip())
    if params.get("cluster_name"):
        queryset = queryset.filter(cluster_name__contains=str(params["cluster_name"]).strip())
    if params.get("registered_system") not in (None, ""):
        queryset = queryset.filter(registered_system=str(params["registered_system"]).strip())
    is_default_cluster = normalize_optional_bool(params.get("is_default_cluster"), "is_default_cluster")
    if is_default_cluster is not None:
        queryset = queryset.filter(is_default_cluster=is_default_cluster)

    return queryset


def _enrich_clusters_with_datasource_count(
    clusters: list[models.ClusterInfo], bk_tenant_id: str | None
) -> dict[Any, int]:
    kafka_cluster_ids = [c.cluster_id for c in clusters if c.cluster_type == models.ClusterInfo.TYPE_KAFKA]
    if not kafka_cluster_ids:
        return {}
    if bk_tenant_id is None:
        return count_by_tenant_and_field(models.DataSource, group_field="mq_cluster_id", values=kafka_cluster_ids)
    return count_by_field(
        models.DataSource, group_field="mq_cluster_id", values=kafka_cluster_ids, bk_tenant_id=bk_tenant_id
    )


def _enrich_clusters_with_storage_count(clusters: list[models.ClusterInfo], bk_tenant_id: str | None) -> dict[Any, int]:
    storage_model_map: dict[type[Any], list[int]] = {}
    vm_cluster_ids: list[int] = []
    for cluster in clusters:
        if cluster.cluster_type == models.ClusterInfo.TYPE_VM:
            vm_cluster_ids.append(cluster.cluster_id)
            continue
        model_cls = _get_storage_model_for_cluster_type(cluster.cluster_type)
        if model_cls is None:
            continue
        storage_model_map.setdefault(model_cls, []).append(cluster.cluster_id)

    result: dict[Any, int] = {}
    if vm_cluster_ids:
        if bk_tenant_id is None:
            result.update(
                count_by_tenant_and_field(models.AccessVMRecord, group_field="vm_cluster_id", values=vm_cluster_ids)
            )
        else:
            result.update(
                count_by_field(
                    models.AccessVMRecord,
                    group_field="vm_cluster_id",
                    values=vm_cluster_ids,
                    bk_tenant_id=bk_tenant_id,
                )
            )

    for model_cls, cluster_ids in storage_model_map.items():
        if bk_tenant_id is None:
            grouped = count_by_tenant_and_field(model_cls, group_field="storage_cluster_id", values=cluster_ids)
            result.update(grouped)
            continue
        grouped = count_by_field(
            model_cls, group_field="storage_cluster_id", values=cluster_ids, bk_tenant_id=bk_tenant_id
        )
        result.update(grouped)
    return result


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_LIST,
    summary="Admin 查询 ClusterInfo 列表",
    description="只读查询 ClusterInfo，支持受控过滤、白名单排序和分页；敏感字段以布尔标记代替。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "cluster_id": "可选，ClusterInfo.cluster_id 精确匹配",
        "cluster_type": "可选，集群类型精确匹配",
        "cluster_name": "可选，集群名称包含匹配",
        "is_default_cluster": "可选，是否默认集群",
        "registered_system": "可选，注册来源系统精确匹配",
        "include": "可选，展开范围；默认 associated_counts，传空列表可跳过关联统计",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}，默认 cluster_id",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20, "ordering": "cluster_id"},
)
def list_cluster_infos(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="cluster_id")
    includes = normalize_include(params.get("include"), CLUSTER_LIST_INCLUDE_VALUES, default=DEFAULT_LIST_INCLUDE)

    queryset = _build_cluster_info_queryset(params, bk_tenant_id).order_by(ordering, "cluster_id")
    clusters, total = paginate_queryset(queryset, page=page, page_size=page_size)

    datasource_count_map: dict[int, int] = {}
    storage_count_map: dict[int, int] = {}
    if "associated_counts" in includes:
        datasource_count_map = _enrich_clusters_with_datasource_count(clusters, bk_tenant_id)
        storage_count_map = _enrich_clusters_with_storage_count(clusters, bk_tenant_id)

    items = []
    for cluster in clusters:
        item = _serialize_cluster_info(cluster)
        item["associated_datasources"] = (
            get_scoped_map_value(datasource_count_map, cluster.bk_tenant_id, cluster.cluster_id) or 0
        )
        item["associated_storages"] = (
            get_scoped_map_value(storage_count_map, cluster.bk_tenant_id, cluster.cluster_id) or 0
        )
        items.append(item)

    return build_response(
        operation="cluster_info.list",
        func_name=FUNC_CLUSTER_INFO_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


def _resolve_cluster_type(params: dict[str, Any], cluster: models.ClusterInfo) -> str:
    override = params.get("cluster_type")
    return str(override).strip() if override not in (None, "") else cluster.cluster_type


def _split_space_uid_filter(value: Any) -> tuple[str, str]:
    space_uid = str(value or "").strip()
    parts = space_uid.split("__", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise CustomException(message="space_uid 格式不合法，应为 <space_type_id>__<space_id>")
    return parts[0], parts[1]


def _split_search_space_uid(value: str) -> tuple[str, str] | None:
    if value.count("__") != 1:
        return None
    space_type, space_id = value.split("__", 1)
    space_type = space_type.strip()
    space_id = space_id.strip()
    return (space_type, space_id) if space_type and space_id else None


def _compose_space_uid(space_type_id: str, space_id: str) -> str:
    return f"{space_type_id}__{space_id}"


def _serialize_space_summary(space: models.Space | None) -> dict[str, Any] | None:
    if space is None:
        return None
    item = serialize_model(space, SPACE_SUMMARY_FIELDS)
    item["space_uid"] = _compose_space_uid(space.space_type_id, space.space_id)
    return item


def _serialize_cluster_space_vm_info(
    space_vm_info: models.SpaceVMInfo,
    spaces_by_key: dict[tuple[str, str], models.Space],
) -> dict[str, Any]:
    space_key = (space_vm_info.space_type, space_vm_info.space_id)
    return {
        "space_vm_info": serialize_model(space_vm_info, SPACE_VM_INFO_FIELDS),
        "space": _serialize_space_summary(spaces_by_key.get(space_key)),
    }


def _space_pair_query(space_vm_infos: list[models.SpaceVMInfo]) -> Q:
    query = Q()
    for space_vm_info in space_vm_infos:
        query |= Q(space_type_id=space_vm_info.space_type, space_id=space_vm_info.space_id)
    return query


def _load_spaces_for_space_vm_infos(
    bk_tenant_id: str, space_vm_infos: list[models.SpaceVMInfo]
) -> dict[tuple[str, str], models.Space]:
    if not space_vm_infos:
        return {}
    query = _space_pair_query(space_vm_infos)
    spaces = models.Space.objects.filter(bk_tenant_id=bk_tenant_id).filter(query)
    return {(space.space_type_id, space.space_id): space for space in spaces}


def _build_space_vm_info_queryset(params: dict[str, Any], bk_tenant_id: str, cluster_id: int):
    queryset = models.SpaceVMInfo.objects.filter(vm_cluster_id=cluster_id)

    if params.get("space_uid"):
        space_type, space_id = _split_space_uid_filter(params["space_uid"])
        queryset = queryset.filter(space_type=space_type, space_id=space_id)
    if params.get("space_type") not in (None, ""):
        queryset = queryset.filter(space_type=str(params["space_type"]).strip())
    if params.get("space_id") not in (None, ""):
        queryset = queryset.filter(space_id__icontains=str(params["space_id"]).strip())
    if params.get("status") not in (None, ""):
        queryset = queryset.filter(status=str(params["status"]).strip())

    search = str(params.get("search") or "").strip()
    if search:
        search_query = Q(space_id__icontains=search)
        space_uid_parts = _split_search_space_uid(search)
        if space_uid_parts:
            search_query |= Q(space_type=space_uid_parts[0], space_id__icontains=space_uid_parts[1])
        matching_spaces = models.Space.objects.filter(bk_tenant_id=bk_tenant_id).filter(
            Q(space_id__icontains=search) | Q(space_name__icontains=search)
        )[:1000]
        for space in matching_spaces:
            search_query |= Q(space_type=space.space_type_id, space_id=space.space_id)
        queryset = queryset.filter(search_query)

    return queryset


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_DETAIL,
    summary="Admin 查询 ClusterInfo 详情",
    description="只读查询 ClusterInfo 详情及关联的 ClusterConfig 信息。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，集群 ID",
        "include": f"可选，展开范围: {', '.join(sorted(INCLUDE_VALUES))}",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 1, "include": ["component_config"]},
)
def get_cluster_info_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        cluster_id = int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    includes = normalize_include(params.get("include"), INCLUDE_VALUES, default=DEFAULT_DETAIL_INCLUDE)

    try:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 ClusterInfo: cluster_id={cluster_id}") from error

    effective_cluster_type = _resolve_cluster_type(params, cluster)

    cluster_item = _serialize_cluster_info(cluster)
    data: dict[str, Any] = {"cluster": cluster_item}
    warnings: list[dict[str, Any]] = []

    from metadata.models.data_link.data_link_configs import ClusterConfig
    from metadata.models.data_link.constants import DataLinkKind

    kind = ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP.get(effective_cluster_type)
    if kind is None:
        kind = DataLinkKind.KAFKACHANNEL.value

    namespaces = ClusterConfig.KIND_TO_NAMESPACES_MAP.get(kind, [])
    if not namespaces:
        kind_via_enum = DataLinkKind.KAFKACHANNEL.value
        namespaces = ClusterConfig.KIND_TO_NAMESPACES_MAP.get(kind_via_enum, [])

    cluster_name = cluster.cluster_name

    cluster_configs = list(
        ClusterConfig.objects.filter(
            bk_tenant_id=bk_tenant_id,
            namespace__in=namespaces,
            kind=kind,
            name=cluster_name,
        ).order_by("namespace")
    )

    cluster_config_items: list[dict[str, Any]] = []
    for cfg in cluster_configs:
        item: dict[str, Any] = {
            "namespace": cfg.namespace,
            "kind": cfg.kind,
            "name": cfg.name,
            "origin_config": cfg.origin_config,
            "create_time": serialize_value(cfg.create_time),
            "update_time": serialize_value(cfg.update_time),
        }
        if "component_config" in includes:
            try:
                item["component_config"] = _mask_sensitive_fields(cfg.component_config)
            except Exception:
                item["component_config"] = None
                warnings.append(
                    {
                        "code": "COMPONENT_CONFIG_UNAVAILABLE",
                        "message": (
                            f"component_config 获取失败: namespace={cfg.namespace}, kind={cfg.kind}, name={cfg.name}"
                        ),
                    }
                )
        cluster_config_items.append(item)

    data["cluster_configs"] = cluster_config_items

    datasource_count = 0
    if effective_cluster_type == models.ClusterInfo.TYPE_KAFKA:
        datasource_count = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, mq_cluster_id=cluster_id).count()
    data["related_datasources"] = datasource_count
    cluster_item["associated_datasources"] = datasource_count

    storage_count = 0
    if effective_cluster_type == models.ClusterInfo.TYPE_VM:
        storage_count = models.AccessVMRecord.objects.filter(
            bk_tenant_id=bk_tenant_id, vm_cluster_id=cluster_id
        ).count()
    else:
        storage_model = _get_storage_model_for_cluster_type(effective_cluster_type)
        if storage_model is not None:
            storage_count = storage_model.objects.filter(
                bk_tenant_id=bk_tenant_id, storage_cluster_id=cluster_id
            ).count()
    data["related_result_tables"] = storage_count
    cluster_item["associated_storages"] = storage_count

    return build_response(
        operation="cluster_info.detail",
        func_name=FUNC_CLUSTER_INFO_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_SPACE_VM_INFO_LIST,
    summary="Admin 查询 VM ClusterInfo 关联 SpaceVMInfo",
    description=(
        "只读分页查询指定 VM 集群关联的 SpaceVMInfo。该接口只面向 "
        "ClusterInfo.cluster_type=victoria_metrics 的集群，支持按 space_uid、space_type、"
        "space_id、status 或统一 search 检索，并补充当前租户下匹配的 Space 摘要。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，VM ClusterInfo.cluster_id",
        "search": "可选，统一搜索；匹配 space_uid / space_id / space_name",
        "space_uid": "可选，格式为 <space_type_id>__<space_id>",
        "space_type": "可选，SpaceVMInfo.space_type 精确匹配",
        "space_id": "可选，SpaceVMInfo.space_id 包含匹配",
        "status": "可选，SpaceVMInfo.status 精确匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(SPACE_VM_INFO_ORDERING_FIELDS))}，默认 id",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 10001, "search": "bkcc__2", "page": 1},
)
def list_cluster_space_vm_infos(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        cluster_id = int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    try:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 ClusterInfo: cluster_id={cluster_id}") from error

    if cluster.cluster_type != models.ClusterInfo.TYPE_VM:
        raise CustomException(message=f"cluster_id={cluster_id} 不是 victoria_metrics 集群")

    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), SPACE_VM_INFO_ORDERING_FIELDS, default="id")
    queryset = _build_space_vm_info_queryset(params, bk_tenant_id, cluster_id).order_by(ordering, "id")
    rows, total = paginate_queryset(queryset, page=page, page_size=page_size)
    spaces_by_key = _load_spaces_for_space_vm_infos(bk_tenant_id, rows)

    return build_response(
        operation="cluster_info.space_vm_info_list",
        func_name=FUNC_CLUSTER_INFO_SPACE_VM_INFO_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_cluster_space_vm_info(row, spaces_by_key) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_COMPONENT_CONFIG,
    summary="Admin 查询单个 ClusterConfig 的 ComponentConfig",
    description="根据 cluster_id、namespace、kind、name 查询单个 ClusterConfig 的 component_config。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，集群 ID",
        "namespace": "必填，数据链路命名空间",
        "kind": "必填，数据链路类型",
        "name": "必填，集群名称",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": 1,
        "namespace": "bkmonitor",
        "kind": "ElasticsearchCluster",
        "name": "es-cluster-1",
    },
)
def get_component_config(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    namespace = params.get("namespace")
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    kind = params.get("kind")
    if not kind:
        raise CustomException(message="kind 为必填项")
    name = params.get("name")
    if not name:
        raise CustomException(message="name 为必填项")

    from metadata.models.data_link.data_link_configs import ClusterConfig

    try:
        cfg = ClusterConfig.objects.get(
            bk_tenant_id=bk_tenant_id,
            namespace=str(namespace).strip(),
            kind=str(kind).strip(),
            name=str(name).strip(),
        )
    except ClusterConfig.DoesNotExist as error:
        raise CustomException(
            message=f"未找到 ClusterConfig: cluster_id={cluster_id}, namespace={namespace}, kind={kind}, name={name}"
        ) from error

    try:
        component_config = cfg.component_config
    except Exception:
        component_config = None

    component_config = _mask_sensitive_fields(component_config)

    return build_response(
        operation="cluster_info.component_config",
        func_name=FUNC_CLUSTER_INFO_COMPONENT_CONFIG,
        bk_tenant_id=bk_tenant_id,
        data={
            "component_config": component_config,
            "namespace": namespace,
            "kind": kind,
            "name": name,
        },
    )


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_HEALTH_CHECK,
    summary="Admin 探测非 ES ClusterInfo 健康状态",
    description=(
        "inspect 级别能力，针对非 elasticsearch ClusterInfo 调用模型侧 health_check，"
        "执行简单健康检查和连通性测试；ES 集群请使用 admin.cluster_info.es_overview。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，ClusterInfo.cluster_id，不能是 elasticsearch 集群",
        "timeout": "可选，探测超时时间，单位秒，必须是正整数；默认使用 ClusterInfo.DEFAULT_CHECK_TIMEOUT",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 1, "timeout": 5},
)
def check_cluster_info_health(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        cluster_id = int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    timeout = params.get("timeout")
    if timeout in (None, ""):
        timeout = None
    else:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError) as error:
            raise CustomException(message="timeout 必须是正整数") from error
        if timeout <= 0:
            raise CustomException(message="timeout 必须是正整数")

    try:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 ClusterInfo: cluster_id={cluster_id}") from error

    if cluster.cluster_type == models.ClusterInfo.TYPE_ES:
        raise CustomException(message="elasticsearch 集群已有独立大盘，请使用 admin.cluster_info.es_overview")

    response = build_response(
        operation="cluster_info.health_check",
        func_name=FUNC_CLUSTER_INFO_HEALTH_CHECK,
        bk_tenant_id=bk_tenant_id,
        data=cluster.health_check(timeout=timeout),
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_ES_OVERVIEW,
    summary="Admin 查询 ES ClusterInfo 运行时大盘",
    description="inspect 级别能力，访问目标 ES 集群读取健康状态、存储使用量、索引数量、别名数量和 shard 使用情况；只用轻量 alias 列计数，不读取详细 alias map。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，ClusterInfo.cluster_id，必须是 elasticsearch 集群",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 1},
)
def get_es_cluster_overview(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        cluster_id = int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    try:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 ClusterInfo: cluster_id={cluster_id}") from error

    if cluster.cluster_type != models.ClusterInfo.TYPE_ES:
        raise CustomException(message=f"cluster_id={cluster_id} 不是 elasticsearch 集群")

    data, warnings = _build_es_cluster_overview(cluster, bk_tenant_id)
    response = build_response(
        operation="cluster_info.es_overview",
        func_name=FUNC_CLUSTER_INFO_ES_OVERVIEW,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_CLUSTER_INFO_ES_STORAGE_ANALYSIS,
    summary="Admin 分析 ES ClusterInfo 索引存储占用并反向关联 ESStorage",
    description="inspect 级别能力，访问目标 ES 集群读取索引存储明细，并基于物理 ESStorage.table_id 反向归因；不处理虚拟 ESStorage，不执行任何写操作。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，ClusterInfo.cluster_id，必须是 elasticsearch 集群",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 1},
)
def analyze_es_storage_usage(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    try:
        cluster_id = int(cluster_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id 必须是整数") from error

    try:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 ClusterInfo: cluster_id={cluster_id}") from error

    if cluster.cluster_type != models.ClusterInfo.TYPE_ES:
        raise CustomException(message=f"cluster_id={cluster_id} 不是 elasticsearch 集群")

    data, warnings = _build_es_storage_analysis(cluster, bk_tenant_id)
    response = build_response(
        operation="cluster_info.es_storage_analysis",
        func_name=FUNC_CLUSTER_INFO_ES_STORAGE_ANALYSIS,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
    return _mark_inspect_response(response)
