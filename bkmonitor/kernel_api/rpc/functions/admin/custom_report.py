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

from django.db.models import Count

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_optional_bool,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_value,
)
from metadata import models

FUNC_CUSTOM_REPORT_LIST = "admin.custom_report.list"
FUNC_CUSTOM_REPORT_DETAIL = "admin.custom_report.detail"
FUNC_CUSTOM_REPORT_METRIC_LIST = "admin.custom_report.metric_list"

REPORT_TYPE_METRIC = "custom_metric"
REPORT_TYPE_EVENT = "custom_event"
REPORT_TYPE_LOG = "custom_log"
REPORT_TYPES = {REPORT_TYPE_METRIC, REPORT_TYPE_EVENT, REPORT_TYPE_LOG}


def _normalize_report_type(value: Any, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise CustomException(message="report_type 为必填项")
        return None
    report_type = str(value).strip()
    if report_type not in REPORT_TYPES:
        raise CustomException(message=f"不支持的 report_type: {report_type}")
    return report_type


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _serialize_datasource_summary(datasource: models.DataSource | None) -> dict[str, Any] | None:
    if datasource is None:
        return None
    item = serialize_model(
        datasource,
        [
            "bk_data_id",
            "data_name",
            "data_description",
            "bk_tenant_id",
            "type_label",
            "source_label",
            "created_from",
            "is_enable",
            "is_custom_source",
            "is_platform_data_id",
            "space_uid",
            "mq_cluster_id",
            "mq_config_id",
            "transfer_cluster_id",
            "create_time",
            "last_modify_time",
        ],
    )
    item.update(
        {
            "result_table_count": 0,
            "space_count": 0,
            "option_count": 0,
            "has_data_id_config": False,
        }
    )
    return item


def _serialize_result_table_summary(result_table: models.ResultTable | None) -> dict[str, Any] | None:
    if result_table is None:
        return None
    item = serialize_model(
        result_table,
        [
            "table_id",
            "table_name_zh",
            "bk_tenant_id",
            "bk_biz_id",
            "label",
            "data_label",
            "schema_type",
            "default_storage",
            "is_custom_table",
            "is_builtin",
            "is_enable",
            "is_deleted",
            "create_time",
            "last_modify_time",
        ],
    )
    item.update(
        {
            "field_count": 0,
            "datasource_count": 0,
            "has_es_storage": False,
            "has_vm_record": False,
            "custom_group_type": None,
        }
    )
    return item


def _load_datasource_map(bk_tenant_id: str, bk_data_ids: list[int]) -> dict[int, models.DataSource]:
    data_ids = [bk_data_id for bk_data_id in bk_data_ids if bk_data_id]
    if not data_ids:
        return {}
    return {
        datasource.bk_data_id: datasource
        for datasource in models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    }


def _load_result_table_map(bk_tenant_id: str, table_ids: list[str]) -> dict[str, models.ResultTable]:
    normalized_table_ids = [table_id for table_id in table_ids if table_id]
    if not normalized_table_ids:
        return {}
    return {
        result_table.table_id: result_table
        for result_table in models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=normalized_table_ids
        )
    }


def _metric_count_map(group_ids: list[int]) -> dict[int, int]:
    if not group_ids:
        return {}
    return {
        item["group_id"]: item["total"]
        for item in models.TimeSeriesMetric.objects.filter(group_id__in=group_ids)
        .values("group_id")
        .annotate(total=Count("field_id"))
    }


def _serialize_time_series_group(group: models.TimeSeriesGroup, metric_counts: dict[int, int]) -> dict[str, Any]:
    group_id = group.time_series_group_id
    return {
        "report_type": REPORT_TYPE_METRIC,
        "group_id": group_id,
        "group_name": group.time_series_group_name,
        "bk_tenant_id": group.bk_tenant_id,
        "bk_biz_id": group.bk_biz_id,
        "bk_data_id": group.bk_data_id,
        "table_id": group.table_id,
        "data_label": getattr(group, "data_label", None),
        "created_from": None,
        "is_enable": group.is_enable,
        "metric_count": metric_counts.get(group_id, 0),
        "field_count": 0,
        "monitor_web_source": None,
        "last_modify_time": serialize_value(group.last_modify_time),
    }


def _serialize_event_group(group: models.EventGroup) -> dict[str, Any]:
    return {
        "report_type": REPORT_TYPE_EVENT,
        "group_id": group.event_group_id,
        "group_name": group.event_group_name,
        "bk_tenant_id": group.bk_tenant_id,
        "bk_biz_id": group.bk_biz_id,
        "bk_data_id": group.bk_data_id,
        "table_id": group.table_id,
        "data_label": None,
        "created_from": None,
        "is_enable": group.is_enable,
        "metric_count": 0,
        "field_count": len(getattr(group, "STORAGE_FIELD_LIST", []) or []),
        "monitor_web_source": None,
        "last_modify_time": serialize_value(group.last_modify_time),
    }


def _first_result_table_id(bk_tenant_id: str, bk_data_id: int) -> str | None:
    return (
        models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
        .order_by("table_id")
        .values_list("table_id", flat=True)
        .first()
    )


def _serialize_log_datasource(datasource: models.DataSource) -> dict[str, Any]:
    return {
        "report_type": REPORT_TYPE_LOG,
        "group_id": datasource.bk_data_id,
        "group_name": datasource.data_name,
        "bk_tenant_id": datasource.bk_tenant_id,
        "bk_biz_id": getattr(datasource, "bk_biz_id", None),
        "bk_data_id": datasource.bk_data_id,
        "table_id": _first_result_table_id(datasource.bk_tenant_id, datasource.bk_data_id),
        "data_label": None,
        "created_from": datasource.created_from,
        "is_enable": datasource.is_enable,
        "metric_count": 0,
        "field_count": 0,
        "monitor_web_source": None,
        "last_modify_time": serialize_value(datasource.last_modify_time),
    }


def _build_metric_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    if bk_data_id is not None:
        queryset = queryset.filter(bk_data_id=bk_data_id)
    table_id = str(params.get("table_id") or "").strip()
    if table_id:
        queryset = queryset.filter(table_id__icontains=table_id)
    group_name = str(params.get("group_name") or "").strip()
    if group_name:
        queryset = queryset.filter(time_series_group_name__icontains=group_name)
    return queryset


def _build_event_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    if bk_data_id is not None:
        queryset = queryset.filter(bk_data_id=bk_data_id)
    table_id = str(params.get("table_id") or "").strip()
    if table_id:
        queryset = queryset.filter(table_id__icontains=table_id)
    group_name = str(params.get("group_name") or "").strip()
    if group_name:
        queryset = queryset.filter(event_group_name__icontains=group_name)
    return queryset


def _build_log_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        is_custom_source=True,
        type_label__icontains="log",
    )
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    if bk_data_id is not None:
        queryset = queryset.filter(bk_data_id=bk_data_id)
    group_name = str(params.get("group_name") or "").strip()
    if group_name:
        queryset = queryset.filter(data_name__icontains=group_name)
    table_id = str(params.get("table_id") or "").strip()
    if table_id:
        bk_data_ids = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__icontains=table_id
        ).values_list("bk_data_id", flat=True)
        queryset = queryset.filter(bk_data_id__in=bk_data_ids)
    created_from = str(params.get("created_from") or "").strip()
    if created_from:
        queryset = queryset.filter(created_from=created_from)
    return queryset


@KernelRPCRegistry.register(
    FUNC_CUSTOM_REPORT_LIST,
    summary="Admin 查询自定义上报列表",
    description="只读分页查询自定义指标、自定义事件和日志类自定义上报资源。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "report_type": "可选，custom_metric / custom_event / custom_log",
        "bk_biz_id": "可选，业务 ID",
        "bk_data_id": "可选，DataId",
        "table_id": "可选，结果表 ID 包含匹配",
        "group_name": "可选，名称包含匹配",
        "created_from": "可选，创建来源",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "report_type": "custom_metric", "page": 1, "page_size": 20},
)
def list_custom_reports(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    report_type = _normalize_report_type(params.get("report_type")) or REPORT_TYPE_METRIC
    page, page_size = normalize_pagination(params)

    if report_type == REPORT_TYPE_METRIC:
        queryset = _build_metric_queryset(params, bk_tenant_id).order_by("-last_modify_time", "time_series_group_id")
        groups, total = paginate_queryset(queryset, page=page, page_size=page_size)
        metric_counts = _metric_count_map([group.time_series_group_id for group in groups])
        items = [_serialize_time_series_group(group, metric_counts) for group in groups]
    elif report_type == REPORT_TYPE_EVENT:
        queryset = _build_event_queryset(params, bk_tenant_id).order_by("-last_modify_time", "event_group_id")
        groups, total = paginate_queryset(queryset, page=page, page_size=page_size)
        items = [_serialize_event_group(group) for group in groups]
    else:
        queryset = _build_log_queryset(params, bk_tenant_id).order_by("-last_modify_time", "bk_data_id")
        datasources, total = paginate_queryset(queryset, page=page, page_size=page_size)
        items = [_serialize_log_datasource(datasource) for datasource in datasources]

    return build_response(
        operation="custom_report.list",
        func_name=FUNC_CUSTOM_REPORT_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_CUSTOM_REPORT_DETAIL,
    summary="Admin 查询自定义上报详情",
    description="只读查询单个自定义上报详情及关联 DataSource / ResultTable 摘要。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "report_type": "必填，custom_metric / custom_event / custom_log",
        "group_id": "必填，分组 ID；custom_log 暂以 bk_data_id 作为 group_id",
    },
    example_params={"bk_tenant_id": "system", "report_type": "custom_metric", "group_id": 1},
)
def get_custom_report_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    report_type = _normalize_report_type(params.get("report_type"), required=True)
    group_id = _normalize_int(params.get("group_id"), "group_id", required=True)

    if report_type == REPORT_TYPE_METRIC:
        try:
            group = models.TimeSeriesGroup.objects.get(
                bk_tenant_id=bk_tenant_id, time_series_group_id=group_id, is_delete=False
            )
        except models.TimeSeriesGroup.DoesNotExist as error:
            raise CustomException(message=f"未找到 TimeSeriesGroup: group_id={group_id}") from error
        report = _serialize_time_series_group(group, _metric_count_map([group.time_series_group_id]))
        report.update({"description": None, "token": None, "status": None})
    elif report_type == REPORT_TYPE_EVENT:
        try:
            group = models.EventGroup.objects.get(bk_tenant_id=bk_tenant_id, event_group_id=group_id, is_delete=False)
        except models.EventGroup.DoesNotExist as error:
            raise CustomException(message=f"未找到 EventGroup: group_id={group_id}") from error
        report = _serialize_event_group(group)
        report.update({"description": None, "token": None, "status": group.status})
    else:
        try:
            datasource = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=group_id)
        except models.DataSource.DoesNotExist as error:
            raise CustomException(message=f"未找到日志自定义上报 DataSource: bk_data_id={group_id}") from error
        report = _serialize_log_datasource(datasource)
        report.update({"description": datasource.data_description, "token": None, "status": None})

    datasource = _load_datasource_map(bk_tenant_id, [report["bk_data_id"]]).get(report["bk_data_id"])
    result_table = _load_result_table_map(bk_tenant_id, [report["table_id"]]).get(report["table_id"])
    event_fields = []
    if report_type == REPORT_TYPE_EVENT:
        event_fields = list(getattr(models.EventGroup, "STORAGE_FIELD_LIST", []) or [])

    return build_response(
        operation="custom_report.detail",
        func_name=FUNC_CUSTOM_REPORT_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "report": report,
            "datasource": _serialize_datasource_summary(datasource),
            "result_table": _serialize_result_table_summary(result_table),
            "monitor_web_relation": None,
            "event_fields": event_fields,
            "warnings": [],
        },
    )


@KernelRPCRegistry.register(
    FUNC_CUSTOM_REPORT_METRIC_LIST,
    summary="Admin 分页查询自定义指标字段",
    description="只读分页查询 TimeSeriesMetric，避免在详情页一次性返回大量指标。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "group_id": "必填，TimeSeriesGroup ID",
        "field_name": "可选，指标名包含匹配",
        "is_active": "可选，是否活跃",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 200",
    },
    example_params={"bk_tenant_id": "system", "group_id": 1, "page": 1, "page_size": 20},
)
def list_custom_report_metrics(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    group_id = _normalize_int(params.get("group_id"), "group_id", required=True)
    page, page_size = normalize_pagination(params, default_page_size=20, max_page_size=200)

    if not models.TimeSeriesGroup.objects.filter(
        bk_tenant_id=bk_tenant_id, time_series_group_id=group_id, is_delete=False
    ).exists():
        raise CustomException(message=f"未找到 TimeSeriesGroup: group_id={group_id}")

    queryset = models.TimeSeriesMetric.objects.filter(group_id=group_id)
    field_name = str(params.get("field_name") or "").strip()
    if field_name:
        queryset = queryset.filter(field_name__icontains=field_name)
    is_active = normalize_optional_bool(params.get("is_active"), "is_active")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    metrics, total = paginate_queryset(queryset.order_by("field_name", "field_scope"), page=page, page_size=page_size)
    items = [
        {
            "field_name": metric.field_name,
            "table_id": metric.table_id,
            "description": metric.field_config.get("alias") if isinstance(metric.field_config, dict) else "",
            "unit": metric.field_config.get("unit") if isinstance(metric.field_config, dict) else "",
            "type": "float",
            "is_active": metric.is_active,
            "last_modify_time": serialize_value(metric.last_modify_time),
        }
        for metric in metrics
    ]

    return build_response(
        operation="custom_report.metric_list",
        func_name=FUNC_CUSTOM_REPORT_METRIC_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )
