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
    _mask_sensitive_fields,
    build_response,
    get_bk_tenant_id,
    normalize_include,
    normalize_optional_bool,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
)
from metadata import models
from metadata.models.data_link.data_link_configs import ClusterConfig, COMPONENT_CLASS_MAP

FUNC_COMPONENT_LIST = "admin.datalink.component_list"
FUNC_COMPONENT_DETAIL = "admin.datalink.component_detail"
FUNC_COMPONENT_CONFIG = "admin.datalink.component_config"
FUNC_CLUSTER_CONFIG_LIST = "admin.datalink.cluster_config_list"
FUNC_CLUSTER_CONFIG_DETAIL = "admin.datalink.cluster_config_detail"
FUNC_CLUSTER_CONFIG_COMPONENT_CONFIG = "admin.datalink.cluster_config_component_config"
FUNC_DATALINK_LIST = "admin.datalink.datalink_list"
FUNC_DATALINK_DETAIL = "admin.datalink.datalink_detail"
FUNC_DATALINK_COMPONENT_CONFIG = "admin.datalink.datalink_component_config"

DRLRB_COMMON_FIELDS = [
    "name",
    "namespace",
    "create_time",
    "last_modify_time",
    "status",
    "data_link_name",
    "bk_biz_id",
    "bk_tenant_id",
]

KIND_EXTRA_FIELDS = {
    "DataId": ["bk_data_id"],
    "ResultTable": ["table_id", "data_type", "bkbase_table_id"],
    "VmStorageBinding": ["vm_cluster_name", "bkbase_result_table_name", "table_id"],
    "ElasticSearchBinding": ["es_cluster_name", "table_id", "bkbase_result_table_name", "timezone"],
    "DorisBinding": ["table_id", "bkbase_result_table_name", "doris_cluster_name"],
    "Databus": ["data_id_name", "bk_data_id", "sink_names"],
    "ConditionalSink": [],
}

CLUSTER_CONFIG_FIELDS = [
    "name",
    "kind",
    "namespace",
    "bk_tenant_id",
    "origin_config",
    "create_time",
    "update_time",
]

DATALINK_FIELDS = [
    "data_link_name",
    "bk_tenant_id",
    "namespace",
    "data_link_strategy",
    "bk_data_id",
    "table_ids",
    "create_time",
    "last_modify_time",
]

ORDERING_FIELDS = {"name", "namespace", "create_time", "last_modify_time", "status", "bk_biz_id"}
CLUSTER_CONFIG_ORDERING_FIELDS = {"name", "namespace", "kind", "create_time", "update_time"}
DATALINK_ORDERING_FIELDS = {
    "data_link_name",
    "namespace",
    "data_link_strategy",
    "bk_data_id",
    "create_time",
    "last_modify_time",
}
INCLUDE_VALUES = {"component_config"}

DRLRB_KINDS = set(COMPONENT_CLASS_MAP.keys())
VALID_KINDS_FOR_LIST = DRLRB_KINDS

KIND_FILTER_MAP: dict[str, list[str]] = {
    "DataId": ["bk_data_id"],
    "Databus": ["bk_data_id"],
    "ResultTable": ["data_type"],
    "VmStorageBinding": ["vm_cluster_name"],
    "ElasticSearchBinding": ["es_cluster_name"],
    "DorisBinding": ["doris_cluster_name"],
    "ConditionalSink": [],
}


def _get_component_model(kind: str):
    if kind not in COMPONENT_CLASS_MAP:
        raise CustomException(
            message=f"未知的组件类型 (kind={kind})，有效值: {', '.join(sorted(COMPONENT_CLASS_MAP.keys()))}"
        )
    return COMPONENT_CLASS_MAP[kind]


def _serialize_component(instance, kind: str) -> dict[str, Any]:
    fields = DRLRB_COMMON_FIELDS + KIND_EXTRA_FIELDS.get(kind, [])
    item = serialize_model(instance, fields)
    item["created_at"] = item.pop("create_time", None)
    item["updated_at"] = item.pop("last_modify_time", None)
    item["kind"] = kind
    return item


def _serialize_cluster_config(instance) -> dict[str, Any]:
    item = serialize_model(instance, CLUSTER_CONFIG_FIELDS)
    item["created_at"] = item.pop("create_time", None)
    item["updated_at"] = item.pop("update_time", None)
    return item


def _serialize_datalink_for_list(instance) -> dict[str, Any]:
    item = serialize_model(instance, DATALINK_FIELDS)
    table_ids = item.pop("table_ids", [])
    item["table_ids_count"] = len(table_ids) if isinstance(table_ids, list) else 0
    item["created_at"] = item.pop("create_time", None)
    item["updated_at"] = item.pop("last_modify_time", None)
    return item


def _serialize_datalink_for_detail(instance) -> dict[str, Any]:
    item = serialize_model(instance, DATALINK_FIELDS)
    item["created_at"] = item.pop("create_time", None)
    item["updated_at"] = item.pop("last_modify_time", None)
    return item


def _handle_component_config(params, operation_name, func_name):
    bk_tenant_id = get_bk_tenant_id(params)

    kind = str(params.get("kind", "")).strip()
    if not kind:
        raise CustomException(message="kind 为必填项")
    namespace = str(params.get("namespace", "")).strip()
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    name = str(params.get("name", "")).strip()
    if not name:
        raise CustomException(message="name 为必填项")

    model_class = _get_component_model(kind)
    try:
        instance = model_class.objects.get(bk_tenant_id=bk_tenant_id, namespace=namespace, name=name)
    except model_class.DoesNotExist as error:
        raise CustomException(message=f"未找到组件: kind={kind}, namespace={namespace}, name={name}") from error

    try:
        component_config = instance.component_config
        component_config = _mask_sensitive_fields(component_config)
    except Exception:
        component_config = None

    return build_response(
        operation=operation_name,
        func_name=func_name,
        bk_tenant_id=bk_tenant_id,
        data={
            "component_config": component_config,
            "namespace": namespace,
            "kind": kind,
            "name": name,
        },
    )


def _fetch_component_config_for_item(instance, item, warnings_list):
    try:
        item["component_config"] = _mask_sensitive_fields(instance.component_config)
    except Exception:
        item["component_config"] = None
        warnings_list.append(
            {
                "code": "COMPONENT_CONFIG_UNAVAILABLE",
                "message": (
                    f"component_config 获取失败: namespace={instance.namespace}, "
                    f"kind={instance.kind}, name={instance.name}"
                ),
            }
        )


# =============================================================================
# RPC Handler: component_list
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_COMPONENT_LIST,
    summary="Admin 查询 DataLink 组件列表",
    description="按 kind 查询指定类型的 DataLink 组件，支持条件过滤和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，组件类型: " + ", ".join(sorted(COMPONENT_CLASS_MAP.keys())),
        "namespace": "可选，命名空间精确匹配",
        "search": "可选，按 name 模糊匹配",
        "status": "可选，状态精确匹配",
        "bk_data_id": "可选，数据源 ID (DataId/Databus 类型)",
        "data_type": "可选，结果表类型 (ResultTable 类型)",
        "vm_cluster_name": "可选，VM 集群名称 (VmStorageBinding 类型)",
        "es_cluster_name": "可选，ES 集群名称 (ElasticSearchBinding 类型)",
        "doris_cluster_name": "可选，Doris 集群名称 (DorisBinding 类型)",
        "has_data_link": "可选，true=筛选已关联 DataLink 的组件，false=筛选未关联的组件",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "kind": "VmStorageBinding", "page": 1, "page_size": 20},
)
def list_components(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)

    kind = str(params.get("kind", "")).strip()
    if not kind:
        raise CustomException(message="kind 为必填项")

    model_class = _get_component_model(kind)
    queryset = model_class.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("namespace"):
        queryset = queryset.filter(namespace=str(params["namespace"]).strip())
    if params.get("search"):
        queryset = queryset.filter(name__contains=str(params["search"]).strip())
    if params.get("status") not in (None, ""):
        queryset = queryset.filter(status=params["status"])

    has_data_link = normalize_optional_bool(params.get("has_data_link"), "has_data_link")
    if has_data_link is True:
        queryset = queryset.filter(data_link_name__isnull=False).exclude(data_link_name="")
    elif has_data_link is False:
        queryset = queryset.filter(Q(data_link_name="") | Q(data_link_name__isnull=True))

    for field_name in KIND_FILTER_MAP.get(kind, []):
        value = params.get(field_name)
        if value is not None and value != "":
            if field_name == "bk_data_id":
                try:
                    queryset = queryset.filter(bk_data_id=int(value))
                except (TypeError, ValueError):
                    raise CustomException(message="bk_data_id 必须是整数") from None
            else:
                queryset = queryset.filter(**{field_name: value})

    queryset = queryset.order_by("-create_time")
    items_raw, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_component(item, kind) for item in items_raw]

    return build_response(
        operation="datalink.component_list",
        func_name=FUNC_COMPONENT_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


# =============================================================================
# RPC Handler: component_detail
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_COMPONENT_DETAIL,
    summary="Admin 查询 DataLink 组件详情",
    description="按 kind、namespace、name 查询单个组件详情。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，组件类型: " + ", ".join(sorted(COMPONENT_CLASS_MAP.keys())),
        "namespace": "必填，命名空间",
        "name": "必填，组件名称",
        "include": "可选，展开范围: component_config",
    },
    example_params={
        "bk_tenant_id": "system",
        "kind": "VmStorageBinding",
        "namespace": "bkmonitor",
        "name": "test-component",
    },
)
def get_component_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    includes = normalize_include(params.get("include"), INCLUDE_VALUES)
    warnings_list: list[dict[str, Any]] = []

    kind = str(params.get("kind", "")).strip()
    if not kind:
        raise CustomException(message="kind 为必填项")
    namespace = str(params.get("namespace", "")).strip()
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    name = str(params.get("name", "")).strip()
    if not name:
        raise CustomException(message="name 为必填项")

    model_class = _get_component_model(kind)
    try:
        instance = model_class.objects.get(bk_tenant_id=bk_tenant_id, namespace=namespace, name=name)
    except model_class.DoesNotExist as error:
        raise CustomException(message=f"未找到组件: kind={kind}, namespace={namespace}, name={name}") from error

    item = _serialize_component(instance, kind)

    if "component_config" in includes:
        _fetch_component_config_for_item(instance, item, warnings_list)

    return build_response(
        operation="datalink.component_detail",
        func_name=FUNC_COMPONENT_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=item,
        warnings=warnings_list,
    )


# =============================================================================
# RPC Handler: component_config (lazy fetch)
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_COMPONENT_CONFIG,
    summary="Admin 查询单个组件的 ComponentConfig",
    description="根据 kind、namespace、name 查询单个组件的远程配置。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，组件类型: " + ", ".join(sorted(COMPONENT_CLASS_MAP.keys())),
        "namespace": "必填，命名空间",
        "name": "必填，组件名称",
    },
    example_params={
        "bk_tenant_id": "system",
        "kind": "VmStorageBinding",
        "namespace": "bkmonitor",
        "name": "test-component",
    },
)
def get_component_config(params: dict[str, Any]) -> dict[str, Any]:
    return _handle_component_config(params, "datalink.component_config", FUNC_COMPONENT_CONFIG)


# =============================================================================
# RPC Handler: cluster_config_list
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_CLUSTER_CONFIG_LIST,
    summary="Admin 查询 ClusterConfig 列表",
    description="查询集群配置列表，支持按 kind、namespace、name 过滤和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "可选，集群类型: KafkaChannel, VmStorage, ElasticSearch, Doris",
        "namespace": "可选，命名空间精确匹配",
        "search": "可选，按 name 模糊匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "kind": "ElasticSearch", "page": 1, "page_size": 20},
)
def list_cluster_configs(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)

    queryset = ClusterConfig.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("kind") not in (None, ""):
        queryset = queryset.filter(kind=str(params["kind"]).strip())
    if params.get("namespace") not in (None, ""):
        queryset = queryset.filter(namespace=str(params["namespace"]).strip())
    if params.get("search") not in (None, ""):
        queryset = queryset.filter(name__contains=str(params["search"]).strip())

    queryset = queryset.order_by("-create_time")
    items_raw, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_cluster_config(item) for item in items_raw]

    return build_response(
        operation="datalink.cluster_config_list",
        func_name=FUNC_CLUSTER_CONFIG_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


# =============================================================================
# RPC Handler: cluster_config_detail
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_CLUSTER_CONFIG_DETAIL,
    summary="Admin 查询 ClusterConfig 详情",
    description="按 kind、namespace、name 查询单个集群配置详情。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，集群类型: KafkaChannel, VmStorage, ElasticSearch, Doris",
        "namespace": "必填，命名空间",
        "name": "必填，集群名称",
        "include": "可选，展开范围: component_config",
    },
    example_params={
        "bk_tenant_id": "system",
        "kind": "ElasticSearch",
        "namespace": "bklog",
        "name": "es-cluster-1",
    },
)
def get_cluster_config_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    includes = normalize_include(params.get("include"), INCLUDE_VALUES)
    warnings_list: list[dict[str, Any]] = []

    kind = str(params.get("kind", "")).strip()
    if not kind:
        raise CustomException(message="kind 为必填项")
    namespace = str(params.get("namespace", "")).strip()
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    name = str(params.get("name", "")).strip()
    if not name:
        raise CustomException(message="name 为必填项")

    try:
        instance = ClusterConfig.objects.get(bk_tenant_id=bk_tenant_id, kind=kind, namespace=namespace, name=name)
    except ClusterConfig.DoesNotExist as error:
        raise CustomException(
            message=f"未找到 ClusterConfig: kind={kind}, namespace={namespace}, name={name}"
        ) from error

    item = _serialize_cluster_config(instance)

    if "component_config" in includes:
        try:
            item["component_config"] = _mask_sensitive_fields(instance.component_config)
        except Exception:
            item["component_config"] = None
            warnings_list.append(
                {
                    "code": "COMPONENT_CONFIG_UNAVAILABLE",
                    "message": (
                        f"component_config 获取失败: namespace={instance.namespace}, "
                        f"kind={instance.kind}, name={instance.name}"
                    ),
                }
            )

    return build_response(
        operation="datalink.cluster_config_detail",
        func_name=FUNC_CLUSTER_CONFIG_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=item,
        warnings=warnings_list,
    )


# =============================================================================
# RPC Handler: cluster_config_component_config (lazy fetch)
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_CLUSTER_CONFIG_COMPONENT_CONFIG,
    summary="Admin 查询单个 ClusterConfig 的 ComponentConfig",
    description="按 kind、namespace、name 查询单个集群配置的远程配置。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，集群类型: KafkaChannel, VmStorage, ElasticSearch, Doris",
        "namespace": "必填，命名空间",
        "name": "必填，集群名称",
    },
    example_params={
        "bk_tenant_id": "system",
        "kind": "ElasticSearch",
        "namespace": "bklog",
        "name": "es-cluster-1",
    },
)
def get_cluster_config_component_config(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    kind = str(params.get("kind", "")).strip()
    if not kind:
        raise CustomException(message="kind 为必填项")
    namespace = str(params.get("namespace", "")).strip()
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    name = str(params.get("name", "")).strip()
    if not name:
        raise CustomException(message="name 为必填项")

    try:
        instance = ClusterConfig.objects.get(bk_tenant_id=bk_tenant_id, kind=kind, namespace=namespace, name=name)
    except ClusterConfig.DoesNotExist as error:
        raise CustomException(
            message=f"未找到 ClusterConfig: kind={kind}, namespace={namespace}, name={name}"
        ) from error

    try:
        component_config = instance.component_config
        component_config = _mask_sensitive_fields(component_config)
    except Exception:
        component_config = None

    return build_response(
        operation="datalink.cluster_config_component_config",
        func_name=FUNC_CLUSTER_CONFIG_COMPONENT_CONFIG,
        bk_tenant_id=bk_tenant_id,
        data={
            "component_config": component_config,
            "namespace": namespace,
            "kind": kind,
            "name": name,
        },
    )


# =============================================================================
# RPC Handler: datalink_list
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_DATALINK_LIST,
    summary="Admin 查询 DataLink 列表",
    description="查询数据链路编排列表，支持按名称、策略、命名空间过滤和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "namespace": "可选，命名空间精确匹配",
        "search": "可选，按 data_link_name 模糊匹配",
        "data_link_strategy": "可选，链路策略精确匹配",
        "bk_data_id": "可选，关联数据源 ID 精确匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20},
)
def list_datalinks(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)

    queryset = models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("namespace") not in (None, ""):
        queryset = queryset.filter(namespace=str(params["namespace"]).strip())
    if params.get("search") not in (None, ""):
        queryset = queryset.filter(data_link_name__contains=str(params["search"]).strip())
    if params.get("data_link_strategy") not in (None, ""):
        queryset = queryset.filter(data_link_strategy=params["data_link_strategy"])
    if params.get("bk_data_id") not in (None, ""):
        try:
            queryset = queryset.filter(bk_data_id=int(params["bk_data_id"]))
        except (TypeError, ValueError):
            raise CustomException(message="bk_data_id 必须是整数") from None

    queryset = queryset.order_by("-create_time")
    items_raw, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_datalink_for_list(item) for item in items_raw]

    return build_response(
        operation="datalink.datalink_list",
        func_name=FUNC_DATALINK_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


# =============================================================================
# RPC Handler: datalink_detail
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_DATALINK_DETAIL,
    summary="Admin 查询 DataLink 详情",
    description="查询数据链路编排详情，包含关联的所有子组件。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "data_link_name": "必填，数据链路名称",
        "include": "可选，展开范围: component_config",
    },
    example_params={
        "bk_tenant_id": "system",
        "data_link_name": "test-data-link",
        "include": ["component_config"],
    },
)
def get_datalink_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    includes = normalize_include(params.get("include"), INCLUDE_VALUES)
    warnings_list: list[dict[str, Any]] = []

    data_link_name = str(params.get("data_link_name", "")).strip()
    if not data_link_name:
        raise CustomException(message="data_link_name 为必填项")

    try:
        datalink = models.DataLink.objects.get(bk_tenant_id=bk_tenant_id, data_link_name=data_link_name)
    except models.DataLink.DoesNotExist as error:
        raise CustomException(message=f"未找到 DataLink: data_link_name={data_link_name}") from error

    data = _serialize_datalink_for_detail(datalink)

    kind_order = [
        "ResultTable",
        "VmStorageBinding",
        "ElasticSearchBinding",
        "DorisBinding",
        "Databus",
        "ConditionalSink",
    ]

    components: dict[str, list[dict[str, Any]]] = {}
    for kind in kind_order:
        if kind not in DRLRB_KINDS:
            continue
        model_class = COMPONENT_CLASS_MAP[kind]
        child_instances = list(model_class.objects.filter(bk_tenant_id=bk_tenant_id, data_link_name=data_link_name))

        serialized_items: list[dict[str, Any]] = []
        for child in child_instances:
            item = _serialize_component(child, kind)
            if "component_config" in includes:
                _fetch_component_config_for_item(child, item, warnings_list)
            serialized_items.append(item)

        components[kind] = serialized_items

    data["components"] = components

    return build_response(
        operation="datalink.datalink_detail",
        func_name=FUNC_DATALINK_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings_list,
    )


# =============================================================================
# RPC Handler: datalink_component_config (lazy fetch)
# =============================================================================
@KernelRPCRegistry.register(
    FUNC_DATALINK_COMPONENT_CONFIG,
    summary="Admin 查询单个组件的 ComponentConfig (DataLink 入口)",
    description="根据 kind、namespace、name 查询单个组件的远程配置。与 component_config 逻辑一致。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "kind": "必填，组件类型: " + ", ".join(sorted(COMPONENT_CLASS_MAP.keys())),
        "namespace": "必填，命名空间",
        "name": "必填，组件名称",
    },
    example_params={
        "bk_tenant_id": "system",
        "kind": "VmStorageBinding",
        "namespace": "bkmonitor",
        "name": "test-component",
    },
)
def get_datalink_component_config(params: dict[str, Any]) -> dict[str, Any]:
    return _handle_component_config(params, "datalink.datalink_component_config", FUNC_DATALINK_COMPONENT_CONFIG)
