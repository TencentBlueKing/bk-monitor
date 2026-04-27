"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from collections import defaultdict
import json
from typing import Any

from django.db.models import Count

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_pagination,
    serialize_model,
    serialize_value,
)


class _LazyApmModels:
    def __getattr__(self, name: str) -> Any:
        from apm import models as apm_models

        return getattr(apm_models, name)


class _LazyMetadataModels:
    def __getattr__(self, name: str) -> Any:
        from metadata import models as metadata_models

        return getattr(metadata_models, name)


apm_models = _LazyApmModels()
metadata_models = _LazyMetadataModels()

FUNC_APM_APPLICATION_LIST = "admin.apm.application_list"
FUNC_APM_APPLICATION_DETAIL = "admin.apm.application_detail"
FUNC_APM_SERVICE_LIST = "admin.apm.service_list"
FUNC_APM_TOPO = "admin.apm.topo"

DATASOURCE_TYPES = ("metric", "trace", "log", "profile")


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _app_key(application: Any) -> tuple[int, str]:
    return application.bk_biz_id, application.app_name


def _datasource_model(datasource_type: str):
    return {
        "metric": apm_models.MetricDataSource,
        "trace": apm_models.TraceDataSource,
        "log": apm_models.LogDataSource,
        "profile": apm_models.ProfileDataSource,
    }[datasource_type]


def _load_apm_datasource_maps(applications: list[Any]) -> dict[str, dict[tuple[int, str], Any]]:
    keys = {_app_key(application) for application in applications}
    if not keys:
        return {datasource_type: {} for datasource_type in DATASOURCE_TYPES}

    bk_biz_ids = sorted({bk_biz_id for bk_biz_id, _ in keys})
    app_names = sorted({app_name for _, app_name in keys})
    result: dict[str, dict[tuple[int, str], Any]] = {}
    for datasource_type in DATASOURCE_TYPES:
        model_cls = _datasource_model(datasource_type)
        records = model_cls.objects.filter(bk_biz_id__in=bk_biz_ids, app_name__in=app_names)
        result[datasource_type] = {
            (record.bk_biz_id, record.app_name): record
            for record in records
            if (record.bk_biz_id, record.app_name) in keys
        }
    return result


def _load_service_count_map(applications: list[Any]) -> dict[tuple[int, str], int]:
    if not applications:
        return {}
    bk_biz_ids = sorted({application.bk_biz_id for application in applications})
    app_names = sorted({application.app_name for application in applications})
    items = (
        apm_models.TopoNode.objects.filter(bk_biz_id__in=bk_biz_ids, app_name__in=app_names)
        .values("bk_biz_id", "app_name")
        .annotate(total=Count("id"))
    )
    return {(item["bk_biz_id"], item["app_name"]): item["total"] for item in items}


def _application_status(application: Any) -> str:
    if not application.is_enabled:
        return "disabled"
    enabled_types = []
    if application.is_enabled_metric:
        enabled_types.append("metric")
    if application.is_enabled_trace:
        enabled_types.append("trace")
    if application.is_enabled_log:
        enabled_types.append("log")
    if application.is_enabled_profiling:
        enabled_types.append("profile")
    return ",".join(enabled_types) if enabled_types else "enabled"


def _serialize_application_summary(
    application: Any,
    datasource_maps: dict[str, dict[tuple[int, str], Any]],
    service_count_map: dict[tuple[int, str], int],
) -> dict[str, Any]:
    key = _app_key(application)
    metric_datasource = datasource_maps["metric"].get(key)
    trace_datasource = datasource_maps["trace"].get(key)
    log_datasource = datasource_maps["log"].get(key)
    profile_datasource = datasource_maps["profile"].get(key)
    return {
        "application_id": application.id,
        "app_name": application.app_name,
        "app_alias": application.app_alias,
        "bk_tenant_id": application.bk_tenant_id,
        "bk_biz_id": application.bk_biz_id,
        "status": _application_status(application),
        "metric_data_id": getattr(metric_datasource, "bk_data_id", None),
        "trace_data_id": getattr(trace_datasource, "bk_data_id", None),
        "log_data_id": getattr(log_datasource, "bk_data_id", None),
        "profile_data_id": getattr(profile_datasource, "bk_data_id", None),
        "service_count": service_count_map.get(key, 0),
        "topo_node_count": service_count_map.get(key, 0),
        "last_modify_time": serialize_value(application.update_time),
    }


def _serialize_datasource_summary(datasource: Any) -> dict[str, Any]:
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


def _serialize_result_table_summary(result_table: Any) -> dict[str, Any]:
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


def _serialize_custom_metric_group(group: Any, metric_count: int) -> dict[str, Any]:
    return {
        "report_type": "custom_metric",
        "group_id": group.time_series_group_id,
        "group_name": group.time_series_group_name,
        "bk_tenant_id": group.bk_tenant_id,
        "bk_biz_id": group.bk_biz_id,
        "bk_data_id": group.bk_data_id,
        "table_id": group.table_id,
        "data_label": getattr(group, "data_label", None),
        "created_from": None,
        "is_enable": group.is_enable,
        "metric_count": metric_count,
        "field_count": 0,
        "monitor_web_source": None,
        "apm_application_count": 1,
        "last_modify_time": serialize_value(group.last_modify_time),
    }


def _filter_applications_by_datasource_params(applications: list[Any], params: dict[str, Any]):
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    table_id = str(params.get("table_id") or "").strip()
    if bk_data_id is None and not table_id:
        return applications

    datasource_maps = _load_apm_datasource_maps(applications)
    filtered = []
    for application in applications:
        key = _app_key(application)
        datasources = [datasource_maps[datasource_type].get(key) for datasource_type in DATASOURCE_TYPES]
        datasources = [datasource for datasource in datasources if datasource]
        if bk_data_id is not None and not any(datasource.bk_data_id == bk_data_id for datasource in datasources):
            continue
        if table_id and not any(table_id in datasource.result_table_id for datasource in datasources):
            continue
        filtered.append(application)
    return filtered


def _get_application(application_id: Any, bk_tenant_id: str) -> Any:
    normalized_application_id = _normalize_int(application_id, "application_id", required=True)
    try:
        return apm_models.ApmApplication.objects.get(id=normalized_application_id, bk_tenant_id=bk_tenant_id)
    except apm_models.ApmApplication.DoesNotExist as error:
        raise CustomException(message=f"未找到 APM 应用: application_id={normalized_application_id}") from error


def _serialize_topo_node(node: Any) -> dict[str, Any]:
    extra_data = node.extra_data if isinstance(node.extra_data, dict) else {}
    return {
        "topo_key": node.topo_key,
        "kind": extra_data.get("kind"),
        "category": extra_data.get("category"),
        "system": _stringify_json(node.system),
        "platform": _stringify_json(node.platform),
        "updated_at": serialize_value(node.updated_at),
    }


def _stringify_json(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _serialize_topo_relation(relation: Any) -> dict[str, Any]:
    return {
        "from_topo_key": relation.from_topo_key,
        "to_topo_key": relation.to_topo_key,
        "kind": relation.kind,
        "category": relation.to_topo_key_category,
    }


def _serialize_service(node: Any, instance_count_map: dict[str, int]) -> dict[str, Any]:
    extra_data = node.extra_data if isinstance(node.extra_data, dict) else {}
    return {
        "service_name": node.topo_key,
        "topo_key": node.topo_key,
        "kind": extra_data.get("kind"),
        "category": extra_data.get("category"),
        "instance_count": instance_count_map.get(node.topo_key, 0),
        "endpoint_count": 0,
        "last_seen_time": serialize_value(node.updated_at),
    }


def _load_instance_count_map(application: Any, topo_keys: list[str]) -> dict[str, int]:
    if not topo_keys:
        return {}
    items = (
        apm_models.TopoInstance.objects.filter(
            bk_biz_id=application.bk_biz_id,
            app_name=application.app_name,
            topo_node_key__in=topo_keys,
        )
        .values("topo_node_key")
        .annotate(total=Count("id"))
    )
    return {item["topo_node_key"]: item["total"] for item in items}


@KernelRPCRegistry.register(
    FUNC_APM_APPLICATION_LIST,
    summary="Admin 查询 APM 应用列表",
    description="只读分页查询 APM 应用及其核心 DataId 摘要。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "可选，业务 ID",
        "app_name": "可选，应用名或别名包含匹配",
        "status": "可选，状态原始值包含匹配",
        "bk_data_id": "可选，关联 DataId",
        "table_id": "可选，关联 ResultTable ID 包含匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20},
)
def list_apm_applications(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)

    queryset = apm_models.ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id).order_by("-update_time", "id")
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    app_name = str(params.get("app_name") or "").strip()
    if app_name:
        queryset = queryset.filter(app_name__icontains=app_name)

    applications = _filter_applications_by_datasource_params(list(queryset), params)
    status = str(params.get("status") or "").strip()
    if status:
        applications = [application for application in applications if status in _application_status(application)]

    total = len(applications)
    offset = (page - 1) * page_size
    page_applications = applications[offset : offset + page_size]
    datasource_maps = _load_apm_datasource_maps(page_applications)
    service_count_map = _load_service_count_map(page_applications)
    items = [
        _serialize_application_summary(application, datasource_maps, service_count_map)
        for application in page_applications
    ]

    return build_response(
        operation="apm.application_list",
        func_name=FUNC_APM_APPLICATION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_APM_APPLICATION_DETAIL,
    summary="Admin 查询 APM 应用详情",
    description="只读查询 APM 应用、DataSource、ResultTable、自定义上报与拓扑摘要。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "application_id": "必填，APM 应用 ID",
        "include": "可选，保留参数；当前返回轻量摘要",
    },
    example_params={"bk_tenant_id": "system", "application_id": 1},
)
def get_apm_application_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    application = _get_application(params.get("application_id"), bk_tenant_id)
    datasource_maps = _load_apm_datasource_maps([application])
    service_count_map = _load_service_count_map([application])
    application_summary = _serialize_application_summary(application, datasource_maps, service_count_map)
    application_summary.update({"description": application.description, "app_token": None})

    apm_datasources = [
        datasource_maps[datasource_type].get(_app_key(application)) for datasource_type in DATASOURCE_TYPES
    ]
    apm_datasources = [datasource for datasource in apm_datasources if datasource and datasource.bk_data_id > 0]
    bk_data_ids = sorted({datasource.bk_data_id for datasource in apm_datasources})
    table_ids = sorted({datasource.result_table_id for datasource in apm_datasources if datasource.result_table_id})

    datasource_items = [
        _serialize_datasource_summary(datasource)
        for datasource in metadata_models.DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids
        ).order_by("bk_data_id")
    ]
    result_table_items = [
        _serialize_result_table_summary(result_table)
        for result_table in metadata_models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=table_ids
        ).order_by("table_id")
    ]

    custom_reports = []
    metric_datasource = datasource_maps["metric"].get(_app_key(application))
    if metric_datasource and metric_datasource.time_series_group_id:
        group = metadata_models.TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            time_series_group_id=metric_datasource.time_series_group_id,
            is_delete=False,
        ).first()
        if group:
            metric_count = metadata_models.TimeSeriesMetric.objects.filter(group_id=group.time_series_group_id).count()
            custom_reports.append(_serialize_custom_metric_group(group, metric_count))

    service_nodes = list(
        apm_models.TopoNode.objects.filter(bk_biz_id=application.bk_biz_id, app_name=application.app_name).order_by(
            "-updated_at", "topo_key"
        )[:10]
    )
    instance_count_map = _load_instance_count_map(application, [node.topo_key for node in service_nodes])
    relation_preview = list(
        apm_models.TopoRelation.objects.filter(bk_biz_id=application.bk_biz_id, app_name=application.app_name).order_by(
            "-updated_at", "from_topo_key"
        )[:20]
    )

    return build_response(
        operation="apm.application_detail",
        func_name=FUNC_APM_APPLICATION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "application": application_summary,
            "datasources": datasource_items,
            "result_tables": result_table_items,
            "custom_reports": custom_reports,
            "services_preview": [_serialize_service(node, instance_count_map) for node in service_nodes],
            "topo_nodes_preview": [_serialize_topo_node(node) for node in service_nodes],
            "topo_relations_preview": [_serialize_topo_relation(relation) for relation in relation_preview],
            "service_summary": {"total": service_count_map.get(_app_key(application), 0)},
            "topo_summary": {
                "node_count": service_count_map.get(_app_key(application), 0),
                "relation_count": apm_models.TopoRelation.objects.filter(
                    bk_biz_id=application.bk_biz_id, app_name=application.app_name
                ).count(),
            },
        },
    )


@KernelRPCRegistry.register(
    FUNC_APM_SERVICE_LIST,
    summary="Admin 分页查询 APM 服务列表",
    description="只读分页查询 APM TopoNode 服务视图，避免详情页一次性返回大量服务。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "application_id": "必填，APM 应用 ID",
        "service_name": "可选，服务名包含匹配",
        "kind": "可选，extra_data.kind 精确匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "application_id": 1, "page": 1, "page_size": 20},
)
def list_apm_services(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    application = _get_application(params.get("application_id"), bk_tenant_id)
    page, page_size = normalize_pagination(params)

    queryset = apm_models.TopoNode.objects.filter(bk_biz_id=application.bk_biz_id, app_name=application.app_name)
    service_name = str(params.get("service_name") or "").strip()
    if service_name:
        queryset = queryset.filter(topo_key__icontains=service_name)

    nodes = list(queryset.order_by("-updated_at", "topo_key"))
    kind = str(params.get("kind") or "").strip()
    if kind:
        nodes = [
            node
            for node in nodes
            if isinstance(node.extra_data, dict) and str(node.extra_data.get("kind") or "") == kind
        ]

    total = len(nodes)
    offset = (page - 1) * page_size
    page_nodes = nodes[offset : offset + page_size]
    instance_count_map = _load_instance_count_map(application, [node.topo_key for node in page_nodes])

    return build_response(
        operation="apm.service_list",
        func_name=FUNC_APM_SERVICE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_service(node, instance_count_map) for node in page_nodes],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_APM_TOPO,
    summary="Admin 查询 APM 拓扑摘要",
    description="只读查询 APM TopoNode / TopoRelation 的轻量拓扑数据。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "application_id": "必填，APM 应用 ID",
        "limit": "可选，默认 200，最大 500",
    },
    example_params={"bk_tenant_id": "system", "application_id": 1, "limit": 200},
)
def get_apm_topo(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    application = _get_application(params.get("application_id"), bk_tenant_id)
    limit = _normalize_int(params.get("limit"), "limit") or 200
    limit = max(1, min(limit, 500))

    nodes = list(
        apm_models.TopoNode.objects.filter(bk_biz_id=application.bk_biz_id, app_name=application.app_name).order_by(
            "-updated_at", "topo_key"
        )[:limit]
    )
    relations = list(
        apm_models.TopoRelation.objects.filter(bk_biz_id=application.bk_biz_id, app_name=application.app_name).order_by(
            "-updated_at", "from_topo_key"
        )[:limit]
    )

    degree_map: dict[str, int] = defaultdict(int)
    for relation in relations:
        degree_map[relation.from_topo_key] += 1
        degree_map[relation.to_topo_key] += 1

    return build_response(
        operation="apm.topo",
        func_name=FUNC_APM_TOPO,
        bk_tenant_id=bk_tenant_id,
        data={
            "nodes": [_serialize_topo_node(node) | {"degree": degree_map.get(node.topo_key, 0)} for node in nodes],
            "relations": [_serialize_topo_relation(relation) for relation in relations],
            "summary": {"node_count": len(nodes), "relation_count": len(relations), "limit": limit},
        },
    )
