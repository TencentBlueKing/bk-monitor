"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    _mask_sensitive_fields,
    build_response,
    count_by_field,
    get_bk_tenant_id,
    normalize_include,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from metadata import models
from metadata.utils import es_tools

FUNC_CLUSTER_INFO_LIST = "admin.cluster_info.list"
FUNC_CLUSTER_INFO_DETAIL = "admin.cluster_info.detail"
FUNC_CLUSTER_INFO_COMPONENT_CONFIG = "admin.cluster_info.component_config"
FUNC_CLUSTER_INFO_ES_OVERVIEW = "admin.cluster_info.es_overview"
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

CLUSTER_LIST_INCLUDE_VALUES = {"associated_counts"}
DEFAULT_LIST_INCLUDE = {"associated_counts"}
INCLUDE_VALUES = {"component_config"}
DEFAULT_DETAIL_INCLUDE = {"component_config"}

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


def _build_alias_summary(client: Any, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = _run_es_overview_query(
        "aliases",
        warnings,
        lambda: client.cat.aliases(format="json", params={"request_timeout": 10}),
    )
    if isinstance(aliases, list):
        alias_names = {str(alias.get("alias")) for alias in aliases if alias.get("alias")}
        index_names = {str(alias.get("index")) for alias in aliases if alias.get("index")}
        return {"count": len(alias_names), "relation_count": len(aliases), "index_count": len(index_names)}

    alias_map = _run_es_overview_query(
        "alias map",
        warnings,
        lambda: client.indices.get_alias(index="*"),
    )
    if not isinstance(alias_map, dict):
        return {"count": None, "relation_count": None, "index_count": None}

    alias_names: set[str] = set()
    relation_count = 0
    for detail in alias_map.values():
        if not isinstance(detail, dict):
            continue
        aliases_obj = detail.get("aliases")
        if not isinstance(aliases_obj, dict):
            continue
        alias_names.update(str(alias_name) for alias_name in aliases_obj)
        relation_count += len(aliases_obj)

    return {"count": len(alias_names), "relation_count": relation_count, "index_count": len(alias_map)}


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
            "aliases": _build_alias_summary(client, warnings),
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


def _serialize_cluster_info(cluster: models.ClusterInfo) -> dict[str, Any]:
    item = {field: serialize_value(getattr(cluster, field, None)) for field in CLUSTER_INFO_FIELDS}
    for sensitive_field, flag_field in SENSITIVE_FLAG_MAP.items():
        raw_value = getattr(cluster, sensitive_field, None)
        item[flag_field] = bool(raw_value)
    return item


def _get_storage_model_for_cluster_type(cluster_type: str) -> type[Any] | None:
    return STORAGE_MODEL_MAP.get(cluster_type)


def _build_cluster_info_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id)

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


def _enrich_clusters_with_datasource_count(clusters: list[models.ClusterInfo], bk_tenant_id: str) -> dict[int, int]:
    kafka_cluster_ids = [c.cluster_id for c in clusters if c.cluster_type == models.ClusterInfo.TYPE_KAFKA]
    if not kafka_cluster_ids:
        return {}
    return count_by_field(
        models.DataSource, group_field="mq_cluster_id", values=kafka_cluster_ids, bk_tenant_id=bk_tenant_id
    )


def _enrich_clusters_with_storage_count(clusters: list[models.ClusterInfo], bk_tenant_id: str) -> dict[int, int]:
    storage_model_map: dict[type[Any], list[int]] = {}
    for cluster in clusters:
        model_cls = _get_storage_model_for_cluster_type(cluster.cluster_type)
        if model_cls is None:
            continue
        storage_model_map.setdefault(model_cls, []).append(cluster.cluster_id)

    result: dict[int, int] = {}
    for model_cls, cluster_ids in storage_model_map.items():
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
        "bk_tenant_id": "可选，租户 ID",
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
    bk_tenant_id = get_bk_tenant_id(params)
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
        item["associated_datasources"] = datasource_count_map.get(cluster.cluster_id, 0)
        item["associated_storages"] = storage_count_map.get(cluster.cluster_id, 0)
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

    data: dict[str, Any] = {"cluster": _serialize_cluster_info(cluster)}
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

    storage_model = _get_storage_model_for_cluster_type(effective_cluster_type)
    if storage_model is not None:
        data["related_result_tables"] = storage_model.objects.filter(
            bk_tenant_id=bk_tenant_id, storage_cluster_id=cluster_id
        ).count()
    else:
        data["related_result_tables"] = 0

    return build_response(
        operation="cluster_info.detail",
        func_name=FUNC_CLUSTER_INFO_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
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
    FUNC_CLUSTER_INFO_ES_OVERVIEW,
    summary="Admin 查询 ES ClusterInfo 运行时大盘",
    description="inspect 级别能力，访问目标 ES 集群读取健康状态、存储使用量、索引/别名数量和 shard 使用情况。",
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
