"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import json
import re
from datetime import datetime, timezone
from typing import Any

from core.drf_resource.exceptions import CustomException
from django.conf import settings
from django.db.models import Q
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from kubernetes import client as k8s_client

from constants.bk_collector import BkCollectorComp
from metadata import config, models

FUNC_BCS_CLUSTER_LIST = "admin.bcs_cluster.list"
FUNC_BCS_CLUSTER_DETAIL = "admin.bcs_cluster.detail"
FUNC_BCS_CLUSTER_DATA_ID_LIST = "admin.bcs_cluster.data_id_list"
FUNC_BCS_CLUSTER_DATA_ID_DETAIL = "admin.bcs_cluster.data_id_detail"
FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_LIST = "admin.bcs_cluster.bk_collector_config_list"
FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_DETAIL = "admin.bcs_cluster.bk_collector_config_detail"
FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_LIST = "admin.bcs_cluster.bkmonitor_operator_release_list"
FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_DETAIL = "admin.bcs_cluster.bkmonitor_operator_release_detail"
INSPECT_SAFETY_LEVEL = "inspect"

BCS_CLUSTER_FIELDS = [
    "cluster_id",
    "bk_tenant_id",
    "bcs_api_cluster_id",
    "bk_biz_id",
    "bk_cloud_id",
    "project_id",
    "status",
    "domain_name",
    "port",
    "server_address_path",
    "api_key_type",
    "api_key_prefix",
    "is_skip_ssl_verify",
    "K8sMetricDataID",
    "CustomMetricDataID",
    "K8sEventDataID",
    "CustomEventDataID",
    "SystemLogDataID",
    "CustomLogDataID",
    "bk_env",
    "operator_ns",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
    "is_deleted_allow_view",
]

SENSITIVE_BCS_FIELDS = {
    "api_key_content": "has_api_key",
    "cert_content": "has_cert",
}

ORDERING_FIELDS = {
    "cluster_id",
    "bcs_api_cluster_id",
    "bk_biz_id",
    "status",
    "create_time",
    "last_modify_time",
}

DATA_ID_FIELD_NAMES = [
    "K8sMetricDataID",
    "CustomMetricDataID",
    "K8sEventDataID",
    "CustomEventDataID",
    "SystemLogDataID",
    "CustomLogDataID",
]

BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON = "custom_metric_json"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS = "custom_metric_prometheus"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT = "custom_event"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT = "custom_report"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON = "custom_report_json"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_PROMETHEUS = "custom_report_prometheus"
BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG = "custom_log"
BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION = "apm_application"
BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM = "apm_platform"
BK_COLLECTOR_CONFIG_CUSTOM_REPORT_TYPES = (
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
)
BK_COLLECTOR_CONFIG_CUSTOM_REPORT_JSON_TYPES = (
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
)
BK_COLLECTOR_CONFIG_CATEGORIES = (
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM,
)
BK_COLLECTOR_CONFIG_QUERY_CATEGORIES = (
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_PROMETHEUS,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM,
    *BK_COLLECTOR_CONFIG_CUSTOM_REPORT_TYPES,
)
BK_COLLECTOR_CONFIG_CATEGORY_ORDER = {
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON: 10,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON: 10,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS: 20,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT: 30,
    BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG: 40,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION: 50,
    BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM: 60,
}
BK_COLLECTOR_CONFIG_PROTOCOLS = ("json", "prometheus", "log", "apm", "platform")
BK_COLLECTOR_CONFIG_PROTOCOL_DEFAULT_CATEGORY = {
    "json": BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON,
    "prometheus": BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS,
    "log": BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG,
    "apm": BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION,
    "platform": BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM,
}
BK_COLLECTOR_CONFIG_VALUE_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}
BK_COLLECTOR_PLATFORM_SENSITIVE_PATTERN = re.compile(
    r"(?P<prefix>[\"']?(?:decoded_key|decoded_iv|fixed_token|bk_data_token|token|secret|password|authorization)[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\"'\n,}\]]+)(?P=quote)",
    re.IGNORECASE,
)
BKMONITOR_OPERATOR_NAMESPACE_KEYWORD = "bkmonitor-operator"
BKMONITOR_OPERATOR_RELEASE_SECRET_TYPE = "helm.sh/release.v1"
BKMONITOR_OPERATOR_RELEASE_SECRET_NAME_PATTERN = re.compile(
    r"^sh\.helm\.release\.v1\.(?P<release_name>.+)\.v(?P<revision>\d+)$"
)
BKMONITOR_OPERATOR_HELM_LABEL_SELECTOR = "owner=helm"
BKMONITOR_OPERATOR_RELEASE_REF_SEPARATOR = ":"


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _normalize_bk_data_id(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_data_id 必须是整数") from error


def _require_cluster_id(params: dict[str, Any]) -> str:
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    return str(cluster_id).strip()


def _get_bcs_cluster_or_raise(bk_tenant_id: str, cluster_id: str) -> models.BCSClusterInfo:
    try:
        return models.BCSClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.BCSClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 BCSClusterInfo: cluster_id={cluster_id}") from error


def _serialize_bcs_cluster(bcs_cluster: models.BCSClusterInfo) -> dict[str, Any]:
    item = {field: serialize_value(getattr(bcs_cluster, field, None)) for field in BCS_CLUSTER_FIELDS}
    for sensitive_field, flag_field in SENSITIVE_BCS_FIELDS.items():
        raw_value = getattr(bcs_cluster, sensitive_field, None)
        item[flag_field] = bool(raw_value)
    return item


def _build_bcs_cluster_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.BCSClusterInfo.objects.all(), bk_tenant_id)

    if params.get("bk_biz_id") not in (None, ""):
        try:
            queryset = queryset.filter(bk_biz_id=int(params["bk_biz_id"]))
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_biz_id 必须是整数") from error

    if params.get("bk_data_id") not in (None, ""):
        bk_data_id = _normalize_bk_data_id(params["bk_data_id"])
        if bk_data_id <= 0:
            return queryset.none()

        data_id_query = Q()
        for field_name in DATA_ID_FIELD_NAMES:
            data_id_query |= Q(**{field_name: bk_data_id})
        queryset = queryset.filter(data_id_query)

    if params.get("cluster_id") not in (None, ""):
        queryset = queryset.filter(cluster_id__contains=str(params["cluster_id"]).strip())

    status = params.get("status")
    if status not in (None, ""):
        if isinstance(status, str):
            status_values = [item.strip() for item in status.split(",") if item.strip()]
        elif isinstance(status, list | tuple | set):
            status_values = [str(item).strip() for item in status if str(item).strip()]
        else:
            status_values = [str(status).strip()]

        if status_values:
            queryset = queryset.filter(status__in=status_values)

    return queryset


def _read_nested_dict_value(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _normalize_label_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value == "true":
            return True
        if normalized_value == "false":
            return False
    return None


def _normalize_optional_data_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_bcs_data_id_resource(resource: dict[str, Any]) -> dict[str, Any]:
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    metadata_labels = metadata.get("labels") if isinstance(metadata.get("labels"), dict) else {}
    spec = resource.get("spec") if isinstance(resource.get("spec"), dict) else {}
    spec_labels = spec.get("labels") if isinstance(spec.get("labels"), dict) else {}
    status = resource.get("status") if isinstance(resource.get("status"), dict) else {}

    return {
        "name": metadata.get("name"),
        "data_id": _normalize_optional_data_id(spec.get("dataID") or spec.get("data_id")),
        "usage": metadata_labels.get("usage"),
        "is_common": _normalize_label_bool(metadata_labels.get("isCommon")),
        "is_system": _normalize_label_bool(metadata_labels.get("isSystem")),
        "monitor_resource": spec.get("monitorResource") if isinstance(spec.get("monitorResource"), dict) else None,
        "labels": spec_labels,
        "phase": status.get("phase"),
        "created_at": metadata.get("creationTimestamp"),
        "resource_version": metadata.get("resourceVersion"),
    }


def _get_bcs_data_id_custom_client(cluster: models.BCSClusterInfo) -> k8s_client.CustomObjectsApi:
    return k8s_client.CustomObjectsApi(cluster.api_client)


def _list_bcs_data_id_resources(cluster: models.BCSClusterInfo) -> list[dict[str, Any]]:
    try:
        resource_list = _get_bcs_data_id_custom_client(cluster).list_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        )
    except k8s_client.exceptions.ApiException as error:
        raise CustomException(message=f"查询 BCS DataID 列表失败: {error}") from error

    items = resource_list.get("items") if isinstance(resource_list, dict) else []
    if not isinstance(items, list):
        return []

    return sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: str(_read_nested_dict_value(item, "metadata", "name") or ""),
    )


def _get_bcs_data_id_resource(cluster: models.BCSClusterInfo, name: str) -> dict[str, Any]:
    try:
        resource = _get_bcs_data_id_custom_client(cluster).get_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
            name=name,
        )
    except k8s_client.exceptions.ApiException as error:
        if getattr(error, "status", None) == 404:
            raise CustomException(message=f"未找到 BCS DataID 资源: name={name}") from error
        raise CustomException(message=f"查询 BCS DataID 资源失败: {error}") from error

    if not isinstance(resource, dict):
        raise CustomException(message=f"BCS DataID 资源返回格式异常: name={name}")

    return resource


def _paginate_list(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


def _normalize_bk_collector_config_category(value: Any) -> str | None:
    if value in (None, ""):
        return None
    category = str(value).strip()
    if category not in BK_COLLECTOR_CONFIG_QUERY_CATEGORIES:
        raise CustomException(message=f"不支持的 bk-collector 配置分类: {category}")
    return category


def _normalize_bk_collector_config_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    config_type = str(value).strip()
    if config_type not in BK_COLLECTOR_CONFIG_CUSTOM_REPORT_JSON_TYPES:
        raise CustomException(message=f"不支持的 bk-collector 配置类型: {config_type}")
    return config_type


def _normalize_bk_collector_keyword(value: Any) -> str | None:
    if value in (None, ""):
        return None
    keyword = str(value).strip()
    return keyword or None


def _get_bk_collector_protocols_by_category(category: str | None, config_type: str | None = None) -> tuple[str, ...]:
    target_category = config_type or category
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT:
        return ("json", "prometheus")
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON:
        return ("json",)
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_PROMETHEUS:
        return ("prometheus",)
    if target_category in {
        BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
        BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
    }:
        return ("json",)
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS:
        return ("prometheus",)
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_LOG:
        return ("log",)
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_APM_APPLICATION:
        return ("apm",)
    if target_category == BK_COLLECTOR_CONFIG_CATEGORY_APM_PLATFORM:
        return ("platform",)
    return BK_COLLECTOR_CONFIG_PROTOCOLS


def _normalize_include_sensitive(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _get_bk_collector_namespace_context(
    cluster: models.BCSClusterInfo,
    *,
    use_config_namespace: bool = False,
) -> dict[str, Any]:
    operator_namespace = getattr(cluster, "operator_ns", None) or BkCollectorComp.NAMESPACE
    cluster_namespace = settings.K8S_OPERATOR_DEPLOY_NAMESPACE or {}
    configured_namespace = cluster_namespace.get(cluster.cluster_id)
    can_use_configured_namespace = bool(configured_namespace)
    using_configured_namespace = bool(use_config_namespace and can_use_configured_namespace)
    namespace = configured_namespace if using_configured_namespace else operator_namespace
    return {
        "namespace": namespace,
        "operator_namespace": operator_namespace,
        "configured_namespace": configured_namespace,
        "can_use_configured_namespace": can_use_configured_namespace,
        "using_configured_namespace": using_configured_namespace,
    }


def _get_bcs_operator_configured_namespace(cluster: models.BCSClusterInfo) -> str | None:
    cluster_namespace = settings.K8S_OPERATOR_DEPLOY_NAMESPACE or {}
    return cluster_namespace.get(cluster.cluster_id)


def _get_bk_collector_core_client(cluster: models.BCSClusterInfo) -> k8s_client.CoreV1Api:
    return k8s_client.CoreV1Api(cluster.api_client)


def _build_bk_collector_secret_label_selector(cluster_id: str, protocol: str) -> tuple[str | None, dict[str, Any]]:
    secret_config = BkCollectorComp.get_secrets_config_map_by_protocol(cluster_id, protocol) or {}
    extra_label = secret_config.get("secret_extra_label")
    if not extra_label:
        return None, secret_config
    return f"{BkCollectorComp.SECRET_COMMON_LABELS},{extra_label}", secret_config


def _decode_bk_collector_secret_content(encoded_content: Any) -> tuple[str | None, str | None]:
    if encoded_content in (None, ""):
        return None, "empty secret data"
    try:
        raw_content = base64.b64decode(encoded_content)
        try:
            return gzip.decompress(raw_content).decode(), None
        except gzip.BadGzipFile:
            return raw_content.decode(), None
    except Exception as error:  # pylint: disable=broad-except
        return None, str(error)


def _extract_bk_collector_config_id(config_key: str) -> int | None:
    matched = re.search(r"-(\d+)\.conf$", config_key)
    if not matched:
        return None
    try:
        return int(matched.group(1))
    except (TypeError, ValueError):
        return None


def _match_bk_collector_raw_config_keyword(
    protocol: str, secret_name: str, config_key: str, keyword: str | None
) -> bool:
    if not keyword:
        return True
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        return True

    try:
        numeric_keyword = int(normalized_keyword)
    except (TypeError, ValueError):
        numeric_keyword = None

    if numeric_keyword is not None:
        config_id = 0 if protocol == "platform" else _extract_bk_collector_config_id(config_key)
        return config_id == numeric_keyword

    return normalized_keyword in secret_name.lower() or normalized_keyword in config_key.lower()


def _get_bk_collector_config_value_pattern(key: str) -> re.Pattern[str]:
    if key not in BK_COLLECTOR_CONFIG_VALUE_PATTERN_CACHE:
        BK_COLLECTOR_CONFIG_VALUE_PATTERN_CACHE[key] = re.compile(
            rf"[\"']?{re.escape(key)}[\"']?\s*[:=]\s*[\"']?(?P<value>[^\"'\n,}}\]]+)",
            re.IGNORECASE,
        )
    return BK_COLLECTOR_CONFIG_VALUE_PATTERN_CACHE[key]


def _extract_bk_collector_config_value(config_content: str | None, *keys: str) -> str | None:
    if not config_content:
        return None
    for key in keys:
        matched = _get_bk_collector_config_value_pattern(key).search(config_content)
        if matched:
            value = matched.group("value").strip()
            return value or None
    return None


def _extract_bk_collector_config_int(config_content: str | None, *keys: str) -> int | None:
    value = _extract_bk_collector_config_value(config_content, *keys)
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _infer_bk_collector_json_category(config_content: str | None) -> str:
    lowered = (config_content or "").lower()
    if re.search(r"validator_config[\s\S]{0,500}[\"']?type[\"']?\s*[:=]\s*[\"']?event", lowered):
        return BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT
    if re.search(r"validator_config[\s\S]{0,500}[\"']?type[\"']?\s*[:=]\s*[\"']?time_series", lowered):
        return BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON
    validator_type = (_extract_bk_collector_config_value(config_content, "type") or "").strip().lower()
    if validator_type == "event":
        return BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT
    return BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON


def _mask_bk_collector_platform_config(config_content: str | None) -> str | None:
    if config_content is None:
        return None

    def replacer(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{match.group('quote')}******{match.group('quote')}"

    return BK_COLLECTOR_PLATFORM_SENSITIVE_PATTERN.sub(replacer, config_content)


def _encode_bk_collector_config_ref(protocol: str, secret_name: str, config_key: str) -> str:
    payload = json.dumps(
        {"protocol": protocol, "secret_name": secret_name, "config_key": config_key},
        ensure_ascii=True,
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_bk_collector_config_ref(config_ref: str) -> dict[str, str]:
    try:
        padded = config_ref + "=" * (-len(config_ref) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as error:  # pylint: disable=broad-except
        raise CustomException(message="config_ref 格式无效") from error
    if not isinstance(payload, dict):
        raise CustomException(message="config_ref 格式无效")
    protocol = payload.get("protocol")
    secret_name = payload.get("secret_name")
    config_key = payload.get("config_key")
    if protocol not in BK_COLLECTOR_CONFIG_PROTOCOLS or not secret_name or not config_key:
        raise CustomException(message="config_ref 格式无效")
    return {"protocol": str(protocol), "secret_name": str(secret_name), "config_key": str(config_key)}


def _list_bk_collector_secrets(
    cluster: models.BCSClusterInfo, core_client: k8s_client.CoreV1Api, protocol: str, namespace: str
) -> tuple[list[Any], list[dict[str, Any]]]:
    label_selector, _ = _build_bk_collector_secret_label_selector(cluster.cluster_id, protocol)
    if not label_selector:
        return [], [
            {
                "code": "BK_COLLECTOR_SECRET_CONFIG_MISSING",
                "message": f"protocol({protocol}) has no bk-collector secret config",
            }
        ]

    try:
        secret_list = core_client.list_namespaced_secret(
            namespace=namespace,
            label_selector=label_selector,
        )
    except k8s_client.exceptions.ApiException as error:
        return [], [
            {
                "code": "BK_COLLECTOR_SECRET_LIST_FAILED",
                "message": f"查询 bk-collector {protocol} Secret 失败: {error}",
            }
        ]

    return list(getattr(secret_list, "items", []) or []), []


def _serialize_bk_collector_config_entry(
    entry: dict[str, Any],
    *,
    include_config: bool,
    include_sensitive: bool,
) -> dict[str, Any]:
    protocol = entry["protocol"]
    config_id = entry.get("config_id")
    config_content = entry.get("config_content")
    category = (
        BK_COLLECTOR_CONFIG_PROTOCOL_DEFAULT_CATEGORY.get(protocol) or BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON
    )
    masked_content = config_content
    if protocol == "platform" and not include_sensitive:
        masked_content = _mask_bk_collector_platform_config(config_content)

    item = {
        "config_ref": _encode_bk_collector_config_ref(protocol, entry["secret_name"], entry["config_key"]),
        "category": category,
        "protocol": protocol,
        "namespace": entry["namespace"],
        "secret_name": entry["secret_name"],
        "config_key": entry["config_key"],
        "config_id": config_id,
        "created_at": entry.get("created_at"),
        "resource_version": entry.get("resource_version"),
    }
    if include_config:
        name = str(config_id or entry["config_key"])
        if protocol == "json":
            item["category"] = _infer_bk_collector_json_category(config_content)
        elif protocol in {"prometheus", "log", "apm"}:
            name = _extract_bk_collector_config_value(config_content, "bk_app_name") or name
        elif protocol == "platform":
            name = "APM 平台配置"
        data_ids = {
            key: _extract_bk_collector_config_int(config_content, key)
            for key in ("metric_data_id", "trace_data_id", "log_data_id", "profile_data_id")
        }
        data_ids = {key: value for key, value in data_ids.items() if value}
        item["name"] = name
        item["bk_biz_id"] = _extract_bk_collector_config_int(config_content, "bk_biz_id")
        item["bk_data_id"] = config_id if protocol in {"json", "prometheus", "log"} else None
        item["data_ids"] = data_ids
        item["config"] = masked_content
        item["decode_error"] = entry.get("decode_error")
    return item


def _collect_bk_collector_config_entries(
    cluster: models.BCSClusterInfo,
    bk_tenant_id: str,
    *,
    namespace: str,
    protocols: tuple[str, ...] | None = None,
    keyword: str | None = None,
    target_secret_name: str | None = None,
    target_config_key: str | None = None,
    decode_content: bool = True,
    include_config: bool = False,
    include_sensitive: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    core_client = _get_bk_collector_core_client(cluster)
    raw_entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for protocol in protocols or BK_COLLECTOR_CONFIG_PROTOCOLS:
        secrets, current_warnings = _list_bk_collector_secrets(cluster, core_client, protocol, namespace)
        warnings.extend(current_warnings)
        for secret in secrets:
            metadata = getattr(secret, "metadata", None)
            secret_name = getattr(metadata, "name", "") or ""
            if target_secret_name and secret_name != target_secret_name:
                continue
            secret_namespace = getattr(metadata, "namespace", None) or namespace
            secret_data = getattr(secret, "data", None)
            if not isinstance(secret_data, dict):
                continue
            for config_key, encoded_content in sorted(secret_data.items()):
                if target_config_key and config_key != target_config_key:
                    continue
                if not _match_bk_collector_raw_config_keyword(protocol, secret_name, config_key, keyword):
                    continue
                if include_config or decode_content:
                    config_content, decode_error = _decode_bk_collector_secret_content(encoded_content)
                else:
                    config_content, decode_error = None, None
                raw_entries.append(
                    {
                        "protocol": protocol,
                        "namespace": secret_namespace,
                        "secret_name": secret_name,
                        "config_key": config_key,
                        "config_id": 0 if protocol == "platform" else _extract_bk_collector_config_id(config_key),
                        "config_content": config_content,
                        "decode_error": decode_error,
                        "created_at": serialize_value(getattr(metadata, "creation_timestamp", None)),
                        "resource_version": getattr(metadata, "resource_version", None),
                    }
                )

    entries = [
        _serialize_bk_collector_config_entry(
            entry,
            include_config=include_config,
            include_sensitive=include_sensitive,
        )
        for entry in raw_entries
    ]
    entries.sort(
        key=lambda item: (
            BK_COLLECTOR_CONFIG_CATEGORY_ORDER.get(item["category"], 999),
            str(item.get("config_id") or ""),
            str(item.get("config_key") or ""),
        )
    )
    return entries, warnings


def _filter_bk_collector_config_entries(
    entries: list[dict[str, Any]], category: str | None, config_type: str | None = None
) -> list[dict[str, Any]]:
    if config_type:
        entries = [entry for entry in entries if entry["category"] == config_type]
    if category is None:
        return entries
    if category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT:
        return [
            entry
            for entry in entries
            if entry["category"]
            in {
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON,
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS,
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
            }
        ]
    if category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON:
        return [
            entry
            for entry in entries
            if entry["category"]
            in {
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_JSON,
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_JSON,
                BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_EVENT,
            }
        ]
    if category == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_REPORT_PROMETHEUS:
        return [
            entry for entry in entries if entry["category"] == BK_COLLECTOR_CONFIG_CATEGORY_CUSTOM_METRIC_PROMETHEUS
        ]
    return [entry for entry in entries if entry["category"] == category]


def _base64_decode_with_padding(value: str | bytes) -> bytes:
    raw = value.encode() if isinstance(value, str) else value
    return base64.b64decode(raw + b"=" * (-len(raw) % 4))


def _decode_helm_release_payload(encoded_release: Any) -> dict[str, Any]:
    if encoded_release in (None, ""):
        raise CustomException(message="Helm release Secret 缺少 data.release")
    try:
        first_decoded = _base64_decode_with_padding(str(encoded_release))
        second_decoded = _base64_decode_with_padding(first_decoded)
        release_text = gzip.decompress(second_decoded).decode()
        release = json.loads(release_text)
    except Exception as error:  # pylint: disable=broad-except
        raise CustomException(message=f"Helm release 解码失败: {error}") from error
    if not isinstance(release, dict):
        raise CustomException(message="Helm release 解码结果格式异常")
    return release


def _normalize_helm_release_time(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        seconds = value.get("seconds") or value.get("sec")
        nanos = value.get("nanos") or value.get("nsec") or 0
        try:
            timestamp = int(seconds) + int(nanos) / 1_000_000_000
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return serialize_value(value)


def _read_helm_release_info(release: dict[str, Any]) -> dict[str, Any]:
    info = release.get("info") if isinstance(release.get("info"), dict) else {}
    chart = release.get("chart") if isinstance(release.get("chart"), dict) else {}
    metadata = chart.get("metadata") if isinstance(chart.get("metadata"), dict) else {}
    chart_name = metadata.get("name")
    chart_version = metadata.get("version")
    return {
        "revision": _normalize_optional_data_id(release.get("version")),
        "status": info.get("status"),
        "updated_at": _normalize_helm_release_time(info.get("last_deployed") or info.get("first_deployed")),
        "description": info.get("description"),
        "chart_name": chart_name,
        "chart_version": chart_version,
        "chart": "-".join([str(chart_name), str(chart_version)])
        if chart_name not in (None, "") and chart_version not in (None, "")
        else None,
        "app_version": metadata.get("appVersion") or metadata.get("app_version"),
    }


def _read_helm_release_config(release: dict[str, Any]) -> Any:
    config_value = release.get("config")
    return config_value if isinstance(config_value, dict) else {}


def _encode_bkmonitor_operator_release_ref(namespace: str, secret_name: str) -> str:
    return f"{namespace}{BKMONITOR_OPERATOR_RELEASE_REF_SEPARATOR}{secret_name}"


def _decode_bkmonitor_operator_release_ref(release_ref: str) -> tuple[str | None, str]:
    if BKMONITOR_OPERATOR_RELEASE_REF_SEPARATOR not in release_ref:
        return None, release_ref

    namespace, secret_name = release_ref.split(BKMONITOR_OPERATOR_RELEASE_REF_SEPARATOR, 1)
    namespace = namespace.strip()
    secret_name = secret_name.strip()
    if not namespace or not secret_name:
        raise CustomException(message="release_ref 格式无效")
    return namespace, secret_name


def _serialize_bkmonitor_operator_release_secret(
    secret: Any,
    *,
    namespace: str,
    include_values: bool,
) -> dict[str, Any] | None:
    metadata = getattr(secret, "metadata", None)
    secret_name = getattr(metadata, "name", "") or ""
    matched = BKMONITOR_OPERATOR_RELEASE_SECRET_NAME_PATTERN.match(secret_name)
    if not matched:
        return None
    secret_type = getattr(secret, "type", None)
    if secret_type and secret_type != BKMONITOR_OPERATOR_RELEASE_SECRET_TYPE:
        return None

    secret_data = getattr(secret, "data", None)
    if not isinstance(secret_data, dict):
        secret_data = {}

    item = {
        "release_ref": _encode_bkmonitor_operator_release_ref(
            getattr(metadata, "namespace", None) or namespace,
            secret_name,
        ),
        "release_name": matched.group("release_name"),
        "secret_name": secret_name,
        "namespace": getattr(metadata, "namespace", None) or namespace,
        "revision": int(matched.group("revision")),
        "type": secret_type or BKMONITOR_OPERATOR_RELEASE_SECRET_TYPE,
        "data_count": len(secret_data),
        "created_at": serialize_value(getattr(metadata, "creation_timestamp", None)),
        "resource_version": getattr(metadata, "resource_version", None),
        "decode_error": None,
    }

    try:
        release = _decode_helm_release_payload(secret_data.get("release"))
    except CustomException as error:
        item["decode_error"] = str(error)
        release = {}

    item.update(_read_helm_release_info(release))
    item["revision"] = item.get("revision") or int(matched.group("revision"))
    if include_values:
        item["values"] = _read_helm_release_config(release)
    return item


def _list_bkmonitor_operator_candidate_namespaces(
    core_client: k8s_client.CoreV1Api,
) -> tuple[list[str], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    discovered_namespaces: list[str] = []

    try:
        namespace_list = core_client.list_namespace()
    except k8s_client.exceptions.ApiException as error:
        warnings.append(
            {
                "code": "BKMONITOR_OPERATOR_NAMESPACE_LIST_FAILED",
                "message": f"查询集群 namespace 列表失败: {error}",
            }
        )
    else:
        for namespace in getattr(namespace_list, "items", []) or []:
            namespace_name = getattr(getattr(namespace, "metadata", None), "name", "") or ""
            if BKMONITOR_OPERATOR_NAMESPACE_KEYWORD in namespace_name:
                discovered_namespaces.append(namespace_name)

    namespace_candidates = sorted(set(discovered_namespaces))

    if not namespace_candidates:
        warnings.append(
            {
                "code": "BKMONITOR_OPERATOR_NAMESPACE_EMPTY",
                "message": "未发现包含 bkmonitor-operator 的 namespace",
            }
        )

    return namespace_candidates, warnings


def _list_bkmonitor_operator_release_secrets(
    core_client: k8s_client.CoreV1Api, namespace: str
) -> tuple[list[Any], list[dict[str, Any]]]:
    try:
        secret_list = core_client.list_namespaced_secret(
            namespace=namespace,
            label_selector=BKMONITOR_OPERATOR_HELM_LABEL_SELECTOR,
        )
    except k8s_client.exceptions.ApiException as error:
        return [], [
            {
                "code": "BKMONITOR_OPERATOR_RELEASE_LIST_FAILED",
                "message": f"查询 namespace={namespace} 中的 Helm release Secret 失败: {error}",
            }
        ]
    return list(getattr(secret_list, "items", []) or []), []


def _collect_bkmonitor_operator_releases(
    *,
    core_client: k8s_client.CoreV1Api,
    namespace_candidates: list[str],
    include_values: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for namespace in namespace_candidates:
        secrets, namespace_warnings = _list_bkmonitor_operator_release_secrets(core_client, namespace)
        warnings.extend(namespace_warnings)
        items.extend(
            item
            for item in (
                _serialize_bkmonitor_operator_release_secret(
                    secret,
                    namespace=namespace,
                    include_values=include_values,
                )
                for secret in secrets
            )
            if item is not None
        )
    items.sort(key=_get_bkmonitor_operator_release_sort_key, reverse=True)
    return items, warnings


def _get_bkmonitor_operator_release_sort_key(item: dict[str, Any]) -> tuple[str, int, str, str]:
    return (
        item.get("updated_at") or item.get("created_at") or "",
        item.get("revision") or 0,
        item.get("namespace") or "",
        item.get("secret_name") or "",
    )


def _group_bkmonitor_operator_releases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_items: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        release_name = item.get("release_name") or item.get("secret_name") or "unknown"
        grouped_items.setdefault(str(release_name), []).append(item)

    groups: list[dict[str, Any]] = []
    for release_name, release_items in grouped_items.items():
        release_items.sort(key=_get_bkmonitor_operator_release_sort_key, reverse=True)
        latest_item = release_items[0]
        groups.append(
            {
                "release_name": release_name,
                "latest_revision": latest_item.get("revision"),
                "latest_status": latest_item.get("status"),
                "latest_updated_at": latest_item.get("updated_at"),
                "namespaces": sorted({item["namespace"] for item in release_items if item.get("namespace")}),
                "items": release_items,
            }
        )

    groups.sort(
        key=lambda group: (
            group.get("latest_updated_at") or "",
            group.get("latest_revision") or 0,
            group.get("release_name") or "",
        ),
        reverse=True,
    )
    return groups


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_LIST,
    summary="Admin 查询 BCSClusterInfo 列表",
    description="只读查询 BCSClusterInfo 列表，支持受控过滤、白名单排序和分页。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID 精确匹配",
        "bk_data_id": "可选，DataID 精确匹配；匹配 K8sMetricDataID、CustomMetricDataID、K8sEventDataID、CustomEventDataID、SystemLogDataID、CustomLogDataID 任一字段",
        "cluster_id": "可选，集群 ID 包含匹配",
        "status": "可选，集群状态原始值精确匹配，支持字符串、逗号分隔字符串或列表；不传则不过滤",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}，默认 cluster_id",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010, "page": 1, "page_size": 20},
)
def list_bcs_clusters(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="cluster_id")

    queryset = _build_bcs_cluster_queryset(params, bk_tenant_id).order_by(ordering, "cluster_id")
    clusters, total = paginate_queryset(queryset, page=page, page_size=page_size)

    items = [_serialize_bcs_cluster(c) for c in clusters]

    return build_response(
        operation="bcs_cluster.list",
        func_name=FUNC_BCS_CLUSTER_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DETAIL,
    summary="Admin 查询 BCSClusterInfo 详情",
    description="只读查询 BCSClusterInfo 详情及关联的 DataSource 摘要信息。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，集群 ID",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000"},
)
def get_bcs_cluster_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    data: dict[str, Any] = {"cluster": _serialize_bcs_cluster(cluster)}

    data_ids = sorted({getattr(cluster, field, 0) for field in DATA_ID_FIELD_NAMES if getattr(cluster, field, 0) > 0})

    if data_ids:
        datasources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids).only(
            "bk_data_id", "data_name", "type_label", "source_label", "is_enable"
        )
        datasource_summaries = [
            {
                "bk_data_id": ds.bk_data_id,
                "data_name": ds.data_name,
                "type_label": ds.type_label,
                "source_label": ds.source_label,
                "is_enable": ds.is_enable,
            }
            for ds in datasources.order_by("bk_data_id")
        ]
    else:
        datasource_summaries = []

    data["datasource_summaries"] = datasource_summaries

    return build_response(
        operation="bcs_cluster.detail",
        func_name=FUNC_BCS_CLUSTER_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DATA_ID_LIST,
    summary="Admin 实时查询 BCS 集群 DataID CRD 列表",
    description="inspect 级别能力，通过 Kubernetes CustomObjectsApi 实时读取目标 BCS 集群中的 DataID CRD 列表，只读不写。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "page": 1, "page_size": 20},
)
def list_bcs_cluster_data_ids(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    page, page_size = normalize_pagination(params)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    resources = _list_bcs_data_id_resources(cluster)
    page_resources, total = _paginate_list(resources, page=page, page_size=page_size)
    items = [_serialize_bcs_data_id_resource(resource) for resource in page_resources]

    response = build_response(
        operation="bcs_cluster.data_id_list",
        func_name=FUNC_BCS_CLUSTER_DATA_ID_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DATA_ID_DETAIL,
    summary="Admin 实时查询 BCS 集群 DataID CRD 详情",
    description="inspect 级别能力，通过 Kubernetes CustomObjectsApi 实时读取目标 BCS 集群中的单个 DataID CRD 原始详情，只读不写。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "name": "必填，DataID CRD metadata.name",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "name": "k8smetricdataid"},
)
def get_bcs_cluster_data_id_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    name = params.get("name")
    if name in (None, ""):
        raise CustomException(message="name 为必填项")
    name = str(name).strip()
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    resource = _get_bcs_data_id_resource(cluster, name)
    data = {**_serialize_bcs_data_id_resource(resource), "resource": resource}
    response = build_response(
        operation="bcs_cluster.data_id_detail",
        func_name=FUNC_BCS_CLUSTER_DATA_ID_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_LIST,
    summary="Admin 实时查询 BCS 集群 bk-collector 配置列表",
    description=(
        "inspect 级别能力，通过 Kubernetes CoreV1Api 实时读取目标 BCS 集群内 bk-collector Secret，"
        "展示自定义指标 JSON、自定义指标 Prometheus、自定义事件、日志上报、APM 应用和 APM 平台配置摘要，只读不写。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "category": "可选，配置分类：custom_report_json/custom_report_prometheus/custom_log/apm_application/apm_platform",
        "type": "暂不支持；列表不解码也不查询关联模型，无法区分 json 上报中的指标/事件",
        "keyword": "可选，按 DataID/APM 应用 ID 精确匹配，也支持 Secret 名称或配置 key 包含匹配",
        "use_config_namespace": "可选，默认 false；true 时使用 K8S_OPERATOR_DEPLOY_NAMESPACE 中配置的命名空间",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 10000；列表页通常一次获取当前分类摘要全集后在前端分页",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": "BCS-K8S-00000",
        "category": "custom_report_json",
        "keyword": "1573195",
        "page": 1,
        "page_size": 20,
    },
)
def list_bcs_cluster_bk_collector_configs(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    category = _normalize_bk_collector_config_category(params.get("category"))
    config_type = _normalize_bk_collector_config_type(params.get("type"))
    if config_type:
        raise CustomException(message="bk-collector 配置列表不支持 type 过滤；请在分页后按 DataID 二次查询关联信息")
    keyword = _normalize_bk_collector_keyword(params.get("keyword"))
    use_config_namespace = _normalize_include_sensitive(params.get("use_config_namespace"))
    _page, page_size = normalize_pagination(params, max_page_size=10000)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)
    namespace_context = _get_bk_collector_namespace_context(cluster, use_config_namespace=use_config_namespace)
    protocols = _get_bk_collector_protocols_by_category(category)

    entries, warnings = _collect_bk_collector_config_entries(
        cluster,
        bk_tenant_id,
        namespace=namespace_context["namespace"],
        protocols=protocols,
        keyword=keyword,
        decode_content=False,
    )
    category_counts = {
        category_name: len([entry for entry in entries if entry["category"] == category_name])
        for category_name in BK_COLLECTOR_CONFIG_CATEGORIES
    }
    filtered_entries = _filter_bk_collector_config_entries(entries, category)
    total = len(filtered_entries)

    response = build_response(
        operation="bcs_cluster.bk_collector_config_list",
        func_name=FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": filtered_entries,
            "page": 1,
            "page_size": max(total, page_size, 1),
            "total": total,
            "category_counts": category_counts,
            **namespace_context,
        },
        warnings=warnings,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_DETAIL,
    summary="Admin 实时查询 BCS 集群 bk-collector 单个配置详情",
    description=(
        "inspect 级别能力，通过 Kubernetes CoreV1Api 实时读取目标 BCS 集群内单个 bk-collector Secret 配置。"
        "上报 token 可展示；APM 平台配置中的 secret 默认脱敏，include_sensitive=true 时返回明文。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "config_ref": "必填，列表返回的配置引用",
        "include_sensitive": "可选，默认 false；仅 APM 平台配置使用，true 时返回平台 secret 明文",
        "use_config_namespace": "可选，默认 false；true 时使用 K8S_OPERATOR_DEPLOY_NAMESPACE 中配置的命名空间",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": "BCS-K8S-00000",
        "config_ref": "eyJjb25maWdfa2V5IjogInBsYXRmb3JtLmNvbmYiLCAicHJvdG9jb2wiOiAicGxhdGZvcm0iLCAic2VjcmV0X25hbWUiOiAiYmstY29sbGVjdG9yLXBsYXRmb3JtIn0",
    },
)
def get_bcs_cluster_bk_collector_config_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    config_ref = params.get("config_ref")
    if config_ref in (None, ""):
        raise CustomException(message="config_ref 为必填项")
    ref = _decode_bk_collector_config_ref(str(config_ref))
    include_sensitive = _normalize_include_sensitive(params.get("include_sensitive"))
    use_config_namespace = _normalize_include_sensitive(params.get("use_config_namespace"))
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)
    namespace_context = _get_bk_collector_namespace_context(cluster, use_config_namespace=use_config_namespace)

    entries, warnings = _collect_bk_collector_config_entries(
        cluster,
        bk_tenant_id,
        namespace=namespace_context["namespace"],
        protocols=(ref["protocol"],),
        target_secret_name=ref["secret_name"],
        target_config_key=ref["config_key"],
        include_config=True,
        include_sensitive=include_sensitive,
    )
    config_ref_value = _encode_bk_collector_config_ref(ref["protocol"], ref["secret_name"], ref["config_key"])
    detail = next((entry for entry in entries if entry["config_ref"] == config_ref_value), None)
    if detail is None:
        raise CustomException(
            message=(
                "未找到 bk-collector 配置: "
                f"protocol={ref['protocol']}, secret={ref['secret_name']}, key={ref['config_key']}"
            )
        )

    response = build_response(
        operation="bcs_cluster.bk_collector_config_detail",
        func_name=FUNC_BCS_CLUSTER_BK_COLLECTOR_CONFIG_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={**detail, **namespace_context},
        warnings=warnings,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_LIST,
    summary="Admin 实时查询 BCS 集群 bkmonitor-operator Helm release 列表",
    description=(
        "inspect 级别能力，通过 Kubernetes CoreV1Api 扫描名称包含 bkmonitor-operator 的 namespace，"
        "读取其中的 Helm release Secret，按 release-name 分组展示，只读不写。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "use_config_namespace": "兼容旧参数，当前已忽略；接口会自动扫描候选 namespace",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 1000；按 release-name 分组分页",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "page": 1, "page_size": 20},
)
def list_bcs_cluster_bkmonitor_operator_releases(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    page, page_size = normalize_pagination(params, max_page_size=1000)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)
    core_client = _get_bk_collector_core_client(cluster)

    namespace_candidates, warnings = _list_bkmonitor_operator_candidate_namespaces(core_client)
    items, release_warnings = _collect_bkmonitor_operator_releases(
        core_client=core_client,
        namespace_candidates=namespace_candidates,
    )
    warnings.extend(release_warnings)
    groups = _group_bkmonitor_operator_releases(items)
    page_groups, total = _paginate_list(groups, page=page, page_size=page_size)
    page_items = [item for group in page_groups for item in group["items"]]

    response = build_response(
        operation="bcs_cluster.bkmonitor_operator_release_list",
        func_name=FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": page_items,
            "groups": page_groups,
            "namespace_candidates": namespace_candidates,
            "release_total": len(items),
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        warnings=warnings,
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_DETAIL,
    summary="Admin 实时查询 BCS 集群 bkmonitor-operator Helm release values",
    description=(
        "inspect 级别能力，通过 Kubernetes CoreV1Api 实时读取单个 bkmonitor-operator Helm release Secret，"
        "解码并返回 Helm 部署时传入的 values 配置，只读不写。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "release_ref": "必填，列表返回的 Helm release 引用，格式为 namespace:secret_name",
        "use_config_namespace": "兼容旧参数，当前已忽略；详情读取 release_ref 中的 namespace",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": "BCS-K8S-00000",
        "release_ref": "bkmonitor-operator:sh.helm.release.v1.bkmonitor-operator.v71",
    },
)
def get_bcs_cluster_bkmonitor_operator_release_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    release_ref = params.get("release_ref")
    if release_ref in (None, ""):
        raise CustomException(message="release_ref 为必填项")
    release_ref = str(release_ref).strip()
    namespace, secret_name = _decode_bkmonitor_operator_release_ref(release_ref)
    if not BKMONITOR_OPERATOR_RELEASE_SECRET_NAME_PATTERN.match(secret_name):
        raise CustomException(message="release_ref 格式无效")

    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)
    core_client = _get_bk_collector_core_client(cluster)

    namespace_candidates: list[str] = []
    warnings: list[dict[str, Any]] = []
    if namespace is None:
        namespace_candidates, warnings = _list_bkmonitor_operator_candidate_namespaces(core_client)
        fallback_items, fallback_warnings = _collect_bkmonitor_operator_releases(
            core_client=core_client,
            namespace_candidates=namespace_candidates,
        )
        warnings.extend(fallback_warnings)
        namespace = next(
            (item["namespace"] for item in fallback_items if item["secret_name"] == secret_name),
            None,
        )
        if namespace is None:
            raise CustomException(message=f"未找到 bkmonitor-operator Helm release: release_ref={release_ref}")

    try:
        secret = core_client.read_namespaced_secret(name=secret_name, namespace=namespace)
    except k8s_client.exceptions.ApiException as error:
        if getattr(error, "status", None) == 404:
            raise CustomException(
                message=f"未找到 bkmonitor-operator Helm release: release_ref={release_ref}"
            ) from error
        raise CustomException(message=f"查询 bkmonitor-operator Helm release 失败: {error}") from error

    detail = _serialize_bkmonitor_operator_release_secret(
        secret,
        namespace=namespace,
        include_values=True,
    )
    if detail is None:
        raise CustomException(message=f"bkmonitor-operator Helm release Secret 格式无效: release_ref={release_ref}")

    response = build_response(
        operation="bcs_cluster.bkmonitor_operator_release_detail",
        func_name=FUNC_BCS_CLUSTER_BKMONITOR_OPERATOR_RELEASE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            **detail,
            "namespace_candidates": namespace_candidates,
        },
        warnings=warnings,
    )
    return _mark_inspect_response(response)
