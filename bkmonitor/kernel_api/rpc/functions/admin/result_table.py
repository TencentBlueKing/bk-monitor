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

from django.db.models import Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    count_by_field,
    get_bk_tenant_id,
    normalize_include,
    normalize_ordering,
    normalize_optional_bool,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_option,
)
from metadata import models

FUNC_RESULT_TABLE_LIST = "admin.result_table.list"
FUNC_RESULT_TABLE_DETAIL = "admin.result_table.detail"
FUNC_RESULT_TABLE_FIELD_LIST = "admin.result_table.field_list"
FUNC_RESULT_TABLE_FIELD_OPTIONS = "admin.result_table.field_options"

RESULT_TABLE_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "bk_biz_id_alias",
    "label",
    "data_label",
    "schema_type",
    "default_storage",
    "is_custom_table",
    "is_builtin",
    "is_enable",
    "is_deleted",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
RESULT_TABLE_DETAIL_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "table_name_zh",
    "bk_biz_id",
    "bk_biz_id_alias",
    "schema_type",
    "default_storage",
    "label",
    "data_label",
    "labels",
    "is_custom_table",
    "is_builtin",
    "is_enable",
    "is_deleted",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
RESULT_TABLE_FIELD_FIELDS = [
    "table_id",
    "bk_tenant_id",
    "field_name",
    "field_type",
    "description",
    "unit",
    "tag",
    "is_config_by_user",
    "default_value",
    "alias_name",
    "is_disabled",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
RESULT_TABLE_ORDERING_FIELDS = {
    "table_id",
    "table_name_zh",
    "bk_biz_id",
    "data_label",
    "label",
    "schema_type",
    "default_storage",
    "is_enable",
    "is_deleted",
    "is_builtin",
    "create_time",
    "last_modify_time",
}
FIELD_ORDERING_FIELDS = {
    "field_name",
    "field_type",
    "tag",
    "is_config_by_user",
    "is_disabled",
    "create_time",
    "last_modify_time",
}
DETAIL_INCLUDE_VALUES = {"options", "datasources", "custom_groups", "storages", "vm_records"}


def _require_table_id(params: dict[str, Any]) -> str:
    table_id = str(params.get("table_id") or "").strip()
    if not table_id:
        raise CustomException(message="table_id 为必填项")
    return table_id


def _serialize_result_table(result_table: models.ResultTable) -> dict[str, Any]:
    return serialize_model(result_table, RESULT_TABLE_FIELDS)


def _serialize_result_table_detail(result_table: models.ResultTable) -> dict[str, Any]:
    return serialize_model(result_table, RESULT_TABLE_DETAIL_FIELDS)


def _serialize_result_table_field(field: models.ResultTableField) -> dict[str, Any]:
    return serialize_model(field, RESULT_TABLE_FIELD_FIELDS)


def _serialize_datasource_relation(relation: models.DataSourceResultTable) -> dict[str, Any]:
    return serialize_model(relation, ["bk_data_id", "table_id", "bk_tenant_id", "creator", "create_time"])


def _serialize_datasource(datasource: models.DataSource) -> dict[str, Any]:
    item = serialize_model(
        datasource,
        [
            "bk_data_id",
            "bk_tenant_id",
            "data_name",
            "data_description",
            "type_label",
            "source_label",
            "custom_label",
            "source_system",
            "is_enable",
            "is_custom_source",
            "is_platform_data_id",
            "space_type_id",
            "space_uid",
            "created_from",
        ],
    )
    item["has_token"] = bool(getattr(datasource, "token", ""))
    return item


def _serialize_es_storage(es_storage: models.ESStorage) -> dict[str, Any]:
    return serialize_model(
        es_storage,
        [
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
            "need_create_index",
            "archive_index_days",
        ],
    )


def _serialize_access_vm_record(record: models.AccessVMRecord) -> dict[str, Any]:
    return serialize_model(
        record,
        [
            "id",
            "bk_tenant_id",
            "data_type",
            "result_table_id",
            "bcs_cluster_id",
            "storage_cluster_id",
            "vm_cluster_id",
            "bk_base_data_id",
            "bk_base_data_name",
            "vm_result_table_id",
            "remark",
        ],
    )


def _serialize_custom_group(group: Any, id_field: str, name_field: str) -> dict[str, Any]:
    return serialize_model(
        group,
        [
            id_field,
            name_field,
            "bk_data_id",
            "bk_biz_id",
            "bk_tenant_id",
            "table_id",
            "label",
            "is_enable",
            "is_delete",
            "is_split_measurement",
            "creator",
            "create_time",
            "last_modify_user",
            "last_modify_time",
        ],
    )


def _build_result_table_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("table_id"):
        table_id = str(params["table_id"]).strip()
        queryset = queryset.filter(
            Q(table_id=table_id) | Q(table_id__startswith=table_id) | Q(table_id__contains=table_id)
        )
    if params.get("table_name_zh"):
        queryset = queryset.filter(table_name_zh__contains=str(params["table_name_zh"]).strip())
    if params.get("bk_biz_id") not in (None, ""):
        try:
            queryset = queryset.filter(bk_biz_id=int(params["bk_biz_id"]))
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_biz_id 必须是整数") from error
    if params.get("bk_data_id") not in (None, ""):
        try:
            bk_data_id = int(params["bk_data_id"])
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_data_id 必须是整数") from error
        table_ids = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id
        ).values_list("table_id", flat=True)
        queryset = queryset.filter(table_id__in=table_ids)
    for field in ["data_label", "label", "schema_type", "default_storage"]:
        if params.get(field) not in (None, ""):
            queryset = queryset.filter(**{field: params[field]})
    for field in ["is_enable", "is_deleted", "is_builtin"]:
        field_value = normalize_optional_bool(params.get(field), field)
        if field_value is not None:
            queryset = queryset.filter(**{field: field_value})

    return queryset


def _build_field_queryset(params: dict[str, Any], bk_tenant_id: str, table_id: str):
    queryset = models.ResultTableField.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)

    if params.get("field_name"):
        queryset = queryset.filter(field_name__contains=str(params["field_name"]).strip())
    for field in ["field_type", "tag"]:
        if params.get(field) not in (None, ""):
            queryset = queryset.filter(**{field: params[field]})
    for field in ["is_config_by_user", "is_disabled"]:
        field_value = normalize_optional_bool(params.get(field), field)
        if field_value is not None:
            queryset = queryset.filter(**{field: field_value})
    has_option = normalize_optional_bool(params.get("has_option"), "has_option")
    if has_option is not None:
        field_names_with_options = models.ResultTableFieldOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id
        ).values_list("field_name", flat=True)
        if has_option:
            queryset = queryset.filter(field_name__in=field_names_with_options)
        else:
            queryset = queryset.exclude(field_name__in=field_names_with_options)

    return queryset


def _build_field_summary(bk_tenant_id: str, table_id: str) -> dict[str, int]:
    fields = models.ResultTableField.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
    return {
        "metric_count": fields.filter(tag=models.ResultTableField.FIELD_TAG_METRIC).count(),
        "dimension_count": fields.filter(tag=models.ResultTableField.FIELD_TAG_DIMENSION).count(),
        "timestamp_count": fields.filter(tag=models.ResultTableField.FIELD_TAG_TIMESTAMP).count(),
        "disabled_count": fields.filter(is_disabled=True).count(),
    }


def _build_result_table_summary(bk_tenant_id: str, table_id: str) -> dict[str, int]:
    fields = models.ResultTableField.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
    return {
        "field_count": fields.count(),
        "metric_field_count": fields.filter(tag=models.ResultTableField.FIELD_TAG_METRIC).count(),
        "dimension_field_count": fields.filter(tag=models.ResultTableField.FIELD_TAG_DIMENSION).count(),
        "disabled_field_count": fields.filter(is_disabled=True).count(),
        "datasource_count": models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id
        ).count(),
    }


@KernelRPCRegistry.register(
    FUNC_RESULT_TABLE_LIST,
    summary="Admin 查询 ResultTable 列表",
    description="只读查询 ResultTable，支持受控过滤、白名单排序和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "可选，结果表 ID，支持精确、前缀或受控包含匹配",
        "table_name_zh": "可选，中文名包含匹配",
        "bk_biz_id": "可选，所属业务",
        "bk_data_id": "可选，通过 DataSourceResultTable 关联过滤",
        "data_label": "可选，数据标签",
        "label": "可选，结果表标签",
        "schema_type": "可选，free / dynamic / fixed",
        "default_storage": "可选，默认存储",
        "is_enable": "可选，是否启用",
        "is_deleted": "可选，是否删除",
        "is_builtin": "可选，是否内置",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(RESULT_TABLE_ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20, "ordering": "table_id"},
)
def list_result_tables(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), RESULT_TABLE_ORDERING_FIELDS, default="table_id")

    queryset = _build_result_table_queryset(params, bk_tenant_id).order_by(ordering, "table_id")
    result_tables, total = paginate_queryset(queryset, page=page, page_size=page_size)
    table_ids = [result_table.table_id for result_table in result_tables]

    field_count_map = count_by_field(
        models.ResultTableField, group_field="table_id", values=table_ids, bk_tenant_id=bk_tenant_id
    )
    datasource_count_map = count_by_field(
        models.DataSourceResultTable, group_field="table_id", values=table_ids, bk_tenant_id=bk_tenant_id
    )
    es_storage_table_ids = set(
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).values_list(
            "table_id", flat=True
        )
    )
    vm_record_table_ids = set(
        models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id__in=table_ids).values_list(
            "result_table_id", flat=True
        )
    )
    custom_group_types: dict[str, str] = {}
    for model_cls, group_type in [
        (models.TimeSeriesGroup, "time_series"),
        (models.EventGroup, "event"),
        (models.LogGroup, "log"),
    ]:
        for table_id in model_cls.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).values_list(
            "table_id", flat=True
        ):
            custom_group_types.setdefault(table_id, group_type)

    items = []
    for result_table in result_tables:
        item = _serialize_result_table(result_table)
        item.update(
            {
                "field_count": field_count_map.get(result_table.table_id, 0),
                "datasource_count": datasource_count_map.get(result_table.table_id, 0),
                "has_es_storage": result_table.table_id in es_storage_table_ids,
                "has_vm_record": result_table.table_id in vm_record_table_ids,
                "custom_group_type": custom_group_types.get(result_table.table_id),
            }
        )
        items.append(item)

    return build_response(
        operation="result_table.list",
        func_name=FUNC_RESULT_TABLE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_RESULT_TABLE_DETAIL,
    summary="Admin 查询 ResultTable 详情",
    description="只读查询 ResultTable 详情和关联信息；字段列表不会在详情接口全量返回，请使用 field_list。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，结果表 ID",
        "include": f"可选，展开范围: {', '.join(sorted(DETAIL_INCLUDE_VALUES))}；不支持 fields",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "include": ["datasources", "storages"]},
)
def get_result_table_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    includes = normalize_include(params.get("include"), DETAIL_INCLUDE_VALUES)

    try:
        result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except models.ResultTable.DoesNotExist as error:
        raise CustomException(message=f"未找到 ResultTable: table_id={table_id}") from error

    data: dict[str, Any] = {
        "result_table": _serialize_result_table_detail(result_table),
        "summary": _build_result_table_summary(bk_tenant_id, table_id),
    }

    if "options" in includes:
        data["options"] = [
            serialize_option(option)
            for option in models.ResultTableOption.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id=table_id
            ).order_by("name")
        ]
    if "datasources" in includes:
        relations = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).order_by(
                "bk_data_id"
            )
        )
        bk_data_ids = [relation.bk_data_id for relation in relations]
        datasources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids).order_by(
            "bk_data_id"
        )
        data["datasource_relations"] = [_serialize_datasource_relation(relation) for relation in relations]
        data["datasources"] = [_serialize_datasource(datasource) for datasource in datasources]
    if "custom_groups" in includes:
        data["custom_groups"] = {
            "time_series_groups": [
                _serialize_custom_group(group, "time_series_group_id", "time_series_group_name")
                for group in models.TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id, table_id=table_id
                ).order_by("time_series_group_id")
            ],
            "event_groups": [
                _serialize_custom_group(group, "event_group_id", "event_group_name")
                for group in models.EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).order_by(
                    "event_group_id"
                )
            ],
            "log_groups": [
                _serialize_custom_group(group, "log_group_id", "log_group_name")
                for group in models.LogGroup.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).order_by(
                    "log_group_id"
                )
            ],
        }
    if "storages" in includes:
        data["storages"] = {
            "es": [
                _serialize_es_storage(es_storage)
                for es_storage in models.ESStorage.objects.filter(
                    bk_tenant_id=bk_tenant_id, table_id=table_id
                ).order_by("id")
            ]
        }
    if "vm_records" in includes:
        data["access_vm_records"] = [
            _serialize_access_vm_record(record)
            for record in models.AccessVMRecord.objects.filter(
                bk_tenant_id=bk_tenant_id, result_table_id=table_id
            ).order_by("id")
        ]

    return build_response(
        operation="result_table.detail",
        func_name=FUNC_RESULT_TABLE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=[
            {
                "code": "FIELDS_NOT_INCLUDED",
                "message": "字段数量可能较大，请通过 admin.result_table.field_list 分页查询",
            }
        ],
    )


@KernelRPCRegistry.register(
    FUNC_RESULT_TABLE_FIELD_LIST,
    summary="Admin 分页查询 ResultTableField",
    description="只读分页查询 ResultTableField，支持受控过滤和字段 option 概览。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，结果表 ID",
        "field_name": "可选，字段名包含匹配",
        "field_type": "可选，字段类型",
        "tag": "可选，metric / dimension / timestamp / group 等",
        "is_config_by_user": "可选，是否用户确认字段",
        "is_disabled": "可选，是否禁用",
        "has_option": "可选，是否存在 FieldOption",
        "page": "可选，默认 1",
        "page_size": "可选，默认 50，最大 200",
        "ordering": f"可选，白名单字段: {', '.join(sorted(FIELD_ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "page": 1, "page_size": 50},
)
def list_result_table_fields(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    page, page_size = normalize_pagination(params, default_page_size=50, max_page_size=200)
    ordering = normalize_ordering(params.get("ordering"), FIELD_ORDERING_FIELDS, default="field_name")

    if not models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).exists():
        raise CustomException(message=f"未找到 ResultTable: table_id={table_id}")

    queryset = _build_field_queryset(params, bk_tenant_id, table_id).order_by(ordering, "field_name")
    fields, total = paginate_queryset(queryset, page=page, page_size=page_size)
    field_names = [field.field_name for field in fields]
    option_count_map = count_by_field(
        models.ResultTableFieldOption,
        group_field="field_name",
        values=field_names,
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
    )
    option_map: dict[str, list[dict[str, Any]]] = {}
    if field_names:
        all_options = models.ResultTableFieldOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id, field_name__in=field_names
        ).order_by("field_name", "name")
        for opt in all_options:
            option_map.setdefault(opt.field_name, []).append(serialize_option(opt))

    items = []
    for field in fields:
        item = _serialize_result_table_field(field)
        option_count = option_count_map.get(field.field_name, 0)
        item["option_count"] = option_count
        item["has_option"] = option_count > 0
        item["options"] = option_map.get(field.field_name, [])
        items.append(item)

    return build_response(
        operation="result_table.field_list",
        func_name=FUNC_RESULT_TABLE_FIELD_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "summary": _build_field_summary(bk_tenant_id, table_id),
        },
    )


@KernelRPCRegistry.register(
    FUNC_RESULT_TABLE_FIELD_OPTIONS,
    summary="Admin 查询单个 ResultTableField 及 FieldOption",
    description="只读查询单个字段及其 FieldOption。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "table_id": "必填，结果表 ID",
        "field_name": "必填，字段名",
    },
    example_params={"bk_tenant_id": "system", "table_id": "system.cpu", "field_name": "usage"},
)
def get_result_table_field_options(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    table_id = _require_table_id(params)
    field_name = str(params.get("field_name") or "").strip()
    if not field_name:
        raise CustomException(message="field_name 为必填项")

    try:
        field = models.ResultTableField.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id, field_name=field_name)
    except models.ResultTableField.DoesNotExist as error:
        raise CustomException(
            message=f"未找到 ResultTableField: table_id={table_id}, field_name={field_name}"
        ) from error

    options = [
        serialize_option(option)
        for option in models.ResultTableFieldOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id, field_name=field_name
        ).order_by("name")
    ]

    return build_response(
        operation="result_table.field_options",
        func_name=FUNC_RESULT_TABLE_FIELD_OPTIONS,
        bk_tenant_id=bk_tenant_id,
        data={"field": _serialize_result_table_field(field), "options": options},
    )
