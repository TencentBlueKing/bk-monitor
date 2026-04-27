"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import Any

from django.db.models import Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    count_by_field,
    get_bk_tenant_id,
    normalize_include,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_option,
    serialize_value,
)
from metadata import models

FUNC_ES_STORAGE_LIST = "admin.es_storage.list"
FUNC_ES_STORAGE_DETAIL = "admin.es_storage.detail"
FUNC_ES_STORAGE_RUNTIME_OVERVIEW = "admin.es_storage.runtime_overview"
FUNC_ES_STORAGE_SAMPLE = "admin.es_storage.sample"

TABLE_KIND_PHYSICAL = "physical"
TABLE_KIND_VIRTUAL = "virtual"
INSPECT_SAFETY_LEVEL = "inspect"

ES_STORAGE_LIST_FIELDS = [
    "id",
    "table_id",
    "origin_table_id",
    "bk_tenant_id",
    "storage_cluster_id",
    "date_format",
    "slice_size",
    "slice_gap",
    "retention",
    "warm_phase_days",
    "time_zone",
    "source_type",
    "index_set",
    "need_create_index",
    "archive_index_days",
    "create_time",
    "last_modify_time",
]
ES_STORAGE_DETAIL_FIELDS = [
    *ES_STORAGE_LIST_FIELDS,
    "index_settings",
    "mapping_settings",
    "warm_phase_settings",
    "long_term_storage_settings",
]
ES_STORAGE_JSON_FIELDS = {
    "index_settings",
    "mapping_settings",
    "warm_phase_settings",
    "long_term_storage_settings",
}
RESULT_TABLE_SUMMARY_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "bk_biz_id_alias",
    "data_label",
    "default_storage",
    "is_enable",
    "is_deleted",
]
CLUSTER_SUMMARY_FIELDS = ["cluster_id", "cluster_name", "display_name", "cluster_type"]
STORAGE_CLUSTER_RECORD_FIELDS = [
    "table_id",
    "cluster_id",
    "is_current",
    "is_deleted",
    "enable_time",
    "disable_time",
    "delete_time",
    "creator",
    "create_time",
]
RESULT_TABLE_OPTION_NAMES = {
    models.ResultTableOption.OPTION_ES_DOCUMENT_ID,
    models.ResultTableOption.OPTION_CUSTOM_REPORT_DIMENSION_VALUES,
    models.ResultTableOption.OPTION_SEGMENTED_QUERY_ENABLE,
}
ES_STORAGE_ORDERING_FIELDS = {
    "id",
    "table_id",
    "origin_table_id",
    "storage_cluster_id",
    "retention",
    "source_type",
    "create_time",
    "last_modify_time",
}
RUNTIME_INCLUDE_VALUES = {"indices", "aliases", "mapping"}
DEFAULT_RUNTIME_INCLUDE = {"indices", "aliases", "mapping"}


def _require_table_id(params: dict[str, Any]) -> str:
    table_id = str(params.get("table_id") or "").strip()
    if not table_id:
        raise CustomException(message="table_id 为必填项")
    return table_id


def _is_virtual_es_storage(es_storage: Any) -> bool:
    return getattr(es_storage, "origin_table_id", None) not in (None, "")


def _table_kind(es_storage: Any) -> str:
    return TABLE_KIND_VIRTUAL if _is_virtual_es_storage(es_storage) else TABLE_KIND_PHYSICAL


def _parse_json_value(value: Any, field: str, table_id: str, warnings: list[dict[str, Any]]) -> Any:
    if value in (None, "") or not isinstance(value, str):
        return serialize_value(value)
    try:
        return json.loads(value)
    except (TypeError, ValueError) as error:
        warnings.append(
            {
                "code": "ES_STORAGE_JSON_PARSE_FAILED",
                "message": f"{field} 不是合法 JSON，已返回原始值: table_id={table_id}",
                "details": {"field": field, "error": str(error)},
            }
        )
        return value


def _serialize_es_storage_config(es_storage: Any, warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    item = serialize_model(es_storage, ES_STORAGE_DETAIL_FIELDS)
    item["table_kind"] = _table_kind(es_storage)
    if warnings is not None:
        for field in ES_STORAGE_JSON_FIELDS:
            item[field] = _parse_json_value(item.get(field), field, item["table_id"], warnings)
    return item


def _serialize_es_storage_list_item(
    es_storage: Any,
    *,
    result_table_map: dict[str, Any],
    cluster_map: dict[int, Any],
    physical_table_exists: set[str],
    virtual_table_count_map: dict[str, int],
) -> dict[str, Any]:
    item = serialize_model(es_storage, ES_STORAGE_LIST_FIELDS)
    item["table_kind"] = _table_kind(es_storage)
    item["result_table"] = _serialize_result_table_summary(result_table_map.get(es_storage.table_id))
    item["storage_cluster"] = _serialize_cluster_summary(cluster_map.get(es_storage.storage_cluster_id))
    item["physical_table"] = None
    if item["table_kind"] == TABLE_KIND_VIRTUAL:
        item["physical_table"] = {
            "table_id": es_storage.origin_table_id,
            "exists": es_storage.origin_table_id in physical_table_exists,
        }
    item["virtual_table_count"] = (
        virtual_table_count_map.get(es_storage.table_id, 0) if item["table_kind"] == TABLE_KIND_PHYSICAL else 0
    )
    return item


def _serialize_result_table_summary(result_table: Any | None) -> dict[str, Any] | None:
    if result_table is None:
        return None
    return serialize_model(result_table, RESULT_TABLE_SUMMARY_FIELDS)


def _serialize_cluster_summary(cluster: Any | None) -> dict[str, Any] | None:
    if cluster is None:
        return None
    return serialize_model(cluster, CLUSTER_SUMMARY_FIELDS)


def _build_es_storage_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("table_id"):
        table_id = str(params["table_id"]).strip()
        queryset = queryset.filter(
            Q(table_id=table_id)
            | Q(table_id__startswith=table_id)
            | Q(table_id__contains=table_id)
            | Q(origin_table_id=table_id)
            | Q(origin_table_id__startswith=table_id)
            | Q(origin_table_id__contains=table_id)
        )

    if params.get("data_label") not in (None, ""):
        table_ids = models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, data_label=str(params["data_label"]).strip()
        ).values_list("table_id", flat=True)
        queryset = queryset.filter(table_id__in=table_ids)

    table_kind = str(params.get("table_kind") or "").strip()
    if table_kind == TABLE_KIND_PHYSICAL:
        queryset = queryset.filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
    elif table_kind == TABLE_KIND_VIRTUAL:
        queryset = queryset.exclude(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
    elif table_kind:
        raise CustomException(message="table_kind 仅支持 physical 或 virtual")

    if params.get("storage_cluster_id") not in (None, ""):
        try:
            storage_cluster_id = int(params["storage_cluster_id"])
        except (TypeError, ValueError) as error:
            raise CustomException(message="storage_cluster_id 必须是整数") from error
        queryset = queryset.filter(storage_cluster_id=storage_cluster_id)

    if params.get("source_type") not in (None, ""):
        queryset = queryset.filter(source_type=str(params["source_type"]).strip())

    need_create_index = normalize_optional_bool(params.get("need_create_index"), "need_create_index")
    if need_create_index is not None:
        queryset = queryset.filter(need_create_index=need_create_index)

    return queryset


def _load_result_table_map(bk_tenant_id: str, table_ids: list[str]) -> dict[str, Any]:
    if not table_ids:
        return {}
    return {
        result_table.table_id: result_table
        for result_table in models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    }


def _load_cluster_map(bk_tenant_id: str, cluster_ids: list[int]) -> dict[int, Any]:
    normalized_ids = [cluster_id for cluster_id in cluster_ids if cluster_id not in (None, "")]
    if not normalized_ids:
        return {}
    return {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=normalized_ids)
    }


def _get_es_storage_or_raise(bk_tenant_id: str, table_id: str):
    try:
        return models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except models.ESStorage.DoesNotExist as error:
        raise CustomException(message=f"未找到 ESStorage: table_id={table_id}") from error


def _serialize_storage_cluster_record(record: Any, cluster_map: dict[int, Any]) -> dict[str, Any]:
    item = serialize_model(record, STORAGE_CLUSTER_RECORD_FIELDS)
    item["cluster"] = _serialize_cluster_summary(cluster_map.get(record.cluster_id))
    return item


def _build_storage_cluster_records(es_storage: Any, bk_tenant_id: str) -> list[dict[str, Any]]:
    record_table_id = es_storage.origin_table_id if _is_virtual_es_storage(es_storage) else es_storage.table_id
    records = list(
        models.StorageClusterRecord.objects.filter(bk_tenant_id=bk_tenant_id, table_id=record_table_id).order_by(
            "-create_time"
        )
    )
    cluster_map = _load_cluster_map(bk_tenant_id, [record.cluster_id for record in records])
    return [_serialize_storage_cluster_record(record, cluster_map) for record in records]


def _build_physical_table(es_storage: Any, bk_tenant_id: str) -> dict[str, Any] | None:
    if not _is_virtual_es_storage(es_storage):
        return None
    physical_storage = models.ESStorage.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=es_storage.origin_table_id
    ).first()
    physical_rt = models.ResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=es_storage.origin_table_id
    ).first()
    return {
        "table_id": es_storage.origin_table_id,
        "exists": physical_storage is not None,
        "es_storage": _serialize_es_storage_config(physical_storage) if physical_storage else None,
        "result_table": _serialize_result_table_summary(physical_rt),
    }


def _build_virtual_tables(es_storage: Any, bk_tenant_id: str) -> list[dict[str, Any]]:
    if _is_virtual_es_storage(es_storage):
        return []
    virtual_storages = list(
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id=es_storage.table_id).order_by(
            "table_id"
        )
    )
    result_table_map = _load_result_table_map(bk_tenant_id, [storage.table_id for storage in virtual_storages])
    return [
        {
            "table_id": storage.table_id,
            "es_storage": _serialize_es_storage_config(storage),
            "result_table": _serialize_result_table_summary(result_table_map.get(storage.table_id)),
        }
        for storage in virtual_storages
    ]


def _build_result_table_options(table_id: str, bk_tenant_id: str) -> list[dict[str, Any]]:
    return [
        serialize_option(option)
        for option in models.ResultTableOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id, name__in=RESULT_TABLE_OPTION_NAMES
        ).order_by("name")
    ]


def _build_field_aliases(table_id: str, bk_tenant_id: str, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = list(
        models.ESFieldQueryAliasOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id, is_deleted=False
        ).order_by("query_alias")
    )
    try:
        alias_settings = models.ESFieldQueryAliasOption.generate_query_alias_settings(
            table_id=table_id, bk_tenant_id=bk_tenant_id
        )
    except Exception as error:  # pylint: disable=broad-except
        alias_settings = {}
        warnings.append(
            {
                "code": "QUERY_ALIAS_SETTINGS_UNAVAILABLE",
                "message": f"字段查询别名配置生成失败: table_id={table_id}",
                "details": {"error": str(error)},
            }
        )

    return {
        "items": [
            {
                "query_alias": alias.query_alias,
                "field_path": alias.field_path,
                "path_type": alias.path_type,
                "mapping_alias": alias_settings.get(alias.query_alias),
            }
            for alias in aliases
        ],
        "mapping_alias_settings": alias_settings,
    }


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _serialize_runtime_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize_runtime_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_runtime_value(item) for item in value]
    return serialize_value(value)


def _runtime_index_expression(es_storage: Any, index: str | None = None) -> str:
    return index or es_storage.search_format_v2()


def _append_runtime_warning(
    warnings: list[dict[str, Any]], code: str, message: str, error: Exception | None = None
) -> None:
    warning: dict[str, Any] = {"code": code, "message": message}
    if error is not None:
        warning["details"] = {"error": str(error)}
    warnings.append(warning)


def _run_runtime_query(
    *,
    name: str,
    es_storage: Any,
    bk_tenant_id: str,
    table_id: str,
    query,
    warnings: list[dict[str, Any]],
) -> Any:
    try:
        return query(es_storage)
    except Exception as error:  # pylint: disable=broad-except
        if _is_virtual_es_storage(es_storage):
            physical_storage = models.ESStorage.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id=es_storage.origin_table_id
            ).first()
            if physical_storage is not None:
                try:
                    result = query(physical_storage)
                    _append_runtime_warning(
                        warnings,
                        "RUNTIME_QUERY_FALLBACK_TO_PHYSICAL",
                        f"{name} 查询虚拟表失败，已回退实体表: table_id={table_id}, origin_table_id={es_storage.origin_table_id}",
                        error,
                    )
                    return result
                except Exception as fallback_error:  # pylint: disable=broad-except
                    _append_runtime_warning(
                        warnings,
                        "RUNTIME_QUERY_FAILED",
                        f"{name} 查询失败，虚拟表和实体表回退均不可用: table_id={table_id}",
                        fallback_error,
                    )
                    return None
        _append_runtime_warning(warnings, "RUNTIME_QUERY_FAILED", f"{name} 查询失败: table_id={table_id}", error)
        return None


def _build_indices_overview(es_storage: Any, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    index_exist: bool | None = None
    current_index_info: dict[str, Any] | None = None
    index_names = es_storage.get_index_names()
    stats_map, stats_version = es_storage.get_index_stats()

    try:
        index_exist = es_storage.index_exist()
    except Exception as error:  # pylint: disable=broad-except
        _append_runtime_warning(warnings, "INDEX_EXIST_UNAVAILABLE", "ES 索引存在性查询失败", error)

    try:
        current_index_info = es_storage.current_index_info()
    except Exception as error:  # pylint: disable=broad-except
        _append_runtime_warning(warnings, "CURRENT_INDEX_INFO_UNAVAILABLE", "ES 当前索引信息查询失败", error)

    return {
        "index_names": index_names,
        "index_stats": stats_map,
        "index_version": stats_version,
        "index_exist": index_exist,
        "current_index_info": _serialize_runtime_value(current_index_info),
        "items": [
            {
                "index": index_name,
                "stats": stats_map.get(index_name, {}),
            }
            for index_name in index_names
        ],
    }


def _build_aliases_overview(es_storage: Any, index: str | None = None) -> Any:
    client = es_storage.get_client()
    return client.indices.get_alias(index=_runtime_index_expression(es_storage, index))


def _build_mapping_overview(es_storage: Any, index: str | None = None) -> Any:
    client = es_storage.get_client()
    return client.indices.get_mapping(index=_runtime_index_expression(es_storage, index))


def _contains_index_wildcard(index: str) -> bool:
    return any(char in index for char in ["*", "?", "[", "]", "{", "}"])


def _is_index_allowed(es_storage: Any, index: str, warnings: list[dict[str, Any]]) -> bool:
    if _contains_index_wildcard(index):
        return False

    try:
        return index in set(es_storage.get_index_names())
    except Exception as error:  # pylint: disable=broad-except
        warnings.append(
            {
                "code": "INDEX_LIST_UNAVAILABLE",
                "message": f"索引列表获取失败，改用当前 ESStorage 索引规则校验: table_id={es_storage.table_id}",
                "details": {"error": str(error)},
            }
        )
        return es_storage.index_re_common.match(index) is not None


@KernelRPCRegistry.register(
    FUNC_ES_STORAGE_LIST,
    summary="Admin 查询 ESStorage 列表",
    description="只读查询 ESStorage，支持实体/虚拟表、ResultTable.data_label、集群和受控 table_id 匹配。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，同时匹配 ESStorage.table_id 和 origin_table_id，支持精确、前缀或受控包含匹配",
        "data_label": "可选，精确匹配 ResultTable.data_label 后按 table_id 查询 ESStorage",
        "table_kind": "可选，physical / virtual",
        "storage_cluster_id": "可选，ES 集群 ID",
        "source_type": "可选，数据源类型",
        "need_create_index": "可选，是否需要创建物理索引",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ES_STORAGE_ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "table_kind": "virtual", "page": 1, "page_size": 20},
)
def list_es_storages(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ES_STORAGE_ORDERING_FIELDS, default="table_id")

    queryset = _build_es_storage_queryset(params, bk_tenant_id).order_by(ordering, "table_id")
    es_storages, total = paginate_queryset(queryset, page=page, page_size=page_size)

    table_ids = [storage.table_id for storage in es_storages]
    cluster_ids = [storage.storage_cluster_id for storage in es_storages]
    origin_table_ids = [storage.origin_table_id for storage in es_storages if _is_virtual_es_storage(storage)]
    physical_table_ids = [storage.table_id for storage in es_storages if not _is_virtual_es_storage(storage)]

    result_table_map = _load_result_table_map(bk_tenant_id, table_ids)
    cluster_map = _load_cluster_map(bk_tenant_id, cluster_ids)
    physical_table_exists = set(
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=origin_table_ids).values_list(
            "table_id", flat=True
        )
    )
    virtual_table_count_map = count_by_field(
        models.ESStorage, group_field="origin_table_id", values=physical_table_ids, bk_tenant_id=bk_tenant_id
    )

    items = [
        _serialize_es_storage_list_item(
            storage,
            result_table_map=result_table_map,
            cluster_map=cluster_map,
            physical_table_exists=physical_table_exists,
            virtual_table_count_map=virtual_table_count_map,
        )
        for storage in es_storages
    ]

    return build_response(
        operation="es_storage.list",
        func_name=FUNC_ES_STORAGE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_ES_STORAGE_DETAIL,
    summary="Admin 查询 ESStorage 详情",
    description="只读查询 ESStorage 静态配置、ResultTable、ClusterInfo、实体/虚拟关系、迁移记录和字段别名。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，ESStorage.table_id",
        "include": "可选，当前支持 relations；保留用于后续扩展",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "include": ["relations"]},
)
def get_es_storage_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    normalize_include(params.get("include"), {"relations"})
    es_storage = _get_es_storage_or_raise(bk_tenant_id, table_id)

    warnings: list[dict[str, Any]] = []
    result_table = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
    cluster = models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id, cluster_id=es_storage.storage_cluster_id
    ).first()

    data = {
        "es_storage": _serialize_es_storage_config(es_storage, warnings),
        "result_table": _serialize_result_table_summary(result_table),
        "storage_cluster": _serialize_cluster_summary(cluster),
        "physical_table": _build_physical_table(es_storage, bk_tenant_id),
        "virtual_tables": _build_virtual_tables(es_storage, bk_tenant_id),
        "storage_cluster_records": _build_storage_cluster_records(es_storage, bk_tenant_id),
        "result_table_options": _build_result_table_options(table_id, bk_tenant_id),
        "field_aliases": _build_field_aliases(table_id, bk_tenant_id, warnings),
    }

    return build_response(
        operation="es_storage.detail",
        func_name=FUNC_ES_STORAGE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_ES_STORAGE_RUNTIME_OVERVIEW,
    summary="Admin 查询 ESStorage 运行时 ES 概览",
    description="inspect 级别能力，访问目标 ES 集群读取索引、别名和 mapping；单类查询失败不影响整体返回。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，ESStorage.table_id",
        "include": f"可选，展开范围: {', '.join(sorted(RUNTIME_INCLUDE_VALUES))}",
        "index": "可选，指定索引；不传时使用 ESStorage 现有 search_format_v2 规则",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "include": ["indices", "mapping"]},
)
def get_es_storage_runtime_overview(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    includes = normalize_include(params.get("include"), RUNTIME_INCLUDE_VALUES, default=DEFAULT_RUNTIME_INCLUDE)
    index = str(params["index"]).strip() if params.get("index") not in (None, "") else None
    es_storage = _get_es_storage_or_raise(bk_tenant_id, table_id)

    warnings: list[dict[str, Any]] = []
    data: dict[str, Any] = {
        "table_id": table_id,
        "origin_table_id": es_storage.origin_table_id,
        "table_kind": _table_kind(es_storage),
        "index_set": es_storage.index_set,
        "index_pattern": {
            "v2": es_storage.search_format_v2(),
            "v1": es_storage.search_format_v1(),
            "effective": _runtime_index_expression(es_storage, index),
        },
        "inspect": True,
    }

    if "indices" in includes:
        data["indices"] = _run_runtime_query(
            name="indices",
            es_storage=es_storage,
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            query=lambda storage: _build_indices_overview(storage, warnings),
            warnings=warnings,
        )
    if "aliases" in includes:
        data["aliases"] = _run_runtime_query(
            name="aliases",
            es_storage=es_storage,
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            query=lambda storage: _build_aliases_overview(storage, index),
            warnings=warnings,
        )
    if "mapping" in includes:
        data["mapping"] = _run_runtime_query(
            name="mapping",
            es_storage=es_storage,
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            query=lambda storage: _build_mapping_overview(storage, index),
            warnings=warnings,
        )
        data["field_aliases"] = _build_field_aliases(table_id, bk_tenant_id, warnings)

    response = build_response(
        operation="es_storage.runtime_overview",
        func_name=FUNC_ES_STORAGE_RUNTIME_OVERVIEW,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_ES_STORAGE_SAMPLE,
    summary="Admin 查询 ESStorage 最新样例数据",
    description="inspect 级别能力，校验索引属于当前 ESStorage 后调用 get_raw_data 获取最新一条数据。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，ESStorage.table_id",
        "index": "必填，指定查询索引，不允许通配符，必须属于当前 ESStorage 索引集合或规则",
        "time_field": "可选，默认 dtEventTimeStamp",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "index": "v2_system_cpu_20260425_0"},
)
def get_es_storage_sample(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    index = str(params.get("index") or "").strip()
    if not index:
        raise CustomException(message="index 为必填项")
    time_field = str(params.get("time_field") or "dtEventTimeStamp").strip() or "dtEventTimeStamp"
    es_storage = _get_es_storage_or_raise(bk_tenant_id, table_id)

    warnings: list[dict[str, Any]] = []
    sample_storage = es_storage
    is_allowed = _is_index_allowed(sample_storage, index, warnings)
    if not is_allowed and _is_virtual_es_storage(es_storage):
        physical_storage = models.ESStorage.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=es_storage.origin_table_id
        ).first()
        if physical_storage is not None and _is_index_allowed(physical_storage, index, warnings):
            sample_storage = physical_storage
            is_allowed = True
            _append_runtime_warning(
                warnings,
                "SAMPLE_FALLBACK_TO_PHYSICAL",
                f"虚拟表索引校验失败，已回退实体表: table_id={table_id}, origin_table_id={es_storage.origin_table_id}",
            )

    if not is_allowed:
        raise CustomException(message=f"index 不属于当前 ESStorage 的索引集合或规则: {index}")

    try:
        raw_data = sample_storage.get_raw_data(index_name=index, time_field=time_field)
    except Exception as error:  # pylint: disable=broad-except
        raise CustomException(message=f"查询 ES 最新样例数据失败: {error}") from error

    hits = raw_data.get("hits", {}).get("hits", []) if isinstance(raw_data, dict) else []
    data = {
        "table_id": table_id,
        "origin_table_id": es_storage.origin_table_id,
        "table_kind": _table_kind(es_storage),
        "index": index,
        "time_field": time_field,
        "took": raw_data.get("took") if isinstance(raw_data, dict) else None,
        "hit": hits[0] if hits else None,
        "raw": raw_data,
        "inspect": True,
    }
    response = build_response(
        operation="es_storage.sample",
        func_name=FUNC_ES_STORAGE_SAMPLE,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
    return _mark_inspect_response(response)
