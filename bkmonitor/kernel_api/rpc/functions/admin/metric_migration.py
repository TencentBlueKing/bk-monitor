"""V3/V4 指标迁移盘点查询。"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from django.db.models import Count, Max, Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.collect_plugin import (
    _collect_config_counts,
    _load_versions_by_plugin_key,
    _select_current_version,
    _serialize_plugin_summary,
)
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    filter_by_tenant_resource_pairs,
    get_page_list_bk_tenant_id,
    normalize_int_list_filter,
    normalize_optional_bool,
    normalize_pagination,
    normalize_string_list_filter,
    serialize_model,
)
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.constants import SpaceTypes
from monitor_web.models.plugin import CollectorPluginMeta

FUNC_DATASOURCE_METRIC_MIGRATION_LIST = "admin.datasource.metric_migration_list"

METRIC_CATEGORIES = {"custom_metric", "plugin_metric", "bcs_metric", "other_metric"}
BCS_METRIC_DATA_ID_FIELDS = ("K8sMetricDataID", "CustomMetricDataID")
PROCESS_DATASOURCE_PATTERN = re.compile(
    r"^(?P<bk_biz_id>-?\d+)_custom_time_series_process_(?:perf|port)$",
    re.IGNORECASE,
)

DATASOURCE_FIELDS = [
    "bk_data_id",
    "bk_tenant_id",
    "data_name",
    "data_description",
    "etl_config",
    "type_label",
    "source_label",
    "is_enable",
    "is_custom_source",
    "is_platform_data_id",
    "space_type_id",
    "space_uid",
    "created_from",
    "mq_cluster_id",
    "mq_config_id",
    "transfer_cluster_id",
    "create_time",
    "last_modify_time",
]
RESULT_TABLE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "data_label",
    "label",
    "default_storage",
    "is_enable",
    "is_deleted",
]
SPACE_FIELDS = [
    "space_type_id",
    "space_id",
    "bk_tenant_id",
    "space_name",
    "space_code",
    "status",
    "is_bcs_valid",
    "is_global",
]
KAFKA_CLUSTER_FIELDS = [
    "cluster_id",
    "cluster_name",
    "display_name",
    "cluster_type",
    "is_default_cluster",
    "registered_system",
]
KAFKA_TOPIC_FIELDS = ["id", "bk_data_id", "topic", "partition", "batch_size", "flush_interval", "consume_rate"]
CUSTOM_GROUP_FIELDS = [
    "time_series_group_id",
    "time_series_group_name",
    "bk_data_id",
    "bk_biz_id",
    "bk_tenant_id",
    "table_id",
    "label",
    "is_enable",
    "is_delete",
    "is_split_measurement",
    "last_modify_time",
]
BCS_CLUSTER_FIELDS = [
    "cluster_id",
    "bcs_api_cluster_id",
    "bk_biz_id",
    "bk_tenant_id",
    "project_id",
    "status",
    "K8sMetricDataID",
    "CustomMetricDataID",
]


def _tenant_key(instance: Any, resource_id: Any) -> tuple[str | None, Any]:
    return getattr(instance, "bk_tenant_id", None), resource_id


def _pairs(queryset: Any, resource_field: str = "bk_data_id") -> set[tuple[str | None, Any]]:
    return {
        (bk_tenant_id, resource_id)
        for bk_tenant_id, resource_id in queryset.values_list("bk_tenant_id", resource_field)
        if bk_tenant_id not in (None, "") and resource_id not in (None, "")
    }


def _filter_by_pairs(queryset: Any, pairs: Iterable[tuple[str | None, int]]) -> Any:
    # DataSource.bk_data_id 是主键；pairs 在生成时已经带租户过滤，因此使用主键 IN
    # 避免在跨租户大结果集上生成成千上万个 OR 条件。
    data_ids = {int(bk_data_id) for _tenant_id, bk_data_id in pairs if bk_data_id not in (None, "")}
    return queryset.filter(bk_data_id__in=data_ids) if data_ids else queryset.none()


def _parse_optional_int(value: Any, field_name: str, *, minimum: int | None = None) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise CustomException(message=f"{field_name} 必须是整数")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error
    if minimum is not None and normalized < minimum:
        raise CustomException(message=f"{field_name} 必须大于等于 {minimum}")
    return normalized


def _normalize_categories(params: dict[str, Any]) -> list[str]:
    categories = normalize_string_list_filter(params, "scene_category", "scene_categories")
    unsupported = set(categories) - METRIC_CATEGORIES
    if unsupported:
        raise CustomException(message=f"不支持的场景分类: {', '.join(sorted(unsupported))}")
    return categories


def _bcs_pairs(queryset: Any) -> set[tuple[str | None, int]]:
    result: set[tuple[str | None, int]] = set()
    for cluster in queryset.only("bk_tenant_id", *BCS_METRIC_DATA_ID_FIELDS):
        for field_name in BCS_METRIC_DATA_ID_FIELDS:
            data_id = getattr(cluster, field_name, 0)
            if data_id and data_id > 0:
                result.add((cluster.bk_tenant_id, data_id))
    return result


def _plugin_data_name(plugin: CollectorPluginMeta) -> str:
    return f"{plugin.plugin_type}_{plugin.plugin_id}".lower()


def _plugin_pairs(plugin_queryset: Any, datasource_queryset: Any) -> set[tuple[str | None, int]]:
    names_by_tenant: dict[str, set[str]] = defaultdict(set)
    for plugin in plugin_queryset.only("bk_tenant_id", "plugin_type", "plugin_id"):
        if plugin.bk_tenant_id:
            names_by_tenant[plugin.bk_tenant_id].add(_plugin_data_name(plugin))
    if not names_by_tenant:
        return set()
    query = Q()
    for tenant_id, data_names in names_by_tenant.items():
        query |= Q(bk_tenant_id=tenant_id, data_name__in=data_names)
    matched = datasource_queryset.filter(query)
    return _pairs(matched)


def _process_pairs(datasource_queryset: Any, bk_biz_id: int | None = None) -> set[tuple[str | None, int]]:
    queryset = datasource_queryset.filter(data_name__icontains="_custom_time_series_process_")
    result: set[tuple[str | None, int]] = set()
    for tenant_id, data_id, data_name in queryset.values_list("bk_tenant_id", "bk_data_id", "data_name"):
        match = PROCESS_DATASOURCE_PATTERN.fullmatch(str(data_name))
        if not match:
            continue
        if bk_biz_id is not None and int(match.group("bk_biz_id")) != bk_biz_id:
            continue
        result.add((tenant_id, data_id))
    return result


def _result_table_pairs(
    *,
    bk_tenant_id: str | None,
    table_ids: list[str] | None = None,
    bk_biz_id: int | None = None,
    is_enable: bool | None = None,
    is_deleted: bool | None = None,
) -> set[tuple[str | None, int]]:
    if table_ids and bk_biz_id is None and is_enable is None and is_deleted is None:
        relations = filter_by_bk_tenant_id(models.DataSourceResultTable.objects.all(), bk_tenant_id).filter(
            table_id__in=table_ids
        )
        return _pairs(relations)
    result_tables = filter_by_bk_tenant_id(models.ResultTable.objects.all(), bk_tenant_id)
    if table_ids:
        result_tables = result_tables.filter(table_id__in=table_ids)
    if bk_biz_id is not None:
        result_tables = result_tables.filter(bk_biz_id=bk_biz_id)
    if is_enable is not None:
        result_tables = result_tables.filter(is_enable=is_enable)
    if is_deleted is not None:
        result_tables = result_tables.filter(is_deleted=is_deleted)
    table_pairs = set(result_tables.values_list("bk_tenant_id", "table_id"))
    if not table_pairs:
        return set()
    relations = filter_by_tenant_resource_pairs(models.DataSourceResultTable.objects.all(), "table_id", table_pairs)
    return _pairs(relations)


def _space_pairs(datasource_queryset: Any, bk_tenant_id: str | None, space_uid: str) -> set[tuple[str | None, int]]:
    if "__" not in space_uid:
        return _pairs(datasource_queryset.filter(space_uid=space_uid))
    space_type_id, space_id = space_uid.split("__", 1)
    relations = filter_by_bk_tenant_id(models.SpaceDataSource.objects.all(), bk_tenant_id).filter(
        space_type_id=space_type_id,
        space_id=space_id,
    )
    return _pairs(relations) | _pairs(datasource_queryset.filter(space_uid=space_uid))


def _biz_pairs(datasource_queryset: Any, bk_tenant_id: str | None, bk_biz_id: int) -> set[tuple[str | None, int]]:
    result = _result_table_pairs(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    result |= _pairs(
        filter_by_bk_tenant_id(models.TimeSeriesGroup.objects.all(), bk_tenant_id).filter(bk_biz_id=bk_biz_id)
    )
    result |= _bcs_pairs(
        filter_by_bk_tenant_id(models.BCSClusterInfo.objects.all(), bk_tenant_id).filter(bk_biz_id=bk_biz_id)
    )
    plugins = filter_by_bk_tenant_id(CollectorPluginMeta.origin_objects.all(), bk_tenant_id).filter(bk_biz_id=bk_biz_id)
    result |= _plugin_pairs(plugins, datasource_queryset)
    result |= _process_pairs(datasource_queryset, bk_biz_id)
    result |= _pairs(
        filter_by_bk_tenant_id(models.SpaceDataSource.objects.all(), bk_tenant_id).filter(
            space_type_id=SpaceTypes.BKCC.value,
            space_id=str(bk_biz_id),
        )
    )
    return result | _pairs(datasource_queryset.filter(space_uid=f"{SpaceTypes.BKCC.value}__{bk_biz_id}"))


def _category_pairs(
    datasource_queryset: Any,
    bk_tenant_id: str | None,
) -> dict[str, set[tuple[str | None, int]]]:
    custom_pairs = _pairs(filter_by_bk_tenant_id(models.TimeSeriesGroup.objects.all(), bk_tenant_id))
    bcs_pairs = _bcs_pairs(filter_by_bk_tenant_id(models.BCSClusterInfo.objects.all(), bk_tenant_id))
    plugin_pairs = _plugin_pairs(
        filter_by_bk_tenant_id(CollectorPluginMeta.origin_objects.all(), bk_tenant_id), datasource_queryset
    ) | _process_pairs(datasource_queryset)
    known_pairs = custom_pairs | bcs_pairs | plugin_pairs
    datasource_pairs = _pairs(datasource_queryset)
    return {
        "custom_metric": custom_pairs,
        "plugin_metric": plugin_pairs,
        "bcs_metric": bcs_pairs,
        "other_metric": datasource_pairs - known_pairs,
    }


def _build_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> Any:
    queryset = filter_by_bk_tenant_id(
        models.DataSource.objects.filter(
            created_from=DataIdCreatedFromSystem.BKGSE.value,
            type_label="time_series",
        ),
        bk_tenant_id,
    )

    data_ids = normalize_int_list_filter(params, "bk_data_id", "bk_data_ids", positive=True)
    if data_ids:
        queryset = queryset.filter(bk_data_id__in=data_ids)
    if params.get("data_name") not in (None, ""):
        queryset = queryset.filter(data_name__icontains=str(params["data_name"]).strip())
    for singular, plural in (
        ("etl_config", "etl_configs"),
        ("source_label", "source_labels"),
        ("transfer_cluster_id", "transfer_cluster_ids"),
    ):
        values = normalize_string_list_filter(params, singular, plural)
        if values:
            queryset = queryset.filter(**{f"{singular}__in": values})
    mq_cluster_ids = normalize_int_list_filter(params, "mq_cluster_id", "mq_cluster_ids", positive=True)
    if mq_cluster_ids:
        queryset = queryset.filter(mq_cluster_id__in=mq_cluster_ids)
    for field_name in ("is_enable", "is_platform_data_id"):
        value = normalize_optional_bool(params.get(field_name), field_name)
        if value is not None:
            queryset = queryset.filter(**{field_name: value})

    table_ids = normalize_string_list_filter(params, "table_id", "table_ids")
    rt_is_enable = normalize_optional_bool(params.get("result_table_is_enable"), "result_table_is_enable")
    rt_is_deleted = normalize_optional_bool(params.get("result_table_is_deleted"), "result_table_is_deleted")
    if table_ids or rt_is_enable is not None or rt_is_deleted is not None:
        queryset = _filter_by_pairs(
            queryset,
            _result_table_pairs(
                bk_tenant_id=bk_tenant_id,
                table_ids=table_ids,
                is_enable=rt_is_enable,
                is_deleted=rt_is_deleted,
            ),
        )

    bk_biz_id = _parse_optional_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = _filter_by_pairs(queryset, _biz_pairs(queryset, bk_tenant_id, bk_biz_id))

    space_uid = str(params.get("space_uid") or "").strip()
    if space_uid:
        queryset = _filter_by_pairs(queryset, _space_pairs(queryset, bk_tenant_id, space_uid))

    plugin_id = str(params.get("plugin_id") or "").strip()
    if plugin_id:
        plugins = filter_by_bk_tenant_id(CollectorPluginMeta.origin_objects.all(), bk_tenant_id).filter(
            plugin_id__icontains=plugin_id
        )
        queryset = _filter_by_pairs(queryset, _plugin_pairs(plugins, queryset))

    bcs_cluster_id = str(params.get("bcs_cluster_id") or "").strip()
    if bcs_cluster_id:
        clusters = filter_by_bk_tenant_id(models.BCSClusterInfo.objects.all(), bk_tenant_id).filter(
            cluster_id__icontains=bcs_cluster_id
        )
        queryset = _filter_by_pairs(queryset, _bcs_pairs(clusters))

    categories = _normalize_categories(params)
    if categories:
        category_pairs = _category_pairs(queryset, bk_tenant_id)
        selected_pairs: set[tuple[str | None, int]] = set()
        for category in categories:
            selected_pairs |= category_pairs[category]
        queryset = _filter_by_pairs(queryset, selected_pairs)

    return queryset


def _serialize_spaces(datasources: list[models.DataSource]) -> dict[tuple[str | None, int], list[dict[str, Any]]]:
    datasource_pairs = {_tenant_key(item, item.bk_data_id) for item in datasources}
    relations = list(
        filter_by_tenant_resource_pairs(models.SpaceDataSource.objects.all(), "bk_data_id", datasource_pairs).order_by(
            "bk_tenant_id", "bk_data_id", "space_type_id", "space_id"
        )
    )
    space_keys = {(relation.bk_tenant_id, relation.space_type_id, relation.space_id) for relation in relations}
    for datasource in datasources:
        if "__" in (datasource.space_uid or ""):
            space_type_id, space_id = datasource.space_uid.split("__", 1)
            space_keys.add((datasource.bk_tenant_id, space_type_id, space_id))

    query = Q()
    for tenant_id, space_type_id, space_id in space_keys:
        query |= Q(bk_tenant_id=tenant_id, space_type_id=space_type_id, space_id=space_id)
    spaces = models.Space.objects.filter(query) if query else models.Space.objects.none()
    space_map = {(space.bk_tenant_id, space.space_type_id, space.space_id): space for space in spaces}
    result: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    relation_keys: set[tuple[str | None, int, str, str]] = set()
    for relation in relations:
        key = (relation.bk_tenant_id, relation.bk_data_id)
        relation_keys.add((relation.bk_tenant_id, relation.bk_data_id, relation.space_type_id, relation.space_id))
        space = space_map.get((relation.bk_tenant_id, relation.space_type_id, relation.space_id))
        item = (
            serialize_model(space, SPACE_FIELDS)
            if space
            else {
                "space_type_id": relation.space_type_id,
                "space_id": relation.space_id,
                "bk_tenant_id": relation.bk_tenant_id,
                "space_name": None,
                "space_code": None,
                "status": None,
                "is_bcs_valid": None,
                "is_global": None,
            }
        )
        item.update(
            {
                "space_uid": f"{relation.space_type_id}__{relation.space_id}",
                "from_authorization": relation.from_authorization,
                "relation_source": "space_datasource",
                "record_exists": space is not None,
            }
        )
        result[key].append(item)

    for datasource in datasources:
        if "__" not in (datasource.space_uid or ""):
            continue
        space_type_id, space_id = datasource.space_uid.split("__", 1)
        relation_key = (datasource.bk_tenant_id, datasource.bk_data_id, space_type_id, space_id)
        if relation_key in relation_keys:
            continue
        space = space_map.get((datasource.bk_tenant_id, space_type_id, space_id))
        item = (
            serialize_model(space, SPACE_FIELDS)
            if space
            else {
                "space_type_id": space_type_id,
                "space_id": space_id,
                "bk_tenant_id": datasource.bk_tenant_id,
                "space_name": None,
                "space_code": None,
                "status": None,
                "is_bcs_valid": None,
                "is_global": None,
            }
        )
        item.update(
            {
                "space_uid": datasource.space_uid,
                "from_authorization": False,
                "relation_source": "datasource",
                "record_exists": space is not None,
            }
        )
        result[(datasource.bk_tenant_id, datasource.bk_data_id)].append(item)
    return result


def _serialize_result_tables(
    datasources: list[models.DataSource],
) -> dict[tuple[str | None, int], list[dict[str, Any]]]:
    datasource_pairs = {_tenant_key(item, item.bk_data_id) for item in datasources}
    relations = list(
        filter_by_tenant_resource_pairs(
            models.DataSourceResultTable.objects.all(), "bk_data_id", datasource_pairs
        ).order_by("bk_tenant_id", "bk_data_id", "table_id")
    )
    table_pairs = {(item.bk_tenant_id, item.table_id) for item in relations}
    result_tables = filter_by_tenant_resource_pairs(models.ResultTable.objects.all(), "table_id", table_pairs)
    result_table_map = {(item.bk_tenant_id, item.table_id): item for item in result_tables}
    result: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        result_table = result_table_map.get((relation.bk_tenant_id, relation.table_id))
        item = (
            serialize_model(result_table, RESULT_TABLE_FIELDS)
            if result_table
            else {
                "table_id": relation.table_id,
                "bk_tenant_id": relation.bk_tenant_id,
                "table_name_zh": None,
                "bk_biz_id": None,
                "data_label": None,
                "label": None,
                "default_storage": None,
                "is_enable": None,
                "is_deleted": None,
            }
        )
        item["record_exists"] = result_table is not None
        result[(relation.bk_tenant_id, relation.bk_data_id)].append(item)
    return result


def _serialize_custom_groups(
    datasources: list[models.DataSource],
) -> dict[tuple[str | None, int], list[dict[str, Any]]]:
    datasource_pairs = {_tenant_key(item, item.bk_data_id) for item in datasources}
    groups = filter_by_tenant_resource_pairs(models.TimeSeriesGroup.objects.all(), "bk_data_id", datasource_pairs)
    result: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    for group in groups.order_by("bk_tenant_id", "bk_data_id", "time_series_group_id"):
        result[(group.bk_tenant_id, group.bk_data_id)].append(serialize_model(group, CUSTOM_GROUP_FIELDS))
    return result


def _serialize_plugins(datasources: list[models.DataSource]) -> dict[tuple[str | None, int], list[dict[str, Any]]]:
    candidate_pairs: set[tuple[str | None, str]] = set()
    normal_candidates: dict[tuple[str | None, int], tuple[str | None, str]] = {}
    plugin_types = sorted(
        {str(value) for value, _label in CollectorPluginMeta.PLUGIN_TYPE_CHOICES},
        key=len,
        reverse=True,
    )
    process_candidates: dict[tuple[str | None, int], int] = {}
    for datasource in datasources:
        key = (datasource.bk_tenant_id, datasource.bk_data_id)
        normalized_name = datasource.data_name.lower()
        process_match = PROCESS_DATASOURCE_PATTERN.fullmatch(normalized_name)
        if process_match:
            process_candidates[key] = int(process_match.group("bk_biz_id"))
            continue
        for plugin_type in plugin_types:
            prefix = f"{plugin_type}_".lower()
            if not normalized_name.startswith(prefix):
                continue
            plugin_id = normalized_name[len(prefix) :]
            if plugin_id:
                plugin_key = (datasource.bk_tenant_id, plugin_id)
                candidate_pairs.add(plugin_key)
                normal_candidates[key] = plugin_key
            break

    plugin_query = CollectorPluginMeta.origin_objects.none()
    plugin_filter = Q()
    for tenant_id, plugin_id in candidate_pairs:
        plugin_filter |= Q(bk_tenant_id=tenant_id, plugin_id__iexact=plugin_id)
    if plugin_filter:
        plugin_query = CollectorPluginMeta.origin_objects.filter(plugin_filter)
    process_query = CollectorPluginMeta.origin_objects.none()
    process_filter = Q()
    for tenant_id, bk_biz_id in set((key[0], biz_id) for key, biz_id in process_candidates.items()):
        process_filter |= Q(bk_tenant_id=tenant_id, bk_biz_id=bk_biz_id, plugin_type="Process")
    if process_filter:
        process_query = CollectorPluginMeta.origin_objects.filter(process_filter)
    plugins = list(plugin_query) + list(process_query)
    plugin_pairs = {(plugin.bk_tenant_id, plugin.plugin_id) for plugin in plugins}
    versions_by_plugin = _load_versions_by_plugin_key(plugin_pairs)
    config_counts = _collect_config_counts(plugin_pairs)
    serialized_plugins: dict[tuple[str | None, str], dict[str, Any]] = {}
    plugin_instances: dict[tuple[str | None, str], CollectorPluginMeta] = {}
    process_plugins: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    for plugin in plugins:
        plugin_key = (plugin.bk_tenant_id, plugin.plugin_id)
        current_version = _select_current_version(versions_by_plugin.get(plugin_key, []))
        item = _serialize_plugin_summary(plugin, current_version, config_counts.get(plugin_key, 0))
        item["is_deleted"] = bool(plugin.is_deleted)
        item["relation_kind"] = "normal"
        normalized_plugin_key = (plugin.bk_tenant_id, plugin.plugin_id.lower())
        serialized_plugins[normalized_plugin_key] = item
        plugin_instances[normalized_plugin_key] = plugin
        if plugin.plugin_type == "Process":
            process_item = dict(item)
            process_item["relation_kind"] = "shared_process"
            process_plugins[(plugin.bk_tenant_id, plugin.bk_biz_id)].append(process_item)

    result: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    datasource_map = {(item.bk_tenant_id, item.bk_data_id): item for item in datasources}
    for datasource_key, plugin_key in normal_candidates.items():
        plugin = serialized_plugins.get(plugin_key)
        plugin_instance = plugin_instances.get(plugin_key)
        datasource = datasource_map[datasource_key]
        if plugin and plugin_instance and _plugin_data_name(plugin_instance) == datasource.data_name.lower():
            result[datasource_key].append(plugin)
    for datasource_key, bk_biz_id in process_candidates.items():
        result[datasource_key].extend(process_plugins.get((datasource_key[0], bk_biz_id), []))
        if not result[datasource_key]:
            result[datasource_key].append(
                {
                    "bk_tenant_id": datasource_key[0],
                    "plugin_id": "process_shared",
                    "plugin_display_name": "进程采集共享 DataID",
                    "plugin_type": "Process",
                    "bk_biz_id": bk_biz_id,
                    "is_global": False,
                    "is_internal": True,
                    "is_deleted": False,
                    "status": "shared",
                    "related_conf_count": 0,
                    "relation_kind": "shared_process",
                }
            )
    return result


def _serialize_bcs_clusters(
    datasources: list[models.DataSource],
) -> dict[tuple[str | None, int], list[dict[str, Any]]]:
    datasource_pairs = {(item.bk_tenant_id, item.bk_data_id) for item in datasources}
    tenant_ids = {item.bk_tenant_id for item in datasources}
    data_ids = {item.bk_data_id for item in datasources}
    clusters = models.BCSClusterInfo.objects.filter(
        bk_tenant_id__in=tenant_ids,
    ).filter(Q(K8sMetricDataID__in=data_ids) | Q(CustomMetricDataID__in=data_ids))
    result: dict[tuple[str | None, int], list[dict[str, Any]]] = defaultdict(list)
    for cluster in clusters.order_by("bk_tenant_id", "cluster_id"):
        matched_fields = [
            field_name
            for field_name in BCS_METRIC_DATA_ID_FIELDS
            if (cluster.bk_tenant_id, getattr(cluster, field_name, 0)) in datasource_pairs
        ]
        item = serialize_model(cluster, BCS_CLUSTER_FIELDS)
        item["matched_fields"] = matched_fields
        for data_id in {getattr(cluster, field_name) for field_name in matched_fields}:
            result[(cluster.bk_tenant_id, data_id)].append(item)
    return result


def _serialize_kafka(datasources: list[models.DataSource]) -> dict[tuple[str | None, int], dict[str, Any]]:
    cluster_pairs = {
        (datasource.bk_tenant_id, datasource.mq_cluster_id)
        for datasource in datasources
        if datasource.mq_cluster_id not in (None, 0)
    }
    clusters = filter_by_tenant_resource_pairs(models.ClusterInfo.objects.all(), "cluster_id", cluster_pairs).filter(
        cluster_type=models.ClusterInfo.TYPE_KAFKA
    )
    cluster_map = {(cluster.bk_tenant_id, cluster.cluster_id): cluster for cluster in clusters}
    topic_map = {
        topic.bk_data_id: topic
        for topic in models.KafkaTopicInfo.objects.filter(
            bk_data_id__in=[datasource.bk_data_id for datasource in datasources]
        )
    }
    return {
        (datasource.bk_tenant_id, datasource.bk_data_id): {
            "cluster": (
                serialize_model(cluster_map[(datasource.bk_tenant_id, datasource.mq_cluster_id)], KAFKA_CLUSTER_FIELDS)
                if (datasource.bk_tenant_id, datasource.mq_cluster_id) in cluster_map
                else None
            ),
            "topic_config": (
                serialize_model(topic_map[datasource.bk_data_id], KAFKA_TOPIC_FIELDS)
                if datasource.bk_data_id in topic_map
                else None
            ),
        }
        for datasource in datasources
    }


def _build_warnings(
    datasource: models.DataSource,
    result_tables: list[dict[str, Any]],
    spaces: list[dict[str, Any]],
    plugins: list[dict[str, Any]],
    categories: list[str],
    kafka: dict[str, Any],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if not datasource.is_enable:
        warnings.append({"code": "DATASOURCE_DISABLED", "message": "DataSource 已停用"})
    if not result_tables:
        warnings.append({"code": "RESULT_TABLE_RELATION_MISSING", "message": "没有关联 ResultTable"})
    for result_table in result_tables:
        table_id = result_table["table_id"]
        if not result_table["record_exists"]:
            warnings.append({"code": "RESULT_TABLE_RECORD_MISSING", "message": f"ResultTable 不存在: {table_id}"})
        elif result_table["is_deleted"]:
            warnings.append({"code": "RESULT_TABLE_DELETED", "message": f"ResultTable 已删除: {table_id}"})
        elif result_table["is_enable"] is False:
            warnings.append({"code": "RESULT_TABLE_DISABLED", "message": f"ResultTable 已停用: {table_id}"})
    if datasource.mq_cluster_id and kafka.get("cluster") is None:
        warnings.append({"code": "KAFKA_CLUSTER_MISSING", "message": "Kafka 集群记录不存在"})
    if (datasource.space_uid and not spaces) or any(not item["record_exists"] for item in spaces):
        warnings.append({"code": "SPACE_RECORD_MISSING", "message": "DataSource 归属空间记录不存在"})
    for plugin in plugins:
        if plugin.get("is_deleted"):
            warnings.append(
                {
                    "code": "PLUGIN_DELETED",
                    "message": f"插件已删除: {plugin['plugin_type']}_{plugin['plugin_id']}",
                }
            )
    if categories == ["other_metric"]:
        warnings.append({"code": "UNCLASSIFIED_METRIC", "message": "未关联自定义指标、插件或 BCS 集群"})
    return warnings


def _build_items(datasources: list[models.DataSource]) -> list[dict[str, Any]]:
    result_table_map = _serialize_result_tables(datasources)
    space_map = _serialize_spaces(datasources)
    custom_group_map = _serialize_custom_groups(datasources)
    plugin_map = _serialize_plugins(datasources)
    bcs_map = _serialize_bcs_clusters(datasources)
    kafka_map = _serialize_kafka(datasources)
    items: list[dict[str, Any]] = []
    for datasource in datasources:
        key = (datasource.bk_tenant_id, datasource.bk_data_id)
        result_tables = result_table_map.get(key, [])
        spaces = space_map.get(key, [])
        custom_groups = custom_group_map.get(key, [])
        plugins = plugin_map.get(key, [])
        bcs_clusters = bcs_map.get(key, [])
        kafka = kafka_map.get(key, {"cluster": None, "topic_config": None})
        categories = [
            category
            for category, related_items in (
                ("custom_metric", custom_groups),
                ("plugin_metric", plugins),
                ("bcs_metric", bcs_clusters),
            )
            if related_items
        ] or ["other_metric"]
        biz_ids = {
            int(value)
            for value in (
                [item.get("bk_biz_id") for item in result_tables]
                + [item.get("bk_biz_id") for item in custom_groups]
                + [item.get("bk_biz_id") for item in plugins]
                + [item.get("bk_biz_id") for item in bcs_clusters]
                + [
                    int(item["space_id"])
                    for item in spaces
                    if item.get("space_type_id") == SpaceTypes.BKCC.value
                    and str(item.get("space_id", "")).lstrip("-").isdigit()
                ]
            )
            if value is not None
        }
        warnings = _build_warnings(datasource, result_tables, spaces, plugins, categories, kafka)
        items.append(
            {
                "datasource": serialize_model(datasource, DATASOURCE_FIELDS),
                "categories": categories,
                "result_tables": result_tables,
                "spaces": spaces,
                "biz_ids": sorted(biz_ids),
                "custom_metrics": custom_groups,
                "plugins": plugins,
                "bcs_clusters": bcs_clusters,
                "kafka": kafka,
                "warnings": warnings,
            }
        )
    return items


def _build_summary(queryset: Any, bk_tenant_id: str | None) -> dict[str, int]:
    aggregates = queryset.aggregate(
        total=Count("bk_data_id"),
        enabled=Count("bk_data_id", filter=Q(is_enable=True)),
        disabled=Count("bk_data_id", filter=Q(is_enable=False)),
        platform=Count("bk_data_id", filter=Q(is_platform_data_id=True)),
    )
    datasource_pairs = _pairs(queryset)
    relation_pairs = _pairs(
        filter_by_tenant_resource_pairs(models.DataSourceResultTable.objects.all(), "bk_data_id", datasource_pairs)
    )
    disabled_rt_pairs = _result_table_pairs(bk_tenant_id=bk_tenant_id, is_enable=False)
    deleted_rt_pairs = _result_table_pairs(bk_tenant_id=bk_tenant_id, is_deleted=True)
    return {
        "datasource_total": int(aggregates["total"] or 0),
        "datasource_enabled": int(aggregates["enabled"] or 0),
        "datasource_disabled": int(aggregates["disabled"] or 0),
        "platform_data_id": int(aggregates["platform"] or 0),
        "without_result_table": len(datasource_pairs - relation_pairs),
        "with_disabled_result_table": len(datasource_pairs & disabled_rt_pairs),
        "with_deleted_result_table": len(datasource_pairs & deleted_rt_pairs),
    }


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_METRIC_MIGRATION_LIST,
    summary="Admin 查询 V3/V4 指标迁移盘点列表",
    description=(
        "只读查询 created_from=bkgse 且 type_label=time_series 的 DataSource；"
        "先分页 DataSource，再批量加载 ResultTable、空间、自定义指标、插件、BCS 和 Kafka 配置。"
    ),
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_data_id / bk_data_ids": "可选，DataID 或 DataID 数组，最多 100 个",
        "data_name": "可选，DataSource 名称包含匹配",
        "etl_config / etl_configs": "可选，ETL 配置精确匹配",
        "source_label / source_labels": "可选，来源标签精确匹配",
        "is_enable": "可选，DataSource 启停状态",
        "is_platform_data_id": "可选，是否平台级 DataID",
        "mq_cluster_id / mq_cluster_ids": "可选，Kafka 集群 ID",
        "transfer_cluster_id / transfer_cluster_ids": "可选，Transfer 集群 ID",
        "table_id / table_ids": "可选，关联 ResultTable ID",
        "result_table_is_enable": "可选，关联 ResultTable 启停状态",
        "result_table_is_deleted": "可选，关联 ResultTable 删除状态",
        "bk_biz_id": "可选，按 RT、自定义指标、插件、BCS 或 BKCC 空间归属过滤",
        "space_uid": "可选，空间 UID 精确匹配",
        "plugin_id": "可选，插件 ID 包含匹配",
        "bcs_cluster_id": "可选，BCS 集群 ID 包含匹配",
        "scene_category / scene_categories": "可选，场景分类：custom_metric/plugin_metric/bcs_metric/other_metric",
        "pagination_mode": "page 或 cursor；默认 page",
        "page / page_size": "page 模式分页；page_size 最大 100",
        "cursor": "cursor 模式上一批最后一个 bk_data_id，首次传 0",
        "snapshot_max_bk_data_id": "cursor 模式首批返回的固定 DataID 上界",
        "include_summary": "可选，是否返回当前筛选集合摘要；cursor 模式默认 false",
    },
    example_params={
        "bk_tenant_id": "system",
        "scene_categories": ["custom_metric", "plugin_metric"],
        "page": 1,
        "page_size": 20,
    },
)
def list_metric_migration_datasources(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    queryset = _build_queryset(params, bk_tenant_id)
    pagination_mode = str(params.get("pagination_mode") or "page").strip()
    if pagination_mode not in {"page", "cursor"}:
        raise CustomException(message="pagination_mode 仅支持 page 或 cursor")
    page, page_size = normalize_pagination(params)
    include_summary = normalize_optional_bool(params.get("include_summary"), "include_summary")
    if include_summary is None:
        include_summary = pagination_mode == "page"

    next_cursor: int | None = None
    snapshot_max_bk_data_id: int | None = None
    has_more = False
    if pagination_mode == "cursor":
        cursor = _parse_optional_int(params.get("cursor"), "cursor", minimum=0) or 0
        snapshot_max_bk_data_id = _parse_optional_int(
            params.get("snapshot_max_bk_data_id"), "snapshot_max_bk_data_id", minimum=0
        )
        if snapshot_max_bk_data_id is None:
            snapshot_max_bk_data_id = int(queryset.aggregate(value=Max("bk_data_id"))["value"] or 0)
        snapshot_queryset = queryset.filter(
            bk_data_id__gt=cursor,
            bk_data_id__lte=snapshot_max_bk_data_id,
        ).order_by("bk_data_id")
        total = queryset.filter(bk_data_id__lte=snapshot_max_bk_data_id).count()
        batch = list(snapshot_queryset[: page_size + 1])
        has_more = len(batch) > page_size
        datasources = batch[:page_size]
        next_cursor = datasources[-1].bk_data_id if datasources else None
    else:
        ordered_queryset = queryset.order_by("-bk_data_id")
        total = ordered_queryset.count()
        offset = (page - 1) * page_size
        datasources = list(ordered_queryset[offset : offset + page_size])

    return build_response(
        operation="datasource.metric_migration_list",
        func_name=FUNC_DATASOURCE_METRIC_MIGRATION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": _build_items(datasources),
            "page": page,
            "page_size": page_size,
            "total": total,
            "pagination_mode": pagination_mode,
            "next_cursor": next_cursor,
            "snapshot_max_bk_data_id": snapshot_max_bk_data_id,
            "has_more": has_more,
            "summary": _build_summary(queryset, bk_tenant_id) if include_summary else None,
        },
    )
