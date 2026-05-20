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
from decimal import Decimal
from typing import Any

from django.db.models import Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_value,
)
from metadata import models

FUNC_DORIS_STORAGE_LIST = "admin.doris_storage.list"
FUNC_DORIS_STORAGE_DETAIL = "admin.doris_storage.detail"
FUNC_DORIS_STORAGE_PHYSICAL_METADATA = "admin.doris_storage.physical_metadata"
FUNC_DORIS_STORAGE_LATEST_RECORDS = "admin.doris_storage.latest_records"
FUNC_VM_STORAGE_LIST = "admin.vm_storage.list"
FUNC_VM_STORAGE_DETAIL = "admin.vm_storage.detail"
FUNC_KAFKA_STORAGE_LIST = "admin.kafka_storage.list"
FUNC_KAFKA_STORAGE_DETAIL = "admin.kafka_storage.detail"
FUNC_BKBASE_RESULT_TABLE_LIST = "admin.bkbase_result_table.list"
FUNC_BKBASE_RESULT_TABLE_DETAIL = "admin.bkbase_result_table.detail"
INSPECT_SAFETY_LEVEL = "inspect"

RESULT_TABLE_SUMMARY_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "data_label",
    "default_storage",
    "is_enable",
    "is_deleted",
]
CLUSTER_SUMMARY_FIELDS = ["cluster_id", "cluster_name", "display_name", "cluster_type"]
DORIS_STORAGE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "bkbase_table_id",
    "source_type",
    "index_set",
    "table_type",
    "field_config_mapping",
    "expire_days",
    "storage_cluster_id",
]
KAFKA_STORAGE_FIELDS = ["id", "table_id", "bk_tenant_id", "topic", "partition", "storage_cluster_id", "retention"]
ACCESS_VM_RECORD_FIELDS = [
    "id",
    "data_type",
    "result_table_id",
    "bcs_cluster_id",
    "storage_cluster_id",
    "vm_cluster_id",
    "bk_base_data_id",
    "bk_base_data_name",
    "vm_result_table_id",
    "remark",
    "bk_tenant_id",
]
BKBASE_RESULT_TABLE_FIELDS = [
    "data_link_name",
    "bkbase_data_name",
    "storage_type",
    "monitor_table_id",
    "storage_cluster_id",
    "create_time",
    "last_modify_time",
    "status",
    "bkbase_table_id",
    "bkbase_rt_name",
    "bk_tenant_id",
]
DORIS_ORDERING_FIELDS = {"table_id", "storage_cluster_id"}
KAFKA_ORDERING_FIELDS = {"table_id", "storage_cluster_id"}
VM_ORDERING_FIELDS = {"result_table_id", "storage_cluster_id"}
BKBASE_ORDERING_FIELDS = {"monitor_table_id", "storage_cluster_id", "status", "create_time", "last_modify_time"}


def _parse_int_param(params: dict[str, Any], field: str) -> int | None:
    value = params.get(field)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field} 必须是整数") from error


def _parse_positive_int_param(params: dict[str, Any], field: str, *, default: int, maximum: int) -> int:
    value = params.get(field)
    if value in (None, ""):
        return default
    try:
        normalized_value = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field} 必须是整数") from error
    if normalized_value < 1:
        raise CustomException(message=f"{field} 必须大于等于 1")
    return min(normalized_value, maximum)


def _parse_json_field(value: Any, warnings: list[dict[str, Any]], *, field: str, table_id: str) -> Any:
    if value in (None, "") or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError) as error:
        warnings.append(
            {
                "code": "STORAGE_JSON_PARSE_FAILED",
                "message": f"{field} 不是合法 JSON，已返回原始值: table_id={table_id}",
                "details": {"field": field, "error": str(error)},
            }
        )
        return value


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _serialize_runtime_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize_runtime_payload(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_serialize_runtime_payload(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return serialize_value(value)


def _require_doris_table_id(params: dict[str, Any]) -> str:
    table_id = str(params.get("table_id") or "").strip()
    if not table_id:
        raise CustomException(message="table_id 为必填项")
    return table_id


def _get_doris_storage_or_raise(bk_tenant_id: str, table_id: str) -> Any:
    try:
        return models.DorisStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except models.DorisStorage.DoesNotExist as error:
        raise CustomException(message=f"未找到 DorisStorage: table_id={table_id}") from error


def _table_ids_by_data_filters(params: dict[str, Any], bk_tenant_id: str) -> set[str] | None:
    filters: dict[str, Any] = {}
    if params.get("data_label") not in (None, ""):
        filters["data_label"] = str(params["data_label"]).strip()
    if params.get("bk_data_id") not in (None, ""):
        bk_data_id = _parse_int_param(params, "bk_data_id")
        relation_table_ids = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id
        ).values_list("table_id", flat=True)
        filters["table_id__in"] = relation_table_ids
    if not filters:
        return None
    return set(
        models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, **filters).values_list("table_id", flat=True)
    )


def _serialize_result_table(result_table: Any | None) -> dict[str, Any] | None:
    return serialize_model(result_table, RESULT_TABLE_SUMMARY_FIELDS) if result_table else None


def _serialize_cluster(cluster: Any | None) -> dict[str, Any] | None:
    return serialize_model(cluster, CLUSTER_SUMMARY_FIELDS) if cluster else None


def _load_result_table_map(bk_tenant_id: str, table_ids: list[str | None]) -> dict[str, Any]:
    normalized_table_ids = [table_id for table_id in table_ids if table_id]
    if not normalized_table_ids:
        return {}
    return {
        result_table.table_id: result_table
        for result_table in models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=normalized_table_ids
        )
    }


def _load_cluster_map(bk_tenant_id: str, cluster_ids: list[int | None]) -> dict[int, Any]:
    normalized_cluster_ids = [cluster_id for cluster_id in cluster_ids if cluster_id not in (None, "")]
    if not normalized_cluster_ids:
        return {}
    return {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_id__in=normalized_cluster_ids
        )
    }


def _table_id_filter(queryset: Any, table_id: str, field: str = "table_id") -> Any:
    if not table_id:
        return queryset
    return queryset.filter(
        Q(**{field: table_id}) | Q(**{f"{field}__startswith": table_id}) | Q(**{f"{field}__contains": table_id})
    )


def _base_storage_queryset(model_cls: Any, params: dict[str, Any], bk_tenant_id: str, table_field: str = "table_id"):
    queryset = model_cls.objects.filter(bk_tenant_id=bk_tenant_id)
    queryset = _table_id_filter(queryset, str(params.get("table_id") or "").strip(), table_field)
    table_ids = _table_ids_by_data_filters(params, bk_tenant_id)
    if table_ids is not None:
        queryset = queryset.filter(**{f"{table_field}__in": table_ids})
    storage_cluster_id = _parse_int_param(params, "storage_cluster_id")
    if storage_cluster_id is not None:
        queryset = queryset.filter(storage_cluster_id=storage_cluster_id)
    return queryset


def _serialize_doris_storage(storage: Any, warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    item = serialize_model(storage, DORIS_STORAGE_FIELDS)
    if warnings is not None:
        item["field_config_mapping"] = _parse_json_field(
            item.get("field_config_mapping"), warnings, field="field_config_mapping", table_id=item["table_id"]
        )
    return item


def _serialize_doris_item(
    storage: Any, result_table_map: dict[str, Any], cluster_map: dict[int, Any]
) -> dict[str, Any]:
    return {
        "doris_storage": _serialize_doris_storage(storage),
        "result_table": _serialize_result_table(result_table_map.get(storage.table_id)),
        "storage_cluster": _serialize_cluster(cluster_map.get(storage.storage_cluster_id)),
    }


def _serialize_kafka_item(
    storage: Any, result_table_map: dict[str, Any], cluster_map: dict[int, Any]
) -> dict[str, Any]:
    return {
        "kafka_storage": serialize_model(storage, KAFKA_STORAGE_FIELDS),
        "result_table": _serialize_result_table(result_table_map.get(storage.table_id)),
        "storage_cluster": _serialize_cluster(cluster_map.get(storage.storage_cluster_id)),
    }


def _serialize_vm_item(record: Any, result_table_map: dict[str, Any], cluster_map: dict[int, Any]) -> dict[str, Any]:
    return {
        "access_vm_record": serialize_model(record, ACCESS_VM_RECORD_FIELDS),
        "result_table": _serialize_result_table(result_table_map.get(record.result_table_id)),
        "storage_cluster": _serialize_cluster(cluster_map.get(record.storage_cluster_id)),
    }


def _serialize_bkbase_item(
    record: Any, result_table_map: dict[str, Any], cluster_map: dict[int, Any]
) -> dict[str, Any]:
    return {
        "bkbase_result_table": serialize_model(record, BKBASE_RESULT_TABLE_FIELDS),
        "result_table": _serialize_result_table(result_table_map.get(record.monitor_table_id)),
        "storage_cluster": _serialize_cluster(cluster_map.get(record.storage_cluster_id)),
    }


def _paginate_list_response(
    *,
    params: dict[str, Any],
    queryset: Any,
    bk_tenant_id: str,
    operation: str,
    func_name: str,
    table_id_getter,
    cluster_id_getter,
    serializer,
    default_ordering: str,
    ordering_fields: set[str],
) -> dict[str, Any]:
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ordering_fields, default=default_ordering)
    rows, total = paginate_queryset(queryset.order_by(ordering), page=page, page_size=page_size)
    result_table_map = _load_result_table_map(bk_tenant_id, [table_id_getter(row) for row in rows])
    cluster_map = _load_cluster_map(bk_tenant_id, [cluster_id_getter(row) for row in rows])
    items = [serializer(row, result_table_map, cluster_map) for row in rows]
    return build_response(
        operation=operation,
        func_name=func_name,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_DORIS_STORAGE_LIST,
    summary="Admin 查询 DorisStorage 列表",
    description="只读分页查询 DorisStorage，字段按 DorisStorage 模型原样返回。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，DorisStorage.table_id",
        "bk_data_id": "可选，通过 DataSourceResultTable 关联过滤",
        "data_label": "可选，通过 ResultTable.data_label 关联过滤",
        "storage_cluster_id": "可选，Doris 集群 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": "可选，table_id / storage_cluster_id",
    },
    example_params={"bk_tenant_id": "system", "table_id": "3_bklog.demo", "page": 1, "page_size": 20},
)
def list_doris_storages(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    queryset = _base_storage_queryset(models.DorisStorage, params, bk_tenant_id)
    return _paginate_list_response(
        params=params,
        queryset=queryset,
        bk_tenant_id=bk_tenant_id,
        operation="doris_storage.list",
        func_name=FUNC_DORIS_STORAGE_LIST,
        table_id_getter=lambda row: row.table_id,
        cluster_id_getter=lambda row: row.storage_cluster_id,
        serializer=_serialize_doris_item,
        default_ordering="table_id",
        ordering_fields=DORIS_ORDERING_FIELDS,
    )


@KernelRPCRegistry.register(
    FUNC_DORIS_STORAGE_DETAIL,
    summary="Admin 查询 DorisStorage 详情",
    description="只读查询 DorisStorage 原始配置、ResultTable 和 ClusterInfo。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "table_id": "必填，DorisStorage.table_id"},
    example_params={"bk_tenant_id": "system", "table_id": "3_bklog.demo"},
)
def get_doris_storage_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_doris_table_id(params)
    storage = _get_doris_storage_or_raise(bk_tenant_id, table_id)
    warnings: list[dict[str, Any]] = []
    data = _serialize_doris_item(
        storage,
        _load_result_table_map(bk_tenant_id, [storage.table_id]),
        _load_cluster_map(bk_tenant_id, [storage.storage_cluster_id]),
    )
    data["doris_storage"] = _serialize_doris_storage(storage, warnings)
    return build_response(
        operation="doris_storage.detail",
        func_name=FUNC_DORIS_STORAGE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_DORIS_STORAGE_PHYSICAL_METADATA,
    summary="Admin 查询 DorisStorage 物理表元信息",
    description="inspect 级别能力，查询 DorisStorage 关联 DorisBinding 和真实 Doris 物理表 information_schema / SHOW CREATE TABLE。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "table_id": "必填，DorisStorage.table_id"},
    example_params={"bk_tenant_id": "system", "table_id": "3_bklog.demo"},
)
def get_doris_storage_physical_metadata(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_doris_table_id(params)
    storage = _get_doris_storage_or_raise(bk_tenant_id, table_id)
    data = _serialize_runtime_payload(storage.query_physical_storage_metadata())
    response = build_response(
        operation="doris_storage.physical_metadata",
        func_name=FUNC_DORIS_STORAGE_PHYSICAL_METADATA,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=data.get("warnings") if isinstance(data, dict) else [],
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_DORIS_STORAGE_LATEST_RECORDS,
    summary="Admin 查询 DorisStorage 物理表最新样例数据",
    description="inspect 级别能力，按指定排序字段从 DorisStorage 关联真实 Doris 物理表抽样最新记录。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，DorisStorage.table_id",
        "limit": "可选，默认 1，最大 100",
        "order_field": "可选，默认 dtEventTimeStamp",
    },
    example_params={"bk_tenant_id": "system", "table_id": "3_bklog.demo", "limit": 1},
)
def get_doris_storage_latest_records(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_doris_table_id(params)
    limit = _parse_positive_int_param(params, "limit", default=1, maximum=100)
    order_field = str(params.get("order_field") or "dtEventTimeStamp").strip()
    if not order_field:
        raise CustomException(message="order_field 不能为空")
    storage = _get_doris_storage_or_raise(bk_tenant_id, table_id)
    data = _serialize_runtime_payload(
        storage.query_latest_physical_storage_records(limit=limit, order_field=order_field)
    )
    response = build_response(
        operation="doris_storage.latest_records",
        func_name=FUNC_DORIS_STORAGE_LATEST_RECORDS,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=data.get("warnings") if isinstance(data, dict) else [],
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_VM_STORAGE_LIST,
    summary="Admin 查询 AccessVMRecord 列表",
    description="只读分页查询 AccessVMRecord，字段按 VM 接入记录模型原样返回。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，匹配 result_table_id / vm_result_table_id",
        "bk_data_id": "可选，通过 DataSourceResultTable 关联过滤",
        "data_label": "可选，通过 ResultTable.data_label 关联过滤",
        "storage_cluster_id": "可选，VM 接入存储集群 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "table_id": "2_bkmonitor_time_series.__default__"},
)
def list_vm_storages(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    queryset = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id)
    table_id = str(params.get("table_id") or "").strip()
    if table_id:
        queryset = queryset.filter(
            Q(result_table_id=table_id)
            | Q(result_table_id__startswith=table_id)
            | Q(result_table_id__contains=table_id)
            | Q(vm_result_table_id=table_id)
            | Q(vm_result_table_id__startswith=table_id)
            | Q(vm_result_table_id__contains=table_id)
        )
    table_ids = _table_ids_by_data_filters(params, bk_tenant_id)
    if table_ids is not None:
        queryset = queryset.filter(result_table_id__in=table_ids)
    storage_cluster_id = _parse_int_param(params, "storage_cluster_id")
    if storage_cluster_id is not None:
        queryset = queryset.filter(storage_cluster_id=storage_cluster_id)
    return _paginate_list_response(
        params=params,
        queryset=queryset,
        bk_tenant_id=bk_tenant_id,
        operation="vm_storage.list",
        func_name=FUNC_VM_STORAGE_LIST,
        table_id_getter=lambda row: row.result_table_id,
        cluster_id_getter=lambda row: row.storage_cluster_id,
        serializer=_serialize_vm_item,
        default_ordering="result_table_id",
        ordering_fields=VM_ORDERING_FIELDS,
    )


@KernelRPCRegistry.register(
    FUNC_VM_STORAGE_DETAIL,
    summary="Admin 查询 AccessVMRecord 详情",
    description="只读查询 AccessVMRecord 原始记录、ResultTable 和 ClusterInfo。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，AccessVMRecord.id"},
    example_params={"bk_tenant_id": "system", "id": 1},
)
def get_vm_storage_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    record_id = _parse_int_param(params, "id")
    if record_id is None:
        raise CustomException(message="id 为必填项")
    try:
        record = models.AccessVMRecord.objects.get(bk_tenant_id=bk_tenant_id, id=record_id)
    except models.AccessVMRecord.DoesNotExist as error:
        raise CustomException(message=f"未找到 AccessVMRecord: id={record_id}") from error
    data = _serialize_vm_item(
        record,
        _load_result_table_map(bk_tenant_id, [record.result_table_id]),
        _load_cluster_map(bk_tenant_id, [record.storage_cluster_id]),
    )
    return build_response(
        operation="vm_storage.detail",
        func_name=FUNC_VM_STORAGE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )


@KernelRPCRegistry.register(
    FUNC_KAFKA_STORAGE_LIST,
    summary="Admin 查询 KafkaStorage 列表",
    description="只读分页查询 KafkaStorage，字段按 KafkaStorage 模型原样返回。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，KafkaStorage.table_id",
        "bk_data_id": "可选，通过 DataSourceResultTable 关联过滤",
        "data_label": "可选，通过 ResultTable.data_label 关联过滤",
        "storage_cluster_id": "可选，Kafka 集群 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": "可选，table_id / storage_cluster_id",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu"},
)
def list_kafka_storages(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    queryset = _base_storage_queryset(models.KafkaStorage, params, bk_tenant_id)
    return _paginate_list_response(
        params=params,
        queryset=queryset,
        bk_tenant_id=bk_tenant_id,
        operation="kafka_storage.list",
        func_name=FUNC_KAFKA_STORAGE_LIST,
        table_id_getter=lambda row: row.table_id,
        cluster_id_getter=lambda row: row.storage_cluster_id,
        serializer=_serialize_kafka_item,
        default_ordering="table_id",
        ordering_fields=KAFKA_ORDERING_FIELDS,
    )


@KernelRPCRegistry.register(
    FUNC_KAFKA_STORAGE_DETAIL,
    summary="Admin 查询 KafkaStorage 详情",
    description="只读查询 KafkaStorage 原始配置、ResultTable 和 ClusterInfo。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "table_id": "必填，KafkaStorage.table_id"},
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu"},
)
def get_kafka_storage_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = str(params.get("table_id") or "").strip()
    if not table_id:
        raise CustomException(message="table_id 为必填项")
    try:
        storage = models.KafkaStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except models.KafkaStorage.DoesNotExist as error:
        raise CustomException(message=f"未找到 KafkaStorage: table_id={table_id}") from error
    data = _serialize_kafka_item(
        storage,
        _load_result_table_map(bk_tenant_id, [storage.table_id]),
        _load_cluster_map(bk_tenant_id, [storage.storage_cluster_id]),
    )
    return build_response(
        operation="kafka_storage.detail",
        func_name=FUNC_KAFKA_STORAGE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )


@KernelRPCRegistry.register(
    FUNC_BKBASE_RESULT_TABLE_LIST,
    summary="Admin 查询 BkBaseResultTable 列表",
    description="只读分页查询 BkBaseResultTable，字段按 BKBase 链路回填模型原样返回。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，匹配 monitor_table_id / bkbase_table_id / data_link_name",
        "bk_data_id": "可选，通过 DataSourceResultTable 关联过滤",
        "data_label": "可选，通过 ResultTable.data_label 关联过滤",
        "storage_cluster_id": "可选，存储集群 ID",
        "status": "可选，BkBaseResultTable.status",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": "可选，table_id / storage_cluster_id / status / create_time / last_modify_time",
    },
    example_params={"bk_tenant_id": "system", "status": "Ok", "page": 1, "page_size": 20},
)
def list_bkbase_result_tables(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    queryset = models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id)
    table_id = str(params.get("table_id") or "").strip()
    if table_id:
        queryset = queryset.filter(
            Q(monitor_table_id=table_id)
            | Q(monitor_table_id__startswith=table_id)
            | Q(monitor_table_id__contains=table_id)
            | Q(bkbase_table_id=table_id)
            | Q(bkbase_table_id__startswith=table_id)
            | Q(bkbase_table_id__contains=table_id)
            | Q(data_link_name=table_id)
            | Q(data_link_name__startswith=table_id)
            | Q(data_link_name__contains=table_id)
        )
    table_ids = _table_ids_by_data_filters(params, bk_tenant_id)
    if table_ids is not None:
        queryset = queryset.filter(monitor_table_id__in=table_ids)
    storage_cluster_id = _parse_int_param(params, "storage_cluster_id")
    if storage_cluster_id is not None:
        queryset = queryset.filter(storage_cluster_id=storage_cluster_id)
    if params.get("status") not in (None, ""):
        queryset = queryset.filter(status=str(params["status"]).strip())
    ordering = params.get("ordering")
    if ordering in ("table_id", "-table_id"):
        params = {**params, "ordering": str(ordering).replace("table_id", "monitor_table_id")}
    return _paginate_list_response(
        params=params,
        queryset=queryset,
        bk_tenant_id=bk_tenant_id,
        operation="bkbase_result_table.list",
        func_name=FUNC_BKBASE_RESULT_TABLE_LIST,
        table_id_getter=lambda row: row.monitor_table_id,
        cluster_id_getter=lambda row: row.storage_cluster_id,
        serializer=_serialize_bkbase_item,
        default_ordering="monitor_table_id",
        ordering_fields=BKBASE_ORDERING_FIELDS,
    )


@KernelRPCRegistry.register(
    FUNC_BKBASE_RESULT_TABLE_DETAIL,
    summary="Admin 查询 BkBaseResultTable 详情",
    description="只读查询 BkBaseResultTable 原始记录、ResultTable、ClusterInfo 和 DataLink 组件计数。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "data_link_name": "必填，BkBaseResultTable.data_link_name"},
    example_params={"bk_tenant_id": "system", "data_link_name": "bk_log"},
)
def get_bkbase_result_table_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    data_link_name = str(params.get("data_link_name") or "").strip()
    if not data_link_name:
        raise CustomException(message="data_link_name 为必填项")
    try:
        record = models.BkBaseResultTable.objects.get(bk_tenant_id=bk_tenant_id, data_link_name=data_link_name)
    except models.BkBaseResultTable.DoesNotExist as error:
        raise CustomException(message=f"未找到 BkBaseResultTable: data_link_name={data_link_name}") from error
    data = _serialize_bkbase_item(
        record,
        _load_result_table_map(bk_tenant_id, [record.monitor_table_id]),
        _load_cluster_map(bk_tenant_id, [record.storage_cluster_id]),
    )
    data["relations"] = {
        "datalink_components": [
            {
                "kind": "ResultTableConfig",
                "count": models.ResultTableConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
                ).count(),
            },
            {
                "kind": "DataBusConfig",
                "count": models.DataBusConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
                ).count(),
            },
            {
                "kind": "ESStorageBindingConfig",
                "count": models.ESStorageBindingConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
                ).count(),
            },
            {
                "kind": "VMStorageBindingConfig",
                "count": models.VMStorageBindingConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
                ).count(),
            },
            {
                "kind": "DorisStorageBindingConfig",
                "count": models.DorisStorageBindingConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
                ).count(),
            },
        ]
    }
    return build_response(
        operation="bkbase_result_table.detail",
        func_name=FUNC_BKBASE_RESULT_TABLE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )
