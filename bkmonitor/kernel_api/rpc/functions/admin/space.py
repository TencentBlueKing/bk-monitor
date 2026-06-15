"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from typing import Any

from core.drf_resource.exceptions import CustomException
from django.db.models import Q
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.cluster_info import (
    _build_es_analysis_storage_index,
    _serialize_es_analysis_index_row,
)
from kernel_api.rpc.functions.admin.common import (
    build_response,
    filter_by_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    normalize_positive_int,
    paginate_queryset,
    require_bk_tenant_id,
    serialize_model,
)
from metadata import models
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes
from metadata.utils import es_tools

FUNC_SPACE_LIST = "admin.space.list"
FUNC_SPACE_DETAIL = "admin.space.detail"
FUNC_SPACE_ES_USAGE = "admin.space.es_usage"

INSPECT_SAFETY_LEVEL = "inspect"
ES_USAGE_TABLE_CHUNK_SIZE = 50
ES_USAGE_DEFAULT_TIMEOUT = 30
ES_USAGE_MAX_TIMEOUT = 120

SPACE_FIELDS = [
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
SPACE_RESOURCE_FIELDS = [
    "id",
    "bk_tenant_id",
    "space_type_id",
    "space_id",
    "resource_type",
    "resource_id",
    "dimension_values",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
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
VM_CLUSTER_SUMMARY_FIELDS = ["cluster_id", "cluster_name", "display_name", "cluster_type"]
ES_USAGE_RESULT_TABLE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "data_label",
    "default_storage",
    "is_enable",
    "is_deleted",
]
ES_USAGE_STORAGE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "storage_cluster_id",
    "source_type",
    "retention",
    "slice_size",
    "slice_gap",
    "date_format",
    "time_zone",
    "index_set",
    "need_create_index",
]
ORDERING_FIELDS = {
    "id",
    "space_uid",
    "space_type_id",
    "space_id",
    "space_name",
    "status",
    "is_bcs_valid",
    "is_global",
    "create_time",
    "last_modify_time",
}


def _split_space_uid(value: Any) -> tuple[str, str]:
    space_uid = str(value or "").strip()
    if not space_uid:
        raise CustomException(message="space_uid 为必填项")

    parts = space_uid.split(SPACE_UID_HYPHEN, 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise CustomException(message="space_uid 格式不合法，应为 <space_type_id>__<space_id>")
    return parts[0], parts[1]


def _compose_space_uid(space_type_id: str, space_id: str) -> str:
    return f"{space_type_id}{SPACE_UID_HYPHEN}{space_id}"


def _split_search_space_uid(value: str) -> tuple[str, str] | None:
    if value.count(SPACE_UID_HYPHEN) != 1:
        return None

    space_type_id, space_id = value.split(SPACE_UID_HYPHEN, 1)
    space_type_id = space_type_id.strip()
    space_id = space_id.strip()
    if not space_type_id or not space_id:
        return None
    return space_type_id, space_id


def _build_bk_biz_id(space: models.Space) -> int | None:
    if space.space_type_id == SpaceTypes.BKCC.value:
        try:
            return int(space.space_id)
        except (TypeError, ValueError):
            return None
    return -int(space.id)


def _serialize_space(space: models.Space) -> dict[str, Any]:
    item = serialize_model(space, SPACE_FIELDS)
    item["space_uid"] = _compose_space_uid(space.space_type_id, space.space_id)
    item["bk_biz_id"] = _build_bk_biz_id(space)
    return item


def _serialize_space_resource(resource: models.SpaceResource) -> dict[str, Any]:
    item = serialize_model(resource, SPACE_RESOURCE_FIELDS)
    item["space_uid"] = _compose_space_uid(resource.space_type_id, resource.space_id)
    return item


def _serialize_reverse_space_resource(
    resource: models.SpaceResource,
    spaces_by_key: dict[tuple[str, str], models.Space],
) -> dict[str, Any]:
    item = _serialize_space_resource(resource)
    related_space = spaces_by_key.get((resource.space_type_id, resource.space_id))
    item["space"] = _serialize_space(related_space) if related_space else None
    return item


def _serialize_vm_cluster(cluster: models.ClusterInfo | None) -> dict[str, Any] | None:
    return serialize_model(cluster, VM_CLUSTER_SUMMARY_FIELDS) if cluster else None


def _serialize_space_vm_info(
    space_vm_info: models.SpaceVMInfo,
    vm_clusters_by_id: dict[int, models.ClusterInfo],
) -> dict[str, Any]:
    return {
        "space_vm_info": serialize_model(space_vm_info, SPACE_VM_INFO_FIELDS),
        "vm_cluster": _serialize_vm_cluster(vm_clusters_by_id.get(space_vm_info.vm_cluster_id)),
    }


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _build_space_es_usage_prefix(space: models.Space) -> str:
    if space.space_type_id == SpaceTypes.BKCC.value:
        bk_biz_id = _build_bk_biz_id(space)
        if bk_biz_id is None:
            raise CustomException(message=f"Space 的 bk_biz_id 无法计算: space_uid={space.space_uid}")
        return f"{bk_biz_id}_"
    return f"space_{space.pk}_"


def _build_space_es_storage_queryset(bk_tenant_id: str, table_prefix: str):
    return (
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__startswith=table_prefix)
        .filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
        .order_by("table_id")
    )


def _load_es_usage_result_table_map(bk_tenant_id: str, table_ids: list[str]) -> dict[str, Any]:
    if not table_ids:
        return {}
    return {
        result_table.table_id: result_table
        for result_table in models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    }


def _serialize_es_usage_result_table(result_table: Any | None) -> dict[str, Any] | None:
    if result_table is None:
        return None
    return serialize_model(result_table, ES_USAGE_RESULT_TABLE_FIELDS)


def _empty_es_usage_summary() -> dict[str, Any]:
    return {
        "storage_count": 0,
        "index_count": 0,
        "docs_count": 0,
        "store_size_bytes": 0,
        "shards": 0,
        "health_counts": {},
    }


def _merge_es_usage_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["storage_count"] += source.get("storage_count") or 0
    target["index_count"] += source.get("index_count") or 0
    target["docs_count"] += source.get("docs_count") or 0
    target["store_size_bytes"] += source.get("store_size_bytes") or 0
    target["shards"] += source.get("shards") or 0
    for health, count in (source.get("health_counts") or {}).items():
        target["health_counts"][health] = target["health_counts"].get(health, 0) + count


def _add_index_to_es_usage_summary(summary: dict[str, Any], index_item: dict[str, Any]) -> None:
    summary["index_count"] += 1
    summary["docs_count"] += index_item.get("docs_count") or 0
    summary["store_size_bytes"] += index_item.get("store_bytes") or 0
    summary["shards"] += index_item.get("shards") or 0
    health = str(index_item.get("health") or "unknown")
    summary["health_counts"][health] = summary["health_counts"].get(health, 0) + 1


def _serialize_es_usage_storage(
    es_storage: Any,
    result_table: Any | None,
    role: str,
    historical_cluster_ids: set[int],
) -> dict[str, Any]:
    item = serialize_model(es_storage, ES_USAGE_STORAGE_FIELDS)
    item["role"] = role
    item["current_cluster_id"] = es_storage.storage_cluster_id
    item["historical_cluster_ids"] = sorted(historical_cluster_ids)
    item["result_table"] = _serialize_es_usage_result_table(result_table)
    item["summary"] = _empty_es_usage_summary()
    item["summary"]["storage_count"] = 1
    return item


def _chunked(values: list[str], chunk_size: int):
    for offset in range(0, len(values), chunk_size):
        yield values[offset : offset + chunk_size]


def _build_es_usage_index_patterns(table_ids: list[str]) -> list[str]:
    patterns: list[str] = []
    for table_id in table_ids:
        base_index = table_id.replace(".", "_")
        patterns.extend([f"v2_{base_index}_*", f"{base_index}_*"])
    return patterns


def _query_es_usage_index_rows(
    *,
    bk_tenant_id: str,
    cluster_id: int,
    table_ids: list[str],
    timeout: int,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        client = es_tools.get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except Exception as error:  # pylint: disable=broad-except
        warnings.append(
            {
                "code": "SPACE_ES_USAGE_CLIENT_UNAVAILABLE",
                "message": f"ES client 获取失败，已跳过该集群: cluster_id={cluster_id}",
                "details": {"cluster_id": cluster_id, "error": str(error)},
            }
        )
        return []

    rows: list[dict[str, Any]] = []
    for chunk in _chunked(table_ids, ES_USAGE_TABLE_CHUNK_SIZE):
        patterns = _build_es_usage_index_patterns(chunk)
        try:
            chunk_rows = client.cat.indices(
                index=",".join(patterns),
                h="index,health,status,docs.count,store.size,pri,rep",
                format="json",
                bytes="b",
                params={"request_timeout": timeout, "ignore_unavailable": "true", "allow_no_indices": "true"},
            )
        except Exception as error:  # pylint: disable=broad-except
            warnings.append(
                {
                    "code": "SPACE_ES_USAGE_INDEX_QUERY_FAILED",
                    "message": f"ES 索引统计查询失败，已跳过该批实体表: cluster_id={cluster_id}",
                    "details": {"cluster_id": cluster_id, "table_count": len(chunk), "error": str(error)},
                }
            )
            continue

        if isinstance(chunk_rows, list):
            rows.extend(row for row in chunk_rows if isinstance(row, dict))
            continue

        warnings.append(
            {
                "code": "SPACE_ES_USAGE_INDEX_QUERY_INVALID_RESPONSE",
                "message": f"ES 索引统计返回格式异常，已跳过该批实体表: cluster_id={cluster_id}",
                "details": {"cluster_id": cluster_id, "table_count": len(chunk)},
            }
        )
    return rows


def _build_es_usage_table_role(current_table_ids: set[str], historical_table_ids: set[str]) -> str:
    if current_table_ids and historical_table_ids:
        return "mixed"
    if historical_table_ids:
        return "historical"
    return "current"


def _build_space_es_usage_cluster(
    *,
    cluster: models.ClusterInfo,
    es_storages: list[Any],
    result_table_map: dict[str, Any],
    index_rows: list[dict[str, Any]],
    current_table_ids: set[str],
    historical_table_ids: set[str],
    historical_cluster_ids_by_table: dict[str, set[int]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    storage_by_table_id = {storage.table_id: storage for storage in es_storages}
    cluster_table_ids = sorted(current_table_ids | historical_table_ids)
    cluster_storages = [
        storage_by_table_id[table_id] for table_id in cluster_table_ids if table_id in storage_by_table_id
    ]
    storage_by_base, ambiguous_bases = _build_es_analysis_storage_index(cluster_storages, result_table_map, warnings)
    storage_items = {
        storage.table_id: _serialize_es_usage_storage(
            storage,
            result_table_map.get(storage.table_id),
            _build_es_usage_table_role(
                {storage.table_id} if storage.table_id in current_table_ids else set(),
                {storage.table_id} if storage.table_id in historical_table_ids else set(),
            ),
            historical_cluster_ids_by_table.get(storage.table_id, set()),
        )
        for storage in cluster_storages
    }
    summary = _empty_es_usage_summary()
    summary["storage_count"] = len(storage_items)
    seen_indices: set[str] = set()

    for row in index_rows:
        index_item = _serialize_es_analysis_index_row(row, storage_by_base, ambiguous_bases)
        table_id = index_item.get("matched_table_id")
        index_name = index_item.get("index")
        if index_item.get("match_status") != "matched" or not table_id or not index_name:
            continue
        if str(index_name) in seen_indices:
            continue
        seen_indices.add(str(index_name))
        storage_item = storage_items.get(str(table_id))
        if storage_item is None:
            continue
        _add_index_to_es_usage_summary(summary, index_item)
        _add_index_to_es_usage_summary(storage_item["summary"], index_item)

    return {
        "cluster": _serialize_vm_cluster(cluster),
        "summary": summary,
        "storages": list(storage_items.values()),
    }


def _build_space_es_usage_data(
    *,
    space: models.Space,
    bk_tenant_id: str,
    timeout: int,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    table_prefix = _build_space_es_usage_prefix(space)
    es_storages = list(_build_space_es_storage_queryset(bk_tenant_id, table_prefix))
    table_ids = [storage.table_id for storage in es_storages]
    result_table_map = _load_es_usage_result_table_map(bk_tenant_id, table_ids)
    current_table_ids_by_cluster: dict[int, set[str]] = defaultdict(set)
    historical_table_ids_by_cluster: dict[int, set[str]] = defaultdict(set)
    historical_cluster_ids_by_table: dict[str, set[int]] = defaultdict(set)
    current_cluster_id_by_table: dict[str, int] = {}

    for storage in es_storages:
        current_cluster_id_by_table[storage.table_id] = storage.storage_cluster_id
        current_table_ids_by_cluster[storage.storage_cluster_id].add(storage.table_id)

    records = list(
        models.StorageClusterRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            table_id__in=table_ids,
            is_deleted=False,
        ).order_by("table_id", "-create_time")
    )
    for record in records:
        table_id = record.table_id
        cluster_id = int(record.cluster_id)
        if cluster_id != current_cluster_id_by_table.get(table_id) or not record.is_current:
            historical_table_ids_by_cluster[cluster_id].add(table_id)
            historical_cluster_ids_by_table[table_id].add(cluster_id)

    cluster_ids = sorted(set(current_table_ids_by_cluster) | set(historical_table_ids_by_cluster))
    cluster_map = {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=cluster_ids)
    }
    clusters: list[dict[str, Any]] = []
    summary = _empty_es_usage_summary()
    summary["storage_count"] = len(es_storages)
    summary["cluster_count"] = 0

    for cluster_id in cluster_ids:
        cluster = cluster_map.get(cluster_id)
        if cluster is None:
            warnings.append(
                {
                    "code": "SPACE_ES_USAGE_CLUSTER_NOT_FOUND",
                    "message": f"未找到历史或当前 ES ClusterInfo，已跳过: cluster_id={cluster_id}",
                    "details": {"cluster_id": cluster_id},
                }
            )
            continue
        if cluster.cluster_type != models.ClusterInfo.TYPE_ES:
            warnings.append(
                {
                    "code": "SPACE_ES_USAGE_CLUSTER_TYPE_INVALID",
                    "message": f"ClusterInfo 不是 elasticsearch 类型，已跳过: cluster_id={cluster_id}",
                    "details": {"cluster_id": cluster_id, "cluster_type": cluster.cluster_type},
                }
            )
            continue

        cluster_table_ids = sorted(
            current_table_ids_by_cluster.get(cluster_id, set()) | historical_table_ids_by_cluster.get(cluster_id, set())
        )
        index_rows = _query_es_usage_index_rows(
            bk_tenant_id=bk_tenant_id,
            cluster_id=cluster_id,
            table_ids=cluster_table_ids,
            timeout=timeout,
            warnings=warnings,
        )
        cluster_payload = _build_space_es_usage_cluster(
            cluster=cluster,
            es_storages=es_storages,
            result_table_map=result_table_map,
            index_rows=index_rows,
            current_table_ids=current_table_ids_by_cluster.get(cluster_id, set()),
            historical_table_ids=historical_table_ids_by_cluster.get(cluster_id, set()),
            historical_cluster_ids_by_table=historical_cluster_ids_by_table,
            warnings=warnings,
        )
        clusters.append(cluster_payload)
        summary["cluster_count"] += 1
        cluster_summary = dict(cluster_payload["summary"])
        cluster_summary["storage_count"] = 0
        _merge_es_usage_summary(summary, cluster_summary)

    return {
        "space": _serialize_space(space),
        "query": {
            "prefix": table_prefix,
            "table_kind": "physical",
            "table_count": len(es_storages),
            "cluster_count": len(cluster_ids),
            "table_chunk_size": ES_USAGE_TABLE_CHUNK_SIZE,
        },
        "summary": summary,
        "clusters": clusters,
        "inspect": True,
    }


def _normalize_space_ordering(raw_ordering: Any) -> list[str]:
    ordering = normalize_ordering(raw_ordering, ORDERING_FIELDS, default="space_type_id")
    descending = ordering.startswith("-")
    field_name = ordering[1:] if descending else ordering
    prefix = "-" if descending else ""

    if field_name == "space_uid":
        return [f"{prefix}space_type_id", f"{prefix}space_id", "id"]
    return [ordering, "id"]


def _apply_space_search(queryset, raw_search: Any, raw_search_mode: Any):
    search = str(raw_search or "").strip()
    if not search:
        return queryset

    search_mode = str(raw_search_mode or "fuzzy").strip().lower()
    if search_mode not in {"fuzzy", "exact"}:
        raise CustomException(message="search_mode 仅支持 fuzzy / exact")

    space_uid_parts = _split_search_space_uid(search)
    if space_uid_parts:
        space_type_id, space_id = space_uid_parts
        if search_mode == "exact":
            return queryset.filter(space_type_id=space_type_id, space_id=space_id)
        return queryset.filter(space_type_id__iexact=space_type_id, space_id__icontains=space_id)

    if search_mode == "exact":
        return queryset.filter(Q(space_id=search) | Q(space_name=search))
    return queryset.filter(Q(space_id__icontains=search) | Q(space_name__icontains=search))


def _normalize_space_bk_biz_id(value: Any) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_biz_id 必须是整数") from error


def _apply_space_bk_biz_id_filter(queryset, raw_bk_biz_id: Any):
    bk_biz_id = _normalize_space_bk_biz_id(raw_bk_biz_id)
    if bk_biz_id is None:
        return queryset

    if bk_biz_id < 0:
        return queryset.filter(id=abs(bk_biz_id)).exclude(space_type_id=SpaceTypes.BKCC.value)

    return queryset.filter(space_type_id=SpaceTypes.BKCC.value, space_id=str(bk_biz_id))


def _build_space_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.Space.objects.all(), bk_tenant_id)
    queryset = _apply_space_search(queryset, params.get("search"), params.get("search_mode"))
    queryset = _apply_space_bk_biz_id_filter(queryset, params.get("bk_biz_id"))

    if params.get("space_uid"):
        space_type_id, space_id = _split_space_uid(params["space_uid"])
        queryset = queryset.filter(space_type_id=space_type_id, space_id=space_id)
    if params.get("space_type_id"):
        queryset = queryset.filter(space_type_id=str(params["space_type_id"]).strip())
    if params.get("space_id"):
        queryset = queryset.filter(space_id__icontains=str(params["space_id"]).strip())
    if params.get("space_name"):
        queryset = queryset.filter(space_name__icontains=str(params["space_name"]).strip())
    if params.get("status"):
        queryset = queryset.filter(status=str(params["status"]).strip())
    for field in ["is_bcs_valid", "is_global"]:
        field_value = normalize_optional_bool(params.get(field), field)
        if field_value is not None:
            queryset = queryset.filter(**{field: field_value})

    return queryset


@KernelRPCRegistry.register(
    FUNC_SPACE_LIST,
    summary="Admin 查询 Space 列表",
    description="只读查询 Space，支持受控过滤、白名单排序和分页；列表不展开 SpaceResource 或 SpaceDataSource。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID；缺省或空表示全租户查询",
        "search": "可选，统一搜索；匹配 space_uid / space_id / space_name，包含单个 __ 时按 space_uid 拆分",
        "search_mode": "可选，搜索模式 fuzzy / exact，默认 fuzzy",
        "space_uid": "可选，空间 UID，格式为 <space_type_id>__<space_id>",
        "bk_biz_id": "可选，精确匹配查询侧业务 ID 映射；bkcc 为正业务 ID，非 bkcc 为负 Space.id",
        "space_type_id": "可选，空间类型精确匹配",
        "space_id": "可选，空间 ID 模糊匹配",
        "space_name": "可选，空间名称模糊匹配",
        "status": "可选，空间状态，例如 normal / disabled",
        "is_bcs_valid": "可选，BCS 是否可用",
        "is_global": "可选，是否跨业务管理可用",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "search": "bkcc__2", "bk_biz_id": 2, "page": 1, "page_size": 20},
)
def list_spaces(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = _normalize_space_ordering(params.get("ordering"))

    queryset = _build_space_queryset(params, bk_tenant_id).order_by(*ordering)
    spaces, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_space(space) for space in spaces]

    return build_response(
        operation="space.list",
        func_name=FUNC_SPACE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_SPACE_DETAIL,
    summary="Admin 查询 Space 详情",
    description=(
        "只读查询 Space 基础信息、该空间下的 SpaceResource，以及基于 resource_type/resource_id "
        "反查到当前 Space 的 SpaceResource；额外按当前 Space 精确查询 SpaceVMInfo 默认 VM 集群映射；"
        "不展开 SpaceDataSource 或场景聚合。"
    ),
    params_schema={
        "bk_tenant_id": "必填，租户 ID",
        "space_uid": "必填，空间 UID，格式为 <space_type_id>__<space_id>",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2"},
)
def get_space_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = require_bk_tenant_id(params)
    space_type_id, space_id = _split_space_uid(params.get("space_uid"))

    try:
        space = models.Space.objects.get(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        )
    except models.Space.DoesNotExist as error:
        raise CustomException(message=f"未找到 Space: space_uid={params.get('space_uid')}") from error

    resources = [
        _serialize_space_resource(resource)
        for resource in models.SpaceResource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        ).order_by("resource_type", "resource_id", "id")
    ]
    reverse_resources = list(
        models.SpaceResource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            resource_type=space_type_id,
            resource_id=space_id,
        ).order_by("space_type_id", "space_id", "id")
    )
    reverse_resource_query = Q()
    for resource in reverse_resources:
        reverse_resource_query |= Q(space_type_id=resource.space_type_id, space_id=resource.space_id)

    reverse_spaces = (
        models.Space.objects.filter(bk_tenant_id=bk_tenant_id).filter(reverse_resource_query)
        if reverse_resources
        else []
    )
    reverse_spaces_by_key = {(space.space_type_id, space.space_id): space for space in reverse_spaces}
    space_vm_infos = list(
        models.SpaceVMInfo.objects.filter(space_type=space.space_type_id, space_id=space.space_id).order_by("id")
    )
    vm_cluster_ids = [info.vm_cluster_id for info in space_vm_infos]
    vm_clusters_by_id = {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=vm_cluster_ids)
    }

    return build_response(
        operation="space.detail",
        func_name=FUNC_SPACE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "space": _serialize_space(space),
            "space_resources": resources,
            "reverse_space_resources": [
                _serialize_reverse_space_resource(resource, reverse_spaces_by_key) for resource in reverse_resources
            ],
            "space_vm_infos": [
                _serialize_space_vm_info(space_vm_info, vm_clusters_by_id) for space_vm_info in space_vm_infos
            ],
        },
    )


@KernelRPCRegistry.register(
    FUNC_SPACE_ES_USAGE,
    summary="Admin 查询 Space ES 实体表使用统计",
    description=(
        "inspect 级别能力，按 Space 归属前缀匹配物理 ESStorage，并按当前/历史 ES 集群分批读取 "
        "cat.indices 聚合使用量；仅统计实体表，虚拟 ESStorage 不纳入统计。"
    ),
    params_schema={
        "bk_tenant_id": "必填，租户 ID",
        "space_uid": "必填，空间 UID，格式为 <space_type_id>__<space_id>",
        "timeout": f"可选，ES cat.indices request_timeout，默认 {ES_USAGE_DEFAULT_TIMEOUT}，最大 {ES_USAGE_MAX_TIMEOUT}",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2", "timeout": ES_USAGE_DEFAULT_TIMEOUT},
)
def get_space_es_usage(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = require_bk_tenant_id(params)
    space_type_id, space_id = _split_space_uid(params.get("space_uid"))
    timeout = normalize_positive_int(
        params.get("timeout"),
        "timeout",
        default=ES_USAGE_DEFAULT_TIMEOUT,
        maximum=ES_USAGE_MAX_TIMEOUT,
    )

    try:
        space = models.Space.objects.get(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        )
    except models.Space.DoesNotExist as error:
        raise CustomException(message=f"未找到 Space: space_uid={params.get('space_uid')}") from error

    warnings: list[dict[str, Any]] = []
    data = _build_space_es_usage_data(
        space=space,
        bk_tenant_id=bk_tenant_id,
        timeout=timeout,
        warnings=warnings,
    )
    response = build_response(
        operation="space.es_usage",
        func_name=FUNC_SPACE_ES_USAGE,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
    return _mark_inspect_response(response)
