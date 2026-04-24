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
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from django.conf import settings
from django.db.models import Q

from bkmonitor.utils.request import get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
    SpaceTypes,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import reformat_table_id
from metadata.utils.redis_tools import RedisTools


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def _values(queryset, fields: list[str], order_by: list[str]) -> list[dict[str, Any]]:
    return [
        {key: _serialize_value(value) for key, value in item.items()}
        for item in queryset.order_by(*order_by).values(*fields)
    ]


def _build_space_datasource_map(bk_tenant_id: str, bk_data_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not bk_data_ids:
        return {}

    space_datasource_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    queryset = models.SpaceDataSource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        bk_data_id__in=bk_data_ids,
    ).order_by("bk_data_id", "space_type_id", "space_id")

    for item in queryset.values("bk_data_id", "bk_tenant_id", "space_type_id", "space_id", "from_authorization"):
        serialized_item = {key: _serialize_value(value) for key, value in item.items()}
        serialized_item["space_uid"] = f"{item['space_type_id']}__{item['space_id']}"
        space_datasource_map[item["bk_data_id"]].append(serialized_item)

    return space_datasource_map


def _get_bk_tenant_id(params: dict[str, Any]) -> str:
    return params.get("bk_tenant_id") or get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID


def _normalize_bk_data_id(bk_data_id: Any) -> int:
    if isinstance(bk_data_id, int):
        return bk_data_id
    if isinstance(bk_data_id, str) and bk_data_id.isdigit():
        return int(bk_data_id)
    raise CustomException(message="bk_data_id 必须是整数或整数字符串")


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []

    raw_values: list[Any]
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = list(value)
    else:
        raise CustomException(message=f"{field_name} 必须是字符串、列表、元组或集合")

    normalized_values: list[str] = []
    for item in raw_values:
        if item is None:
            continue
        if not isinstance(item, str):
            item = str(item)
        normalized_values.extend([part.strip() for part in item.split(",") if part and part.strip()])

    return sorted(set(normalized_values))


def _normalize_bk_biz_id(bk_biz_id: Any) -> int:
    if bk_biz_id is None or bk_biz_id == "":
        raise CustomException(message="bk_biz_id 不能为空")
    if isinstance(bk_biz_id, int):
        return bk_biz_id
    if isinstance(bk_biz_id, str) and bk_biz_id.lstrip("-").isdigit():
        return int(bk_biz_id)
    raise CustomException(message="bk_biz_id 必须是整数或整数字符串")


def _extract_route_field_names(route_detail: dict[str, Any] | None) -> set[str]:
    if not route_detail:
        return set()

    route_fields = route_detail.get("fields") or []
    extracted_field_names: set[str] = set()
    for field in route_fields:
        if isinstance(field, str):
            if field:
                extracted_field_names.add(field)
            continue
        if isinstance(field, dict):
            field_name = field.get("field_name") or field.get("name")
            if field_name:
                extracted_field_names.add(str(field_name))
    return extracted_field_names


def _decode_redis_json(value: Any) -> Any:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def _build_data_label_route_key(data_label: str, bk_tenant_id: str) -> str:
    return f"{data_label}|{bk_tenant_id}" if settings.ENABLE_MULTI_TENANT_MODE else data_label


def _build_result_table_detail_key(table_id: str, bk_tenant_id: str) -> str:
    normalized_table_id = reformat_table_id(table_id)
    return f"{normalized_table_id}|{bk_tenant_id}" if settings.ENABLE_MULTI_TENANT_MODE else normalized_table_id


def _build_space_route_key(bk_biz_id: int, bk_tenant_id: str) -> str:
    base_key = f"{SpaceTypes.BKCC.value}__{bk_biz_id}"
    return f"{base_key}|{bk_tenant_id}" if settings.ENABLE_MULTI_TENANT_MODE else base_key


def _normalize_space_route_data(space_route_data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for table_id, route_config in (space_route_data or {}).items():
        normalized[reformat_table_id(table_id.split("|")[0])] = route_config
    return normalized


def _query_result_tables_by_inputs(
    bk_tenant_id: str, table_ids: list[str] | None = None, data_labels: list[str] | None = None
) -> list[dict[str, Any]]:
    query_filter = Q(bk_tenant_id=bk_tenant_id)

    input_filter = Q()
    normalized_table_ids = [reformat_table_id(table_id) for table_id in (table_ids or []) if table_id]
    if normalized_table_ids:
        input_filter |= Q(table_id__in=normalized_table_ids)

    normalized_data_labels = [data_label for data_label in (data_labels or []) if data_label]
    if normalized_data_labels:
        data_label_query = Q(data_label__contains=normalized_data_labels[0])
        for data_label in normalized_data_labels[1:]:
            data_label_query |= Q(data_label__contains=data_label)
        input_filter |= data_label_query

    if not input_filter:
        return []

    queryset = models.ResultTable.objects.filter(query_filter & input_filter).values(
        "table_id", "bk_biz_id", "data_label", "bk_tenant_id"
    )
    return list(queryset)


def _expand_es_related_table_ids(table_ids: set[str], bk_tenant_id: str) -> tuple[set[str], list[models.ESStorage]]:
    if not table_ids:
        return set(), []

    related_table_ids = {table_id for table_id in table_ids if table_id}
    all_es_storages: dict[tuple[str, str], models.ESStorage] = {}

    es_by_table = list(models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=related_table_ids))
    for es_storage in es_by_table:
        all_es_storages[(es_storage.table_id, es_storage.bk_tenant_id)] = es_storage
        related_table_ids.add(es_storage.table_id)
        if es_storage.origin_table_id:
            related_table_ids.add(es_storage.origin_table_id)

    es_by_origin = list(
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id__in=related_table_ids)
    )
    for es_storage in es_by_origin:
        all_es_storages[(es_storage.table_id, es_storage.bk_tenant_id)] = es_storage
        related_table_ids.add(es_storage.table_id)
        if es_storage.origin_table_id:
            related_table_ids.add(es_storage.origin_table_id)

    return related_table_ids, sorted(
        all_es_storages.values(), key=lambda item: (item.origin_table_id or "", item.table_id)
    )


@KernelRPCRegistry.register(
    "metadata_related_info",
    summary="查询元数据关联信息",
    description=(
        "基于 bk_data_id 或 table_id 查询关联的 datasource/result_table/time_series_group/event_group/"
        "log_group/esstorage/accessvmrecord 等信息。若 ESStorage 配置了 origin_table_id，"
        "会自动展开关联的索引集虚拟表。"
    ),
    params_schema={
        "bk_data_id": "可选，数据源 ID，与 table_id 至少提供一个",
        "table_id": "可选，结果表 ID，与 bk_data_id 至少提供一个",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退到默认租户",
    },
    example_params={"bk_data_id": 50010},
)
def get_metadata_related_info(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    bk_data_id = params.get("bk_data_id")
    table_id = params.get("table_id")

    if bk_data_id is None and not table_id:
        raise CustomException(message="bk_data_id 和 table_id 至少需要提供一个")

    related_bk_data_ids: set[int] = set()
    if bk_data_id is not None:
        related_bk_data_ids.add(_normalize_bk_data_id(bk_data_id))

    seed_table_ids = {table_id} if table_id else set()
    if related_bk_data_ids:
        seed_table_ids.update(
            models.DataSourceResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id__in=related_bk_data_ids
            ).values_list("table_id", flat=True)
        )

    related_table_ids, es_storages = _expand_es_related_table_ids(seed_table_ids, bk_tenant_id)

    inferred_dsrts = models.DataSourceResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id__in=related_table_ids
    )
    related_bk_data_ids.update(inferred_dsrts.values_list("bk_data_id", flat=True))

    if related_bk_data_ids:
        dsrt_queryset = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id).filter(
            Q(bk_data_id__in=related_bk_data_ids) | Q(table_id__in=related_table_ids)
        )
    else:
        dsrt_queryset = inferred_dsrts

    related_table_ids.update(dsrt_queryset.values_list("table_id", flat=True))
    related_table_ids, es_storages = _expand_es_related_table_ids(related_table_ids, bk_tenant_id)
    related_bk_data_ids.update(
        models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=related_table_ids
        ).values_list("bk_data_id", flat=True)
    )
    dsrt_queryset = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id).filter(
        Q(bk_data_id__in=related_bk_data_ids) | Q(table_id__in=related_table_ids)
    )

    datasource_queryset = models.DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_data_id__in=related_bk_data_ids
    )
    space_datasource_map = _build_space_datasource_map(bk_tenant_id, sorted(related_bk_data_ids))
    result_table_queryset = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=related_table_ids)
    time_series_group_queryset = models.TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id).filter(
        Q(bk_data_id__in=related_bk_data_ids) | Q(table_id__in=related_table_ids)
    )
    event_group_queryset = models.EventGroup.objects.filter(bk_tenant_id=bk_tenant_id).filter(
        Q(bk_data_id__in=related_bk_data_ids) | Q(table_id__in=related_table_ids)
    )
    log_group_queryset = models.LogGroup.objects.filter(bk_tenant_id=bk_tenant_id).filter(
        Q(bk_data_id__in=related_bk_data_ids) | Q(table_id__in=related_table_ids)
    )
    access_vm_record_queryset = models.AccessVMRecord.objects.filter(
        bk_tenant_id=bk_tenant_id, result_table_id__in=related_table_ids
    )
    result_table_data_label_map = dict(result_table_queryset.values_list("table_id", "data_label"))
    time_series_group_items = _values(
        time_series_group_queryset,
        [
            "time_series_group_id",
            "time_series_group_name",
            "bk_data_id",
            "bk_biz_id",
            "bk_tenant_id",
            "table_id",
            "label",
            "is_enable",
            "is_split_measurement",
        ],
        ["time_series_group_id"],
    )
    for item in time_series_group_items:
        item["data_label"] = _serialize_value(result_table_data_label_map.get(item["table_id"]) or "")
    event_group_items = _values(
        event_group_queryset,
        [
            "event_group_id",
            "event_group_name",
            "bk_data_id",
            "bk_biz_id",
            "bk_tenant_id",
            "table_id",
            "label",
            "is_enable",
            "status",
        ],
        ["event_group_id"],
    )
    for item in event_group_items:
        item["data_label"] = _serialize_value(result_table_data_label_map.get(item["table_id"]) or "")

    es_storage_items = [
        {
            "table_id": es_storage.table_id,
            "origin_table_id": es_storage.origin_table_id,
            "bk_tenant_id": es_storage.bk_tenant_id,
            "storage_cluster_id": es_storage.storage_cluster_id,
            "source_type": es_storage.source_type,
            "index_set": es_storage.index_set,
            "need_create_index": es_storage.need_create_index,
            "retention": es_storage.retention,
            "date_format": es_storage.date_format,
            "slice_gap": es_storage.slice_gap,
            "slice_size": es_storage.slice_size,
            "time_zone": es_storage.time_zone,
        }
        for es_storage in es_storages
    ]

    virtual_result_table_relations = [
        {
            "origin_table_id": es_storage.origin_table_id,
            "virtual_table_id": es_storage.table_id,
            "index_set": es_storage.index_set,
        }
        for es_storage in es_storages
        if es_storage.origin_table_id
    ]

    return {
        "query": {
            "bk_tenant_id": bk_tenant_id,
            "bk_data_id": _normalize_bk_data_id(bk_data_id) if bk_data_id is not None else None,
            "table_id": table_id,
        },
        "resolved": {
            "bk_data_ids": sorted(related_bk_data_ids),
            "table_ids": sorted(related_table_ids),
        },
        "datasources": [
            {
                **item,
                "space_datasources": space_datasource_map.get(item["bk_data_id"], []),
            }
            for item in _values(
                datasource_queryset,
                [
                    "bk_data_id",
                    "bk_tenant_id",
                    "data_name",
                    "etl_config",
                    "source_label",
                    "type_label",
                    "source_system",
                    "is_enable",
                    "is_platform_data_id",
                    "space_type_id",
                    "space_uid",
                    "created_from",
                    "transfer_cluster_id",
                ],
                ["bk_data_id"],
            )
        ],
        "data_source_result_tables": _values(
            dsrt_queryset,
            ["bk_data_id", "table_id", "bk_tenant_id", "creator", "create_time"],
            ["bk_data_id", "table_id"],
        ),
        "result_tables": _values(
            result_table_queryset,
            [
                "table_id",
                "bk_tenant_id",
                "table_name_zh",
                "default_storage",
                "schema_type",
                "bk_biz_id",
                "is_enable",
                "is_deleted",
                "label",
                "data_label",
                "labels",
                "is_custom_table",
            ],
            ["table_id"],
        ),
        "time_series_groups": time_series_group_items,
        "event_groups": event_group_items,
        "log_groups": _values(
            log_group_queryset,
            [
                "log_group_id",
                "log_group_name",
                "bk_data_id",
                "bk_biz_id",
                "bk_tenant_id",
                "table_id",
                "label",
                "is_enable",
            ],
            ["log_group_id"],
        ),
        "es_storages": es_storage_items,
        "access_vm_records": _values(
            access_vm_record_queryset,
            [
                "result_table_id",
                "bk_tenant_id",
                "data_type",
                "bcs_cluster_id",
                "storage_cluster_id",
                "vm_cluster_id",
                "bk_base_data_id",
                "bk_base_data_name",
                "vm_result_table_id",
                "remark",
            ],
            ["result_table_id", "vm_result_table_id"],
        ),
        "virtual_result_table_relations": virtual_result_table_relations,
    }


@KernelRPCRegistry.register(
    "metadata_kafka_has_data",
    summary="查询数据源 Kafka 是否有数据",
    description="基于租户和 bk_data_id，复用 KafkaTailResource 探测 Kafka 是否存在消息。",
    params_schema={
        "bk_tenant_id": "必填，租户 ID",
        "bk_data_id": "必填，数据源 ID",
        "namespace": "可选，计算平台命名空间，默认 bkmonitor",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010},
)
def metadata_kafka_has_data(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = params.get("bk_tenant_id")
    bk_data_id = params.get("bk_data_id")
    namespace = params.get("namespace", "bkmonitor")

    if not bk_tenant_id:
        raise CustomException(message="bk_tenant_id 为必填项")
    if bk_data_id is None:
        raise CustomException(message="bk_data_id 为必填项")

    normalized_bk_data_id = _normalize_bk_data_id(bk_data_id)

    from metadata.resources.resources import KafkaTailResource

    sample_data = KafkaTailResource().request(
        {
            "bk_tenant_id": bk_tenant_id,
            "bk_data_id": normalized_bk_data_id,
            "size": 1,
            "namespace": namespace,
        }
    )

    return {
        "bk_tenant_id": bk_tenant_id,
        "bk_data_id": normalized_bk_data_id,
        "namespace": namespace,
        "has_data": bool(sample_data),
        "sample_count": len(sample_data),
        "sample_data": sample_data[:1],
    }


@KernelRPCRegistry.register(
    "unify_query_redis_route",
    summary="查询 unify-query Redis 路由状态",
    description=(
        "支持基于 table_ids/data_label/bk_biz_id/bk_tenant_id 查询 unify-query 的 data_label 路由、"
        "结果表详情路由和空间路由状态。支持传入 field_names 检查字段是否存在于 rt_detail 路由中。"
        "会通过 ResultTable 自动补全 table_ids 与 data_label，并按单租户/多租户模式使用不同的 Redis key 规则进行校验。"
    ),
    params_schema={
        "table_ids": "可选，结果表 ID 列表，也支持逗号分隔字符串",
        "data_label": "可选，数据标签，也支持列表或逗号分隔字符串",
        "field_names": "可选，字段/指标名列表，也支持逗号分隔字符串",
        "bk_biz_id": "可选，业务 ID；传入后会进一步检查 bkcc 空间路由",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户",
    },
    example_params={"table_ids": ["1001_system.cpu"], "bk_biz_id": 2},
)
def query_unify_query_redis_route(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    input_table_ids = _normalize_string_list(params.get("table_ids"), "table_ids")
    input_data_labels = _normalize_string_list(params.get("data_label"), "data_label")
    input_field_names = _normalize_string_list(params.get("field_names"), "field_names")
    raw_bk_biz_id = params.get("bk_biz_id")
    bk_biz_id = _normalize_bk_biz_id(raw_bk_biz_id) if raw_bk_biz_id not in (None, "") else None

    if not input_table_ids and not input_data_labels:
        raise CustomException(message="table_ids 和 data_label 至少需要提供一个")

    result_table_filter = Q()
    if input_table_ids:
        result_table_filter |= Q(table_id__in=input_table_ids) | Q(
            table_id__in=[reformat_table_id(table_id) for table_id in input_table_ids]
        )
    if input_data_labels:
        data_label_query = Q(data_label__contains=input_data_labels[0])
        for data_label in input_data_labels[1:]:
            data_label_query |= Q(data_label__contains=data_label)
        result_table_filter |= data_label_query

    result_table_queryset = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id).filter(result_table_filter)

    result_tables = list(
        result_table_queryset.values(
            "table_id",
            "bk_tenant_id",
            "table_name_zh",
            "bk_biz_id",
            "data_label",
            "default_storage",
            "is_enable",
            "is_deleted",
        )
    )

    table_id_to_result_table: dict[str, dict[str, Any]] = {}
    resolved_table_ids: set[str] = set(input_table_ids)
    resolved_data_labels: set[str] = set(input_data_labels)

    for result_table in result_tables:
        normalized_table_id = reformat_table_id(result_table["table_id"])
        result_table["normalized_table_id"] = normalized_table_id
        labels = [item.strip() for item in (result_table.get("data_label") or "").split(",") if item.strip()]
        result_table["data_label_list"] = labels
        table_id_to_result_table[normalized_table_id] = result_table
        resolved_table_ids.add(normalized_table_id)
        resolved_data_labels.update(labels)

    normalized_table_ids = sorted({reformat_table_id(table_id) for table_id in resolved_table_ids})
    normalized_data_labels = sorted(resolved_data_labels)
    checked_table_ids = normalized_table_ids

    data_label_route_items: list[dict[str, Any]] = []
    data_label_route_map: dict[str, set[str]] = {}
    for data_label in normalized_data_labels:
        redis_key = _build_data_label_route_key(data_label, bk_tenant_id)
        raw_route_table_ids = RedisTools.hget(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_key)
        route_table_ids = _decode_redis_json(raw_route_table_ids) or []
        route_table_ids = {reformat_table_id(table_id) for table_id in route_table_ids}
        data_label_route_map[data_label] = route_table_ids
        expected_table_ids = {
            reformat_table_id(result_table["table_id"])
            for result_table in result_tables
            if data_label in result_table.get("data_label_list", [])
        }
        checked_data_label_table_ids = expected_table_ids
        checked_existing_table_ids = sorted(checked_data_label_table_ids & route_table_ids)
        checked_missing_table_ids = sorted(checked_data_label_table_ids - route_table_ids)
        data_label_route_items.append(
            {
                "data_label": data_label,
                "redis_key": redis_key,
                "exists": raw_route_table_ids is not None,
                "stats": {
                    "route_table_count": len(route_table_ids),
                    "expected_table_count": len(expected_table_ids),
                    "missing_table_count": len(expected_table_ids - route_table_ids),
                    "extra_table_count": len(route_table_ids - expected_table_ids),
                    "checked_table_count": len(checked_data_label_table_ids),
                    "checked_existing_table_count": len(checked_existing_table_ids),
                    "checked_missing_table_count": len(checked_missing_table_ids),
                },
                "checked_table_ids": {
                    "existing": checked_existing_table_ids,
                    "missing": checked_missing_table_ids,
                },
            }
        )

    result_table_route_items: list[dict[str, Any]] = []
    for table_id in checked_table_ids:
        redis_key = _build_result_table_detail_key(table_id, bk_tenant_id)
        raw_route_detail = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, redis_key)
        route_detail = _decode_redis_json(raw_route_detail)
        route_field_names = _extract_route_field_names(route_detail)
        existing_field_names = sorted(set(input_field_names) & route_field_names)
        missing_field_names = sorted(set(input_field_names) - route_field_names)
        result_table_meta = table_id_to_result_table.get(table_id)
        matched_data_labels = sorted(
            [data_label for data_label, route_table_ids in data_label_route_map.items() if table_id in route_table_ids]
        )
        result_table_route_items.append(
            {
                "table_id": table_id,
                "redis_key": redis_key,
                "exists": raw_route_detail is not None,
                "matched_data_labels": matched_data_labels,
                "result_table": result_table_meta,
                "stats": {
                    "route_field_count": len(route_field_names),
                    "checked_field_count": len(input_field_names),
                    "existing_field_count": len(existing_field_names),
                    "missing_field_count": len(missing_field_names),
                },
                "checked_field_names": {
                    "existing": existing_field_names,
                    "missing": missing_field_names,
                },
            }
        )

    space_route = None
    if bk_biz_id is not None:
        space_route_key = _build_space_route_key(bk_biz_id, bk_tenant_id)
        raw_space_route_value = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, space_route_key)
        raw_space_route_data = _decode_redis_json(raw_space_route_value) or {}
        normalized_space_route_data = _normalize_space_route_data(raw_space_route_data)
        space_route = {
            "space_type": SpaceTypes.BKCC.value,
            "space_id": str(bk_biz_id),
            "redis_key": space_route_key,
            "exists": raw_space_route_value is not None,
            "stats": {
                "route_table_count": len(normalized_space_route_data),
                "checked_table_count": len(checked_table_ids),
                "existing_table_count": len(
                    [table_id for table_id in checked_table_ids if table_id in normalized_space_route_data]
                ),
                "missing_table_count": len(
                    [table_id for table_id in checked_table_ids if table_id not in normalized_space_route_data]
                ),
                "filtered_table_count": len(
                    [
                        table_id
                        for table_id in checked_table_ids
                        if (normalized_space_route_data.get(table_id) or {}).get("filters")
                    ]
                ),
            },
            "table_checks": [
                {
                    "table_id": table_id,
                    "exists": table_id in normalized_space_route_data,
                    "has_filters": bool((normalized_space_route_data.get(table_id) or {}).get("filters")),
                    "filter_count": len((normalized_space_route_data.get(table_id) or {}).get("filters") or []),
                }
                for table_id in checked_table_ids
            ],
        }

    return {
        "query": {
            "table_ids": input_table_ids,
            "data_label": input_data_labels,
            "field_names": input_field_names,
            "bk_biz_id": bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
            "multi_tenant_mode": settings.ENABLE_MULTI_TENANT_MODE,
        },
        "resolved": {
            "table_ids": normalized_table_ids,
            "data_labels": normalized_data_labels,
        },
        "result_tables": result_tables,
        "data_label_routes": data_label_route_items,
        "result_table_routes": result_table_route_items,
        "space_route": space_route,
    }


@KernelRPCRegistry.register(
    "refresh_unify_query_redis_route",
    summary="主动刷新 unify-query Redis 路由",
    description=(
        "支持基于 table_ids、data_labels、bk_biz_ids 主动刷新 unify-query 的结果表详情路由、"
        "data_label 路由以及 bkcc 业务空间路由。会自动补全相关的 table_id/data_label/bk_biz_id 后统一刷新。"
    ),
    params_schema={
        "table_ids": "可选，结果表 ID 列表，也支持逗号分隔字符串",
        "data_labels": "可选，数据标签列表，也支持逗号分隔字符串",
        "bk_biz_ids": "可选，业务 ID 列表，也支持逗号分隔字符串",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户",
    },
    example_params={"table_ids": ["2_system.cpu"], "bk_biz_ids": [2]},
)
def refresh_unify_query_redis_route(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    input_table_ids = _normalize_string_list(params.get("table_ids"), "table_ids")
    input_data_labels = _normalize_string_list(params.get("data_labels"), "data_labels")
    raw_bk_biz_ids = _normalize_string_list(params.get("bk_biz_ids"), "bk_biz_ids")
    input_bk_biz_ids = sorted({_normalize_bk_biz_id(bk_biz_id) for bk_biz_id in raw_bk_biz_ids})

    if not input_table_ids and not input_data_labels and not input_bk_biz_ids:
        raise CustomException(message="table_ids、data_labels、bk_biz_ids 至少需要提供一个")

    related_result_tables = _query_result_tables_by_inputs(
        bk_tenant_id=bk_tenant_id,
        table_ids=input_table_ids,
        data_labels=input_data_labels,
    )

    resolved_table_ids = sorted(
        {
            reformat_table_id(table_id)
            for table_id in input_table_ids + [result_table["table_id"] for result_table in related_result_tables]
            if table_id
        }
    )
    resolved_data_labels = sorted(
        {
            data_label
            for data_label in input_data_labels
            + [
                label.strip()
                for result_table in related_result_tables
                for label in (result_table.get("data_label") or "").split(",")
                if label.strip()
            ]
            if data_label
        }
    )
    resolved_bk_biz_ids = sorted(
        {
            *input_bk_biz_ids,
            *[
                result_table["bk_biz_id"]
                for result_table in related_result_tables
                if result_table.get("bk_biz_id") is not None
            ],
        }
    )

    space_client = SpaceTableIDRedis()

    if resolved_table_ids:
        space_client.push_table_id_detail(
            table_id_list=resolved_table_ids,
            is_publish=True,
            include_es_table_ids=True,
            bk_tenant_id=bk_tenant_id,
        )

    if resolved_table_ids or resolved_data_labels:
        space_client.push_data_label_table_ids(
            table_id_list=resolved_table_ids or None,
            data_label_list=resolved_data_labels or None,
            is_publish=True,
            bk_tenant_id=bk_tenant_id,
        )

    refreshed_space_routes: list[dict[str, Any]] = []
    for bk_biz_id in resolved_bk_biz_ids:
        exists = models.Space.objects.filter(
            bk_tenant_id=bk_tenant_id,
            space_type_id=SpaceTypes.BKCC.value,
            space_id=str(bk_biz_id),
        ).exists()
        if exists:
            space_client.push_space_table_ids(
                space_type=SpaceTypes.BKCC.value,
                space_id=str(bk_biz_id),
                is_publish=True,
            )
        refreshed_space_routes.append(
            {
                "space_type": SpaceTypes.BKCC.value,
                "space_id": str(bk_biz_id),
                "exists": exists,
            }
        )

    return {
        "query": {
            "table_ids": input_table_ids,
            "data_labels": input_data_labels,
            "bk_biz_ids": input_bk_biz_ids,
            "bk_tenant_id": bk_tenant_id,
        },
        "refreshed": {
            "table_ids": resolved_table_ids,
            "data_labels": resolved_data_labels,
            "space_routes": refreshed_space_routes,
        },
    }


def _normalize_route_field_alias_map(field_alias: Any) -> dict[str, str]:
    if isinstance(field_alias, dict):
        return {str(key): str(value) for key, value in field_alias.items()}

    if isinstance(field_alias, list | tuple):
        normalized: dict[str, str] = {}
        for item in field_alias:
            if isinstance(item, dict):
                normalized.update({str(key): str(value) for key, value in item.items()})
        return normalized

    return {}


def _normalize_storage_cluster_records(records: Any) -> list[dict[str, Any]]:
    normalized_records: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        storage_id = record.get("storage_id", record.get("cluster_id"))
        enable_time = record.get("enable_time")
        normalized_records.append(
            {
                "storage_id": storage_id,
                "enable_time": int(enable_time) if str(enable_time).isdigit() else 0,
            }
        )

    return sorted(
        normalized_records,
        key=lambda item: (-(item.get("enable_time") or 0), str(item.get("storage_id") or "")),
    )


def _serialize_cluster_info(cluster: models.ClusterInfo | None, cluster_id: int | None) -> dict[str, Any]:
    if cluster is None:
        return {
            "cluster_id": cluster_id,
            "exists": False,
        }

    return {
        "cluster_id": cluster.cluster_id,
        "exists": True,
        "cluster_name": cluster.cluster_name,
        "display_name": cluster.display_name,
        "cluster_type": cluster.cluster_type,
        "domain_name": cluster.domain_name,
        "port": cluster.port,
        "schema": cluster.schema,
        "version": cluster.version,
        "description": cluster.description,
    }


def _get_storage_cluster_history(
    es_storage: models.ESStorage, cluster_map: dict[int, models.ClusterInfo]
) -> list[dict[str, Any]]:
    history_table_id = es_storage.origin_table_id or es_storage.table_id
    records = models.StorageClusterRecord.objects.filter(
        table_id=history_table_id, bk_tenant_id=es_storage.bk_tenant_id
    ).order_by("-create_time")

    history: list[dict[str, Any]] = []
    for record in records:
        history.append(
            {
                "table_id": history_table_id,
                "cluster_id": record.cluster_id,
                "is_current": record.is_current,
                "is_deleted": record.is_deleted,
                "enable_time": _serialize_value(record.enable_time),
                "disable_time": _serialize_value(record.disable_time),
                "delete_time": _serialize_value(record.delete_time),
                "cluster": _serialize_cluster_info(cluster_map.get(record.cluster_id), record.cluster_id),
            }
        )

    return history


def _query_alias_binding(
    es_storage: models.ESStorage, alias_name: str, latest_index_name: str | None
) -> dict[str, Any]:
    try:
        bound_indices = sorted(es_storage.es_client.indices.get_alias(name=alias_name).keys())
        return {
            "alias_name": alias_name,
            "exists": True,
            "bound_indices": bound_indices,
            "points_to_latest_index": bool(latest_index_name and latest_index_name in bound_indices),
        }
    except Exception as error:  # pylint: disable=broad-except
        return {
            "alias_name": alias_name,
            "exists": False,
            "bound_indices": [],
            "points_to_latest_index": False,
            "error": str(error),
        }


def _build_es_index_check(es_storage: models.ESStorage) -> dict[str, Any]:
    if not es_storage.need_create_index:
        return {
            "queried": False,
            "skipped": True,
            "reason": "need_create_index=False，虚拟表或不创建物理索引的 ESStorage 不执行索引轮转检查",
        }

    result: dict[str, Any] = {
        "queried": True,
        "skipped": False,
        "index_count": 0,
        "total_size_bytes": 0,
        "indices": [],
    }

    try:
        index_stats, index_version = es_storage.get_index_stats()
        result["index_version"] = index_version

        if index_version:
            index_pattern = es_storage.search_format_v2() if index_version == "v2" else es_storage.search_format_v1()
            alias_info = es_storage.es_client.indices.get(index=index_pattern)
        else:
            alias_info = {}

        indices: list[dict[str, Any]] = []
        total_size_bytes = 0
        for index_name in sorted(index_stats.keys()):
            stat = index_stats[index_name]
            size_bytes = ((stat.get("primaries") or {}).get("store") or {}).get("size_in_bytes") or 0
            doc_count = ((stat.get("primaries") or {}).get("docs") or {}).get("count") or 0
            total_size_bytes += size_bytes
            indices.append(
                {
                    "index_name": index_name,
                    "size_bytes": size_bytes,
                    "doc_count": doc_count,
                    "aliases": sorted(list(((alias_info.get(index_name) or {}).get("aliases") or {}).keys())),
                }
            )

        result["indices"] = indices
        result["index_count"] = len(indices)
        result["total_size_bytes"] = total_size_bytes
    except Exception as error:  # pylint: disable=broad-except
        result["query_error"] = str(error)
        result["indices"] = []

    latest_index_name = None
    current_index_info = None
    try:
        current_index_info = es_storage.current_index_info()
        latest_index_name = es_storage.make_index_name(
            current_index_info["datetime_object"],
            current_index_info["index"],
            current_index_info["index_version"],
        )
        result["current_index"] = {
            "index_name": latest_index_name,
            "index_version": current_index_info["index_version"],
            "size_bytes": current_index_info["size"],
            "index_time": _serialize_value(current_index_info["datetime_object"]),
            "index_seq": current_index_info["index"],
        }
    except Exception as error:  # pylint: disable=broad-except
        result["current_index"] = {"error": str(error)}

    latest_index_ready = False
    if latest_index_name:
        try:
            latest_index_ready = es_storage.is_index_ready(latest_index_name)
        except Exception as error:  # pylint: disable=broad-except
            result.setdefault("current_index", {})["ready_check_error"] = str(error)

    current_time_str = es_storage.now.strftime(es_storage.date_format)
    expected_write_alias = f"write_{current_time_str}_{es_storage.index_name}"
    expected_read_alias = f"{es_storage.index_name}_{current_time_str}_read"
    write_alias_check = _query_alias_binding(es_storage, expected_write_alias, latest_index_name)
    read_alias_check = _query_alias_binding(es_storage, expected_read_alias, latest_index_name)

    should_rotate = False
    try:
        should_rotate = bool(es_storage._should_create_index())  # pylint: disable=protected-access
    except Exception as error:  # pylint: disable=broad-except
        result["should_rotate_error"] = str(error)

    abnormal_reasons: list[str] = []
    if not latest_index_name:
        abnormal_reasons.append("未识别到当前索引")
    if latest_index_name and not latest_index_ready:
        abnormal_reasons.append("当前最新索引未就绪")
    if not write_alias_check["exists"]:
        abnormal_reasons.append("当前时间片写别名不存在")
    elif not write_alias_check["points_to_latest_index"]:
        abnormal_reasons.append("当前时间片写别名未指向最新索引")
    if not read_alias_check["exists"]:
        abnormal_reasons.append("当前时间片读别名不存在")
    elif not read_alias_check["points_to_latest_index"]:
        abnormal_reasons.append("当前时间片读别名未指向最新索引")
    if should_rotate:
        abnormal_reasons.append("当前索引已满足轮转条件，建议检查轮转任务是否正常执行")

    result["rotation_check"] = {
        "is_normal": len(abnormal_reasons) == 0,
        "abnormal_reasons": abnormal_reasons,
        "latest_index_name": latest_index_name,
        "latest_index_ready": latest_index_ready,
        "should_rotate": should_rotate,
        "expected_write_alias": write_alias_check,
        "expected_read_alias": read_alias_check,
    }
    return result


def _build_es_route_detail_check(
    es_storage: models.ESStorage,
    result_table: models.ResultTable | None,
    expected_field_alias_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    redis_key = _build_result_table_detail_key(es_storage.table_id, es_storage.bk_tenant_id)
    raw_route_detail = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, redis_key)
    route_detail = _decode_redis_json(raw_route_detail) or {}

    expected_storage_cluster_records = _normalize_storage_cluster_records(
        models.StorageClusterRecord.compose_table_id_storage_cluster_records(
            es_storage.table_id, es_storage.bk_tenant_id
        )
    )
    actual_storage_cluster_records = _normalize_storage_cluster_records(route_detail.get("storage_cluster_records"))

    expected_field_alias = expected_field_alias_map.get(
        reformat_table_id(es_storage.table_id),
        expected_field_alias_map.get(es_storage.table_id, {}),
    )
    actual_field_alias = _normalize_route_field_alias_map(route_detail.get("field_alias"))

    expected_data_label = result_table.data_label if result_table else ""
    checks = {
        "storage_id_match": route_detail.get("storage_id") == es_storage.storage_cluster_id,
        "db_match": (route_detail.get("db") or "") == (es_storage.index_set or ""),
        "storage_type_match": route_detail.get("storage_type") == models.ESStorage.STORAGE_TYPE,
        "source_type_match": (route_detail.get("source_type") or "") == (es_storage.source_type or ""),
        "data_label_match": (route_detail.get("data_label") or "") == (expected_data_label or ""),
        "storage_cluster_records_match": actual_storage_cluster_records == expected_storage_cluster_records,
        "field_alias_match": actual_field_alias == expected_field_alias,
    }

    return {
        "redis_key": redis_key,
        "exists": raw_route_detail is not None,
        "is_expected": raw_route_detail is not None and all(checks.values()),
        "checks": checks,
        "expected": {
            "storage_id": es_storage.storage_cluster_id,
            "db": es_storage.index_set or "",
            "storage_type": models.ESStorage.STORAGE_TYPE,
            "source_type": es_storage.source_type or "",
            "data_label": expected_data_label or "",
            "storage_cluster_record_count": len(expected_storage_cluster_records),
            "field_alias_count": len(expected_field_alias),
        },
        "actual": {
            "storage_id": route_detail.get("storage_id"),
            "db": route_detail.get("db"),
            "storage_type": route_detail.get("storage_type"),
            "source_type": route_detail.get("source_type"),
            "data_label": route_detail.get("data_label"),
            "storage_cluster_record_count": len(actual_storage_cluster_records),
            "field_alias_count": len(actual_field_alias),
        },
    }


@KernelRPCRegistry.register(
    "metadata_es_storage_check",
    summary="检查 ESStorage 关联索引、集群、轮转与 RT 路由",
    description=(
        "基于 table_id 或 bk_data_id 查询 ESStorage 的巡检信息，包括关联虚拟表、当前/历史存储集群、"
        "索引与别名、当前索引容量、轮转状态以及 RT_DETAIL 路由是否符合预期。"
    ),
    params_schema={
        "table_id": "可选，结果表 ID，与 bk_data_id 至少提供一个",
        "bk_data_id": "可选，数据源 ID，与 table_id 至少提供一个",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户",
    },
    example_params={"table_id": "2_bklog.demo"},
)
def metadata_es_storage_check(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    input_table_id = params.get("table_id")
    input_bk_data_id = params.get("bk_data_id")

    if not input_table_id and input_bk_data_id is None:
        raise CustomException(message="table_id 和 bk_data_id 至少需要提供一个")

    seed_table_ids: set[str] = set()
    normalized_bk_data_id: int | None = None
    if input_table_id:
        seed_table_ids.add(reformat_table_id(str(input_table_id)))
    if input_bk_data_id is not None:
        normalized_bk_data_id = _normalize_bk_data_id(input_bk_data_id)
        seed_table_ids.update(
            reformat_table_id(table_id)
            for table_id in models.DataSourceResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=normalized_bk_data_id
            ).values_list("table_id", flat=True)
        )

    related_table_ids, es_storages = _expand_es_related_table_ids(seed_table_ids, bk_tenant_id)
    if not es_storages:
        raise CustomException(message="未查询到匹配的 ESStorage 配置")

    raw_related_table_ids = {str(table_id) for table_id in related_table_ids if table_id}
    related_table_ids = {reformat_table_id(table_id) for table_id in raw_related_table_ids}
    related_table_id_candidates = related_table_ids | raw_related_table_ids
    related_result_tables = {
        reformat_table_id(item.table_id): item
        for item in models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=related_table_id_candidates
        )
    }

    dsrt_records = list(
        models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=related_table_id_candidates
        ).values("table_id", "bk_data_id")
    )
    table_data_id_map: dict[str, list[int]] = {}
    all_bk_data_ids: set[int] = set()
    for record in dsrt_records:
        normalized_table_id = reformat_table_id(record["table_id"])
        table_data_id_map.setdefault(normalized_table_id, []).append(record["bk_data_id"])
        all_bk_data_ids.add(record["bk_data_id"])

    datasource_map = {
        item.bk_data_id: item
        for item in models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=all_bk_data_ids)
    }

    cluster_ids = {item.storage_cluster_id for item in es_storages if item.storage_cluster_id is not None}
    history_table_ids = {item.origin_table_id or item.table_id for item in es_storages}
    cluster_ids.update(
        models.StorageClusterRecord.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=history_table_ids
        ).values_list("cluster_id", flat=True)
    )
    cluster_map = {
        item.cluster_id: item
        for item in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=cluster_ids)
    }

    es_storage_map = {reformat_table_id(item.table_id): item for item in es_storages}
    virtual_table_map: dict[str, list[models.ESStorage]] = {}
    for item in es_storages:
        if item.origin_table_id:
            virtual_table_map.setdefault(reformat_table_id(item.origin_table_id), []).append(item)

    field_alias_map = {
        reformat_table_id(table_id): alias_map
        for table_id, alias_map in SpaceTableIDRedis()
        ._get_field_alias_map(
            table_id_list=sorted({item.table_id for item in es_storages} | set(es_storage_map.keys())),
            bk_tenant_id=bk_tenant_id,
        )
        .items()
    }

    items: list[dict[str, Any]] = []
    for table_id in sorted(es_storage_map.keys(), key=lambda tid: (es_storage_map[tid].origin_table_id or "", tid)):
        es_storage = es_storage_map[table_id]
        result_table = related_result_tables.get(table_id)
        data_ids = sorted(set(table_data_id_map.get(table_id, [])))
        datasource_refs = [
            {
                "bk_data_id": bk_data_id,
                "data_name": datasource_map[bk_data_id].data_name,
            }
            for bk_data_id in data_ids
            if bk_data_id in datasource_map
        ]

        current_cluster = _serialize_cluster_info(
            cluster_map.get(es_storage.storage_cluster_id), es_storage.storage_cluster_id
        )
        related_virtual_tables = []
        if es_storage.need_create_index:
            for virtual_es_storage in sorted(
                virtual_table_map.get(table_id, []),
                key=lambda item: item.table_id,
            ):
                virtual_table_id = reformat_table_id(virtual_es_storage.table_id)
                virtual_rt = related_result_tables.get(virtual_table_id)
                related_virtual_tables.append(
                    {
                        "table_id": virtual_table_id,
                        "table_name": virtual_rt.table_name_zh if virtual_rt else "",
                        "data_label": virtual_rt.data_label if virtual_rt else "",
                        "index_set": virtual_es_storage.index_set or "",
                        "need_create_index": virtual_es_storage.need_create_index,
                    }
                )

        items.append(
            {
                "table": {
                    "table_id": table_id,
                    "table_name": result_table.table_name_zh if result_table else "",
                    "bk_biz_id": result_table.bk_biz_id if result_table else None,
                    "data_label": result_table.data_label if result_table else "",
                    "data_labels": [
                        label.strip()
                        for label in (result_table.data_label or "").split(",")
                        if result_table and label.strip()
                    ]
                    if result_table
                    else [],
                    "datasources": datasource_refs,
                    "is_enable": result_table.is_enable if result_table else None,
                    "is_deleted": result_table.is_deleted if result_table else None,
                },
                "es_storage": {
                    "table_id": table_id,
                    "origin_table_id": es_storage.origin_table_id or "",
                    "need_create_index": es_storage.need_create_index,
                    "index_set": es_storage.index_set or "",
                    "source_type": es_storage.source_type or "",
                    "storage_cluster_id": es_storage.storage_cluster_id,
                    "retention": es_storage.retention,
                    "slice_gap": es_storage.slice_gap,
                    "slice_size": es_storage.slice_size,
                },
                "related_virtual_tables": related_virtual_tables,
                "current_cluster": current_cluster,
                "history_clusters": _get_storage_cluster_history(es_storage, cluster_map),
                "index_check": _build_es_index_check(es_storage),
                "route_detail_check": _build_es_route_detail_check(es_storage, result_table, field_alias_map),
            }
        )

    return {
        "query": {
            "table_id": input_table_id,
            "bk_data_id": normalized_bk_data_id,
            "bk_tenant_id": bk_tenant_id,
        },
        "items": items,
    }


def _normalize_optional_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    raise CustomException(message=f"{field_name} 必须是整数或整数字符串")


def _resolve_custom_metric_group(
    bk_tenant_id: str,
    bk_data_id: int | None = None,
    table_id: str | None = None,
    time_series_group_id: int | None = None,
) -> models.TimeSeriesGroup:
    """
    解析自定义指标分组。

    这里的设计目标是“尽量定位到唯一实例”，而不是对多个定位参数做严格的交叉一致性校验。
    实际调用里通常只会传入一个定位参数；如果首轮按 TimeSeriesGroup 直接过滤没有命中，
    且传入了 table_id，则允许再基于 TimeSeriesMetric.table_id 做一次回退匹配，
    只要最终能唯一定位到分组即可。
    """
    queryset = models.TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False)
    if time_series_group_id is not None:
        queryset = queryset.filter(time_series_group_id=time_series_group_id)
    if bk_data_id is not None:
        queryset = queryset.filter(bk_data_id=bk_data_id)
    if table_id:
        normalized_table_id = reformat_table_id(table_id)
        queryset = queryset.filter(Q(table_id=table_id) | Q(table_id=normalized_table_id))

    groups = list(queryset[:2])
    if not groups and table_id:
        normalized_table_id = reformat_table_id(table_id)
        metric_group_ids = list(
            models.TimeSeriesMetric.objects.filter(table_id__in=[table_id, normalized_table_id])
            .values_list("group_id", flat=True)
            .distinct()[:2]
        )
        if metric_group_ids:
            groups = list(
                models.TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id, is_delete=False, time_series_group_id__in=metric_group_ids
                )[:2]
            )

    if not groups:
        raise CustomException(message="未查询到匹配的自定义指标分组")
    if len(groups) > 1:
        raise CustomException(
            message=f"查询条件匹配到多个自定义指标分组，请补充更精确参数：{[group.time_series_group_id for group in groups]}"
        )
    return groups[0]


def _build_data_label_route_checks(table_id: str, data_label: str, bk_tenant_id: str) -> list[dict[str, Any]]:
    route_items: list[dict[str, Any]] = []
    for item in [label.strip() for label in (data_label or "").split(",") if label.strip()]:
        redis_key = _build_data_label_route_key(item, bk_tenant_id)
        raw_route_table_ids = RedisTools.hget(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_key)
        route_table_ids = _decode_redis_json(raw_route_table_ids) or []
        normalized_route_table_ids = {reformat_table_id(route_table_id) for route_table_id in route_table_ids}
        route_items.append(
            {
                "data_label": item,
                "redis_key": redis_key,
                "exists": raw_route_table_ids is not None,
                "contains_table_id": table_id in normalized_route_table_ids,
                "stats": {
                    "route_table_count": len(normalized_route_table_ids),
                    "checked_table_count": 1,
                    "existing_table_count": 1 if table_id in normalized_route_table_ids else 0,
                    "missing_table_count": 0 if table_id in normalized_route_table_ids else 1,
                },
            }
        )
    return route_items


def _build_space_route_check(table_id: str, bk_biz_id: int | None, bk_tenant_id: str) -> dict[str, Any] | None:
    if bk_biz_id is None:
        return None

    redis_key = _build_space_route_key(bk_biz_id, bk_tenant_id)
    raw_space_route_value = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, redis_key)
    raw_space_route_data = _decode_redis_json(raw_space_route_value) or {}
    normalized_space_route_data = _normalize_space_route_data(raw_space_route_data)
    table_route = normalized_space_route_data.get(table_id) or {}

    return {
        "space_type": SpaceTypes.BKCC.value,
        "space_id": str(bk_biz_id),
        "redis_key": redis_key,
        "exists": raw_space_route_value is not None,
        "contains_table_id": table_id in normalized_space_route_data,
        "has_filters": bool(table_route.get("filters")),
        "filter_count": len(table_route.get("filters") or []),
        "stats": {
            "route_table_count": len(normalized_space_route_data),
            "checked_table_count": 1,
            "existing_table_count": 1 if table_id in normalized_space_route_data else 0,
            "missing_table_count": 0 if table_id in normalized_space_route_data else 1,
        },
    }


@KernelRPCRegistry.register(
    "metadata_custom_metric_check",
    summary="检查自定义指标链路与路由状态",
    description=(
        "基于 bk_data_id、table_id 或 time_series_group_id 定位具体的自定义指标分组，"
        "定位逻辑以尽量解析到唯一实例为目标，通常只需传一个定位参数；"
        "检查 TimeSeriesMetric/ResultTableField/Redis 指标发现状态、自动发现配置、"
        "bkbase 或 transfer 清洗链路，以及 rt_detail/data_label/space 路由是否正常。"
    ),
    params_schema={
        "bk_data_id": "可选，数据源 ID；通常三者传一个即可，与 table_id/time_series_group_id 至少提供一个",
        "table_id": "可选，结果表 ID；通常三者传一个即可，与 bk_data_id/time_series_group_id 至少提供一个",
        "time_series_group_id": "可选，自定义时序分组 ID；通常三者传一个即可，与 bk_data_id/table_id 至少提供一个",
        "metric_fields": "可选，待校验的指标名列表，支持字符串逗号分隔或数组",
        "bk_biz_id": "可选，用于校验 space 路由；不传时默认使用分组或结果表上的业务 ID",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户",
    },
    example_params={"bk_data_id": 50010, "metric_fields": ["usage", "idle"]},
)
def metadata_custom_metric_check(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    normalized_bk_data_id = (
        _normalize_bk_data_id(params["bk_data_id"]) if params.get("bk_data_id") is not None else None
    )
    input_table_id = str(params.get("table_id")).strip() if params.get("table_id") else None
    normalized_time_series_group_id = _normalize_optional_int(
        params.get("time_series_group_id"), "time_series_group_id"
    )
    input_metric_fields = _normalize_string_list(params.get("metric_fields"), "metric_fields")
    input_bk_biz_id = _normalize_optional_int(params.get("bk_biz_id"), "bk_biz_id")

    if normalized_bk_data_id is None and not input_table_id and normalized_time_series_group_id is None:
        raise CustomException(message="bk_data_id、table_id 和 time_series_group_id 至少需要提供一个")

    group = _resolve_custom_metric_group(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=normalized_bk_data_id,
        table_id=input_table_id,
        time_series_group_id=normalized_time_series_group_id,
    )
    table_id = reformat_table_id(group.table_id)

    result_table = (
        models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id)
        .filter(Q(table_id=group.table_id) | Q(table_id=table_id))
        .first()
    )
    datasource = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=group.bk_data_id).first()

    resolved_bk_biz_id = input_bk_biz_id
    if resolved_bk_biz_id is None:
        resolved_bk_biz_id = group.bk_biz_id if group.bk_biz_id not in (None, 0) else None
    if resolved_bk_biz_id is None and result_table and result_table.bk_biz_id not in (None, 0):
        resolved_bk_biz_id = result_table.bk_biz_id

    all_rt_field_queryset = models.ResultTableField.objects.filter(
        table_id__in=[group.table_id, table_id],
        bk_tenant_id=bk_tenant_id,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
    )
    rt_field_total_count = all_rt_field_queryset.count()
    rt_field_records: list[dict[str, Any]] = []
    if input_metric_fields:
        rt_field_records = list(
            all_rt_field_queryset.filter(field_name__in=input_metric_fields).values("field_name", "is_disabled")
        )
    rt_field_map = {record["field_name"]: record for record in rt_field_records}

    all_time_series_metric_queryset = models.TimeSeriesMetric.objects.filter(group_id=group.time_series_group_id)
    time_series_metric_total_count = all_time_series_metric_queryset.values("field_name").distinct().count()
    time_series_metric_records: list[dict[str, Any]] = []
    if input_metric_fields:
        time_series_metric_records = list(
            all_time_series_metric_queryset.filter(field_name__in=input_metric_fields).values(
                "field_name", "field_scope", "scope_id", "is_active", "table_id"
            )
        )
    time_series_metric_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"scope_count": 0, "active_scope_count": 0, "table_ids": set(), "scopes": set()}
    )
    for record in time_series_metric_records:
        metric_info = time_series_metric_map[record["field_name"]]
        metric_info["scope_count"] += 1
        metric_info["active_scope_count"] += 1 if record["is_active"] else 0
        if record["table_id"]:
            metric_info["table_ids"].add(record["table_id"])
        if record["field_scope"]:
            metric_info["scopes"].add(record["field_scope"])

    remote_metrics_error = None
    remote_metrics_queried = bool(input_metric_fields)
    remote_metric_records: list[dict[str, Any]] = []
    if remote_metrics_queried:
        try:
            remote_metric_records = group.get_metrics_from_redis()
        except Exception as error:  # pylint: disable=broad-except
            remote_metrics_error = str(error)

    remote_metric_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"scope_count": 0, "latest_modify_time": None, "tag_key_count": 0}
    )
    for record in remote_metric_records:
        field_name = record.get("field_name")
        if not field_name:
            continue
        remote_info = remote_metric_map[field_name]
        remote_info["scope_count"] += 1
        remote_info["latest_modify_time"] = max(
            remote_info["latest_modify_time"] or 0,
            record.get("last_modify_time") or 0,
        )
        remote_info["tag_key_count"] = max(
            remote_info["tag_key_count"],
            len((record.get("tag_value_list") or {}).keys()),
        )

    redis_key = _build_result_table_detail_key(table_id, bk_tenant_id)
    raw_route_detail = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, redis_key)
    route_detail = _decode_redis_json(raw_route_detail) or {}
    rt_route_field_names = _extract_route_field_names(route_detail)

    checked_metric_fields = input_metric_fields
    metric_field_items: list[dict[str, Any]] = []
    for field_name in checked_metric_fields:
        ts_metric_info = time_series_metric_map.get(field_name) or {
            "scope_count": 0,
            "active_scope_count": 0,
            "table_ids": set(),
            "scopes": set(),
        }
        remote_metric_info = remote_metric_map.get(field_name) or {
            "scope_count": 0,
            "latest_modify_time": None,
            "tag_key_count": 0,
        }
        rt_field_info = rt_field_map.get(field_name)
        metric_field_items.append(
            {
                "field_name": field_name,
                "in_result_table_field": rt_field_info is not None,
                "result_table_field_enabled": bool(rt_field_info and not rt_field_info["is_disabled"]),
                "in_time_series_metric": ts_metric_info["scope_count"] > 0,
                "active_in_time_series_metric": ts_metric_info["active_scope_count"] > 0,
                "in_remote_metrics": remote_metric_info["scope_count"] > 0,
                "in_rt_detail_route": field_name in rt_route_field_names,
                "stats": {
                    "time_series_metric_scope_count": ts_metric_info["scope_count"],
                    "active_time_series_metric_scope_count": ts_metric_info["active_scope_count"],
                    "remote_metric_scope_count": remote_metric_info["scope_count"],
                    "remote_metric_tag_key_count": remote_metric_info["tag_key_count"],
                },
                "latest_remote_modify_time": _serialize_value(
                    datetime.fromtimestamp(remote_metric_info["latest_modify_time"])
                )
                if remote_metric_info["latest_modify_time"]
                else None,
            }
        )

    data_label_route_items = _build_data_label_route_checks(
        table_id=table_id,
        data_label=result_table.data_label if result_table else group.data_label,
        bk_tenant_id=bk_tenant_id,
    )
    space_route = _build_space_route_check(table_id=table_id, bk_biz_id=resolved_bk_biz_id, bk_tenant_id=bk_tenant_id)

    existing_rt_route_metric_fields = sorted(set(checked_metric_fields) & rt_route_field_names)
    missing_rt_route_metric_fields = sorted(set(checked_metric_fields) - rt_route_field_names)

    return {
        "query": {
            "bk_data_id": normalized_bk_data_id,
            "table_id": input_table_id,
            "time_series_group_id": normalized_time_series_group_id,
            "metric_fields": input_metric_fields,
            "bk_biz_id": input_bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
        },
        "resolved": {
            "bk_data_id": group.bk_data_id,
            "table_id": table_id,
            "time_series_group_id": group.time_series_group_id,
            "bk_biz_id": resolved_bk_biz_id,
        },
        "time_series_group": {
            "time_series_group_id": group.time_series_group_id,
            "time_series_group_name": group.time_series_group_name,
            "bk_data_id": group.bk_data_id,
            "bk_biz_id": group.bk_biz_id,
            "table_id": table_id,
            "label": group.label,
            "is_enable": group.is_enable,
            "is_delete": group.is_delete,
            "data_label": group.data_label,
            "is_auto_discovery": group.is_auto_discovery(),
            "is_split_measurement": group.is_split_measurement,
        },
        "data_source": {
            "bk_data_id": datasource.bk_data_id if datasource else group.bk_data_id,
            "data_name": datasource.data_name if datasource else "",
            "created_from": datasource.created_from if datasource else "",
            "transfer_cluster_id": datasource.transfer_cluster_id if datasource else "",
            "cleaning_engine": (
                "bkbase"
                if datasource and datasource.created_from == DataIdCreatedFromSystem.BKDATA.value
                else "transfer"
            ),
            "data_link_version": (
                "v4" if datasource and datasource.created_from == DataIdCreatedFromSystem.BKDATA.value else "v3"
            ),
        },
        "result_table": {
            "table_id": table_id,
            "table_name": result_table.table_name_zh if result_table else "",
            "bk_biz_id": result_table.bk_biz_id if result_table else None,
            "data_label": result_table.data_label if result_table else group.data_label,
            "default_storage": result_table.default_storage if result_table else "",
            "is_enable": result_table.is_enable if result_table else None,
            "is_deleted": result_table.is_deleted if result_table else None,
        },
        "metric_checks": {
            "remote_metrics_error": remote_metrics_error,
            "remote_metrics_queried": remote_metrics_queried,
            "stats": {
                "checked_metric_count": len(checked_metric_fields),
                "result_table_field_metric_count": rt_field_total_count,
                "time_series_metric_count": time_series_metric_total_count,
                "remote_metric_count": len(remote_metric_map) if remote_metrics_queried else None,
                "rt_detail_route_field_count": len(rt_route_field_names),
            },
            "items": metric_field_items,
        },
        "routes": {
            "rt_detail": {
                "redis_key": redis_key,
                "exists": raw_route_detail is not None,
                "data_label_match": (route_detail.get("data_label") or "")
                == ((result_table.data_label if result_table else group.data_label) or ""),
                "stats": {
                    "route_field_count": len(rt_route_field_names),
                    "checked_metric_count": len(checked_metric_fields),
                    "existing_metric_count": len(existing_rt_route_metric_fields),
                    "missing_metric_count": len(missing_rt_route_metric_fields),
                },
                "checked_metric_fields": {
                    "existing": existing_rt_route_metric_fields,
                    "missing": missing_rt_route_metric_fields,
                },
            },
            "data_label_routes": data_label_route_items,
            "space_route": space_route,
        },
    }


def _normalize_bcs_cluster_id(bcs_cluster_id: Any) -> str:
    if bcs_cluster_id is None:
        raise CustomException(message="bcs_cluster_id 不能为空")
    if not isinstance(bcs_cluster_id, str):
        bcs_cluster_id = str(bcs_cluster_id)
    normalized = bcs_cluster_id.strip()
    if not normalized:
        raise CustomException(message="bcs_cluster_id 不能为空")
    return normalized


# 按默认 data_id 字段的展示顺序统一命名，便于前端/下游以稳定顺序消费
_BCS_BUILTIN_DATA_ID_FIELDS: tuple[tuple[str, str], ...] = (
    ("K8sMetricDataID", "k8s_metric"),
    ("CustomMetricDataID", "custom_metric"),
    ("K8sEventDataID", "k8s_event"),
)


def _collect_bcs_builtin_data_ids(cluster: models.BCSClusterInfo) -> tuple[list[dict[str, Any]], set[int]]:
    """
    汇总 BCSClusterInfo 上记录的内置 data_id。

    通过 register_cluster 流程通常只会注册 k8s_metric/custom_metric/k8s_event 三个，其他字段默认为 0；
    这里统一把字段值暴露出来（为 0 则 registered=False，方便巡检是否缺失）。
    """
    builtin_items: list[dict[str, Any]] = []
    builtin_data_ids: set[int] = set()
    for field_name, usage in _BCS_BUILTIN_DATA_ID_FIELDS:
        bk_data_id = getattr(cluster, field_name, 0) or 0
        builtin_items.append(
            {
                "field": field_name,
                "usage": usage,
                "bk_data_id": bk_data_id,
                "registered": bk_data_id > 0,
            }
        )
        if bk_data_id > 0:
            builtin_data_ids.add(bk_data_id)
    return builtin_items, builtin_data_ids


def _serialize_bkci_project(space: models.Space | None, project_id: str) -> dict[str, Any]:
    if space is None:
        return {
            "project_id": project_id,
            "exists": False,
        }
    return {
        "project_id": project_id,
        "exists": True,
        "space_type_id": space.space_type_id,
        "space_id": space.space_id,
        "space_name": space.space_name,
        "space_code": space.space_code,
        "bk_tenant_id": space.bk_tenant_id,
        "status": space.status,
        "is_bcs_valid": space.is_bcs_valid,
    }


def _serialize_bkcc_biz(space: models.Space | None, bk_biz_id: int) -> dict[str, Any]:
    if space is None:
        return {
            "bk_biz_id": bk_biz_id,
            "exists": False,
        }
    return {
        "bk_biz_id": bk_biz_id,
        "exists": True,
        "space_type_id": space.space_type_id,
        "space_id": space.space_id,
        "space_name": space.space_name,
        "bk_tenant_id": space.bk_tenant_id,
        "status": space.status,
    }


def _serialize_federal_info(
    cluster_id: str,
    fed_by_host: list[models.BcsFederalClusterInfo],
    fed_by_sub: list[models.BcsFederalClusterInfo],
    fed_by_fed: list[models.BcsFederalClusterInfo],
) -> dict[str, Any]:
    """
    根据集群在联邦关系中的不同位置（host / sub / fed 入口），汇总联邦拓扑信息。

    - fed_by_host: 当前集群作为 HOST 集群时，管理的 fed 入口-子集群映射
    - fed_by_sub:  当前集群作为子集群时，所属的 fed 入口与 HOST
    - fed_by_fed:  当前集群作为联邦入口（fed_cluster_id）时，下辖的 HOST + sub
    """

    def _to_item(record: models.BcsFederalClusterInfo) -> dict[str, Any]:
        return {
            "fed_cluster_id": record.fed_cluster_id,
            "host_cluster_id": record.host_cluster_id,
            "sub_cluster_id": record.sub_cluster_id,
            "is_deleted": record.is_deleted,
            "fed_namespaces": record.fed_namespaces or [],
            "fed_builtin_metric_table_id": record.fed_builtin_metric_table_id or "",
            "fed_builtin_event_table_id": record.fed_builtin_event_table_id or "",
        }

    roles: list[str] = []
    if fed_by_fed:
        roles.append("fed_entry")
    if fed_by_host:
        roles.append("host")
    if fed_by_sub:
        roles.append("sub")

    return {
        "cluster_id": cluster_id,
        "is_federal": bool(roles),
        "roles": roles,
        "as_fed_entry": [_to_item(record) for record in fed_by_fed],
        "as_host": [_to_item(record) for record in fed_by_host],
        "as_sub": [_to_item(record) for record in fed_by_sub],
    }


@KernelRPCRegistry.register(
    "metadata_bcs_cluster_related_info",
    summary="基于 bcs_cluster_id 查询关联元数据",
    description=(
        "基于 BCS 集群 ID 查询关联的 bkcc 业务、bkci 项目、内置/业务 data_id、结果表、"
        "VM 接入记录以及联邦集群拓扑信息。"
        "\n"
        "- BCSClusterInfo 直接持有 bk_biz_id(bkcc)、project_id(bkci) 以及 k8s_metric/custom_metric/k8s_event 等内置 data_id；"
        "\n"
        "- bkci 项目信息通过 Space(space_type_id=bkci, space_code=project_id) 关联；"
        "\n"
        "- bkcc 业务名通过 Space(space_type_id=bkcc, space_id=str(bk_biz_id)) 关联；"
        "\n"
        "- 业务 data_id 通过 data_name 前缀 bcs_{cluster_id}_ 以及 AccessVMRecord.bcs_cluster_id 进一步补齐，"
        "并汇总对应的 result_table_id/vm_result_table_id 等信息。"
    ),
    params_schema={
        "bcs_cluster_id": "必填，BCS 集群 ID（BCSClusterInfo.cluster_id 或 bcs_api_cluster_id），如 BCS-K8S-00000",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户。cluster_id 全局唯一时可忽略",
    },
    example_params={"bcs_cluster_id": "BCS-K8S-00000"},
)
def metadata_bcs_cluster_related_info(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    bcs_cluster_id = _normalize_bcs_cluster_id(params.get("bcs_cluster_id"))

    cluster = (
        models.BCSClusterInfo.objects.filter(Q(cluster_id=bcs_cluster_id) | Q(bcs_api_cluster_id=bcs_cluster_id))
        .order_by("-last_modify_time")
        .first()
    )
    if cluster is None:
        raise CustomException(message=f"未查询到匹配的 BCSClusterInfo，bcs_cluster_id={bcs_cluster_id}")

    effective_tenant_id = cluster.bk_tenant_id or bk_tenant_id

    builtin_data_id_items, builtin_data_ids = _collect_bcs_builtin_data_ids(cluster)

    # bkcc 业务空间（space_type_id=bkcc, space_id=str(bk_biz_id)）
    bkcc_space = (
        models.Space.objects.filter(
            space_type_id=SpaceTypes.BKCC.value,
            space_id=str(cluster.bk_biz_id),
            bk_tenant_id=effective_tenant_id,
        ).first()
        if cluster.bk_biz_id is not None
        else None
    )

    # bkci 项目空间：Space.space_code == BCSClusterInfo.project_id
    bkci_space = (
        models.Space.objects.filter(
            space_type_id=SpaceTypes.BKCI.value,
            space_code=cluster.project_id,
            bk_tenant_id=effective_tenant_id,
        ).first()
        if cluster.project_id
        else None
    )

    # bkci → bkcc 资源绑定（SpaceResource）
    bkci_to_bkcc_resource = None
    if bkci_space is not None:
        resource = models.SpaceResource.objects.filter(
            space_type_id=SpaceTypes.BKCI.value,
            space_id=bkci_space.space_id,
            resource_type=SpaceTypes.BKCC.value,
            bk_tenant_id=effective_tenant_id,
        ).first()
        if resource is not None:
            bkci_to_bkcc_resource = {
                "space_type_id": resource.space_type_id,
                "space_id": resource.space_id,
                "resource_type": resource.resource_type,
                "resource_id": resource.resource_id,
                "bk_tenant_id": resource.bk_tenant_id,
                "dimension_values": resource.dimension_values or [],
            }

    # 汇总 data_id：内置 + data_name 以 bcs_{cluster_id}_ 前缀的业务数据源 + AccessVMRecord 关联的 bk_data_id
    bcs_datasource_queryset = models.DataSource.objects.filter(data_name__startswith=f"bcs_{cluster.cluster_id}_")
    if effective_tenant_id:
        bcs_datasource_queryset = bcs_datasource_queryset.filter(bk_tenant_id=effective_tenant_id)

    access_vm_queryset = models.AccessVMRecord.objects.filter(bcs_cluster_id=cluster.cluster_id)
    if effective_tenant_id:
        access_vm_queryset = access_vm_queryset.filter(bk_tenant_id=effective_tenant_id)
    access_vm_records = list(
        access_vm_queryset.values(
            "result_table_id",
            "data_type",
            "bcs_cluster_id",
            "storage_cluster_id",
            "vm_cluster_id",
            "bk_base_data_id",
            "bk_base_data_name",
            "vm_result_table_id",
            "remark",
            "bk_tenant_id",
        )
    )

    related_data_ids: set[int] = set(builtin_data_ids)
    related_data_ids.update(bcs_datasource_queryset.values_list("bk_data_id", flat=True))

    # 通过 VM 记录对应的 result_table 反查 data_id，补齐那些非 bcs_ 前缀但确实由该集群产生的数据源
    vm_related_table_ids = {record["result_table_id"] for record in access_vm_records if record.get("result_table_id")}
    if vm_related_table_ids:
        related_data_ids.update(
            models.DataSourceResultTable.objects.filter(
                bk_tenant_id=effective_tenant_id, table_id__in=vm_related_table_ids
            ).values_list("bk_data_id", flat=True)
        )

    datasource_queryset = models.DataSource.objects.filter(bk_data_id__in=related_data_ids)
    if effective_tenant_id:
        datasource_queryset = datasource_queryset.filter(bk_tenant_id=effective_tenant_id)

    dsrt_queryset = models.DataSourceResultTable.objects.filter(bk_data_id__in=related_data_ids)
    if effective_tenant_id:
        dsrt_queryset = dsrt_queryset.filter(bk_tenant_id=effective_tenant_id)

    related_table_ids = set(dsrt_queryset.values_list("table_id", flat=True)) | vm_related_table_ids
    result_table_queryset = models.ResultTable.objects.filter(table_id__in=related_table_ids)
    if effective_tenant_id:
        result_table_queryset = result_table_queryset.filter(bk_tenant_id=effective_tenant_id)

    # 标记内置 data_id 对应的用途（metric/event/...），便于下游消费
    builtin_data_id_usage_map = {
        item["bk_data_id"]: item["usage"] for item in builtin_data_id_items if item["bk_data_id"]
    }

    datasource_items = _values(
        datasource_queryset,
        [
            "bk_data_id",
            "bk_tenant_id",
            "data_name",
            "etl_config",
            "source_label",
            "type_label",
            "source_system",
            "is_enable",
            "is_platform_data_id",
            "space_type_id",
            "space_uid",
            "created_from",
            "transfer_cluster_id",
        ],
        ["bk_data_id"],
    )
    for item in datasource_items:
        item["builtin_usage"] = builtin_data_id_usage_map.get(item["bk_data_id"], "")

    # 联邦集群拓扑
    fed_by_host = list(
        models.BcsFederalClusterInfo.objects.filter(host_cluster_id=cluster.cluster_id).order_by(
            "fed_cluster_id", "sub_cluster_id"
        )
    )
    fed_by_sub = list(
        models.BcsFederalClusterInfo.objects.filter(sub_cluster_id=cluster.cluster_id).order_by(
            "fed_cluster_id", "host_cluster_id"
        )
    )
    fed_by_fed = list(
        models.BcsFederalClusterInfo.objects.filter(fed_cluster_id=cluster.cluster_id).order_by(
            "host_cluster_id", "sub_cluster_id"
        )
    )

    cluster_info = {
        "cluster_id": cluster.cluster_id,
        "bcs_api_cluster_id": cluster.bcs_api_cluster_id,
        "bk_biz_id": cluster.bk_biz_id,
        "bk_tenant_id": cluster.bk_tenant_id,
        "bk_cloud_id": cluster.bk_cloud_id,
        "project_id": cluster.project_id,
        "status": cluster.status,
        "domain_name": cluster.domain_name,
        "port": cluster.port,
        "server_address_path": cluster.server_address_path,
        "bk_env": cluster.bk_env or "",
        "operator_ns": cluster.operator_ns,
        "is_skip_ssl_verify": cluster.is_skip_ssl_verify,
        "is_deleted_allow_view": cluster.is_deleted_allow_view,
        "creator": cluster.creator,
        "create_time": _serialize_value(cluster.create_time),
        "last_modify_user": cluster.last_modify_user,
        "last_modify_time": _serialize_value(cluster.last_modify_time),
    }

    return {
        "query": {
            "bcs_cluster_id": bcs_cluster_id,
            "bk_tenant_id": bk_tenant_id,
            "effective_tenant_id": effective_tenant_id,
        },
        "cluster": cluster_info,
        "bkcc_biz": _serialize_bkcc_biz(bkcc_space, cluster.bk_biz_id),
        "bkci_project": _serialize_bkci_project(bkci_space, cluster.project_id),
        "bkci_to_bkcc_resource": bkci_to_bkcc_resource,
        "federal": _serialize_federal_info(cluster.cluster_id, fed_by_host, fed_by_sub, fed_by_fed),
        "builtin_data_ids": builtin_data_id_items,
        "resolved": {
            "bk_data_ids": sorted(related_data_ids),
            "table_ids": sorted(related_table_ids),
        },
        "data_sources": datasource_items,
        "data_source_result_tables": _values(
            dsrt_queryset,
            ["bk_data_id", "table_id", "bk_tenant_id", "creator", "create_time"],
            ["bk_data_id", "table_id"],
        ),
        "result_tables": _values(
            result_table_queryset,
            [
                "table_id",
                "bk_tenant_id",
                "table_name_zh",
                "default_storage",
                "schema_type",
                "bk_biz_id",
                "is_enable",
                "is_deleted",
                "label",
                "data_label",
                "is_custom_table",
            ],
            ["table_id"],
        ),
        "access_vm_records": sorted(
            access_vm_records,
            key=lambda item: (item.get("result_table_id") or "", item.get("vm_result_table_id") or ""),
        ),
    }
