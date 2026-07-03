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

import copy
from typing import Any, cast

from django.db.models import Q

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.collect_plugin import _serialize_version_detail, _select_current_version
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    filter_by_tenant_resource_pairs,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_optional_bool,
    normalize_pagination,
    serialize_value,
)
from kernel_api.rpc.functions.admin.uptime_check import (
    _load_subscription_infos,
    _load_subscription_status_detail,
    _sanitize_subscription_detail_value,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import PluginType

FUNC_COLLECT_CONFIG_LIST = "admin.collect_config.list"
FUNC_COLLECT_CONFIG_DETAIL = "admin.collect_config.detail"
FUNC_COLLECT_CONFIG_VERSION_LIST = "admin.collect_config.version_list"
FUNC_COLLECT_CONFIG_VERSION_DETAIL = "admin.collect_config.version_detail"
FUNC_COLLECT_CONFIG_TARGET_STATUS = "admin.collect_config.target_status"
FUNC_COLLECT_CONFIG_SUBSCRIPTION_DETAIL = "admin.collect_config.subscription_detail"

COLLECT_CONFIG_ORDERING_FIELDS = {"id", "name", "bk_biz_id", "collect_type", "plugin_id", "update_time", "create_time"}
_UNSET = object()


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _normalize_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_ordering(value: Any, allowed_fields: set[str], *, default: str) -> str:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        raise CustomException(message="ordering 必须是字符串")
    normalized = value.strip()
    field = normalized[1:] if normalized.startswith("-") else normalized
    if field not in allowed_fields:
        raise CustomException(message=f"不支持按 {field} 排序")
    return normalized


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_attr(instance: Any, attr: str, default: Any = None) -> Any:
    try:
        value = getattr(instance, attr)
    except Exception:  # noqa: BLE001
        return default
    return value if value is not None else default


def _get_config_queryset():
    return CollectConfigMeta.objects.select_related(
        "deployment_config",
        "deployment_config__plugin_version",
        "deployment_config__plugin_version__config",
        "deployment_config__plugin_version__info",
    )


def _latest_plugin_version(plugin: CollectorPluginMeta | None) -> PluginVersionHistory | None:
    if plugin is None:
        return None
    versions = list(
        PluginVersionHistory.objects.select_related("config", "info").filter(
            bk_tenant_id=plugin.bk_tenant_id,
            plugin_id=plugin.plugin_id,
        )
    )
    return _select_current_version(versions)


def _get_plugin_for_config(config: CollectConfigMeta) -> CollectorPluginMeta | None:
    try:
        return CollectorPluginMeta.objects.get(bk_tenant_id=config.bk_tenant_id, plugin_id=config.plugin_id)
    except CollectorPluginMeta.DoesNotExist:
        return None


def _serialize_label_info(config: CollectConfigMeta) -> Any:
    try:
        return config.label_info
    except Exception:  # noqa: BLE001
        return None


def _safe_need_upgrade(config: CollectConfigMeta) -> bool:
    try:
        return bool(config.need_upgrade)
    except Exception:  # noqa: BLE001
        latest_version = _latest_plugin_version(_get_plugin_for_config(config))
        current_version = config.deployment_config.plugin_version
        if latest_version is None:
            return False
        return latest_version.config_version > current_version.config_version


def _plugin_key(instance: Any) -> tuple[str | None, str]:
    return getattr(instance, "bk_tenant_id", None), str(getattr(instance, "plugin_id", ""))


def _version_sort_key(version: PluginVersionHistory) -> tuple[int, int, str, str, int]:
    return (
        int(getattr(version, "config_version", 0) or 0),
        int(getattr(version, "info_version", 0) or 0),
        str(getattr(version, "create_time", "") or ""),
        str(getattr(version, "update_time", "") or ""),
        int(getattr(version, "id", 0) or 0),
    )


def _select_upgrade_version(versions: list[PluginVersionHistory]) -> PluginVersionHistory | None:
    release_versions = [version for version in versions if version.stage == PluginVersionHistory.Stage.RELEASE]
    packaged_versions = [version for version in release_versions if version.is_packaged]
    candidates = packaged_versions or release_versions
    if not candidates:
        return None
    return sorted(candidates, key=_version_sort_key)[-1]


def _load_collect_config_plugin_context(
    configs: list[CollectConfigMeta],
) -> tuple[
    dict[tuple[str | None, str], CollectorPluginMeta],
    dict[tuple[str | None, str], PluginVersionHistory],
    dict[tuple[str | None, str], PluginVersionHistory],
]:
    plugin_pairs = {_plugin_key(config) for config in configs if config.plugin_id}
    if not plugin_pairs:
        return {}, {}, {}

    plugin_queryset = filter_by_tenant_resource_pairs(CollectorPluginMeta.objects.all(), "plugin_id", plugin_pairs)
    plugins = {_plugin_key(plugin): plugin for plugin in plugin_queryset}

    version_queryset = filter_by_tenant_resource_pairs(
        PluginVersionHistory.objects.select_related("config", "info"),
        "plugin_id",
        plugin_pairs,
    )
    versions_by_plugin: dict[tuple[str | None, str], list[PluginVersionHistory]] = {}
    for version in version_queryset.order_by("bk_tenant_id", "plugin_id", "config_version", "info_version", "id"):
        versions_by_plugin.setdefault(_plugin_key(version), []).append(version)

    latest_versions: dict[tuple[str | None, str], PluginVersionHistory] = {}
    upgrade_versions: dict[tuple[str | None, str], PluginVersionHistory] = {}
    for key, versions in versions_by_plugin.items():
        latest_version = _select_current_version(versions)
        upgrade_version = _select_upgrade_version(versions)
        if latest_version is not None:
            latest_versions[key] = latest_version
        if upgrade_version is not None:
            upgrade_versions[key] = upgrade_version

    return plugins, latest_versions, upgrade_versions


def _calculate_need_upgrade(config: CollectConfigMeta, upgrade_version: PluginVersionHistory | None) -> bool:
    if upgrade_version is None:
        return False

    cache_data = _safe_dict(config.cache_data)
    if _safe_attr(config, "task_status", config.operation_result) == "STOPPED":
        return False
    if int(cache_data.get("total_instance_count") or 0) == 0:
        return False

    current_version = config.deployment_config.plugin_version
    return upgrade_version.config_version > current_version.config_version


def _serialize_collect_config_summary(
    config: CollectConfigMeta,
    *,
    plugin: CollectorPluginMeta | None | object = _UNSET,
    latest_version: PluginVersionHistory | None | object = _UNSET,
    upgrade_version: PluginVersionHistory | None | object = _UNSET,
) -> dict[str, Any]:
    deployment_config: DeploymentConfigVersion = config.deployment_config
    plugin_version = deployment_config.plugin_version
    resolved_plugin = _get_plugin_for_config(config) if plugin is _UNSET else cast(CollectorPluginMeta | None, plugin)
    resolved_latest_version = (
        _latest_plugin_version(resolved_plugin)
        if latest_version is _UNSET
        else cast(PluginVersionHistory | None, latest_version)
    )
    need_upgrade = (
        _safe_need_upgrade(config)
        if upgrade_version is _UNSET
        else _calculate_need_upgrade(config, cast(PluginVersionHistory | None, upgrade_version))
    )
    cache_data = _safe_dict(config.cache_data)
    target_nodes = _safe_list(deployment_config.target_nodes)
    total_instance_count = int(cache_data.get("total_instance_count") or len(target_nodes))
    error_instance_count = int(cache_data.get("error_instance_count") or 0)
    return {
        "id": config.id,
        "bk_tenant_id": config.bk_tenant_id,
        "name": config.name,
        "bk_biz_id": config.bk_biz_id,
        "space_name": cache_data.get("space_name"),
        "collect_type": config.collect_type,
        "plugin_id": config.plugin_id,
        "plugin_display_name": getattr(plugin_version.info, "plugin_display_name", None),
        "status": _safe_attr(config, "config_status", config.operation_result),
        "task_status": _safe_attr(config, "task_status", config.operation_result),
        "target_object_type": config.target_object_type,
        "target_node_type": deployment_config.target_node_type,
        "target_nodes_count": len(target_nodes),
        "subscription_id": deployment_config.subscription_id or None,
        "need_upgrade": need_upgrade,
        "config_version": plugin_version.config_version,
        "info_version": plugin_version.info_version,
        "latest_config_version": getattr(resolved_latest_version, "config_version", None),
        "latest_info_version": getattr(resolved_latest_version, "info_version", None),
        "error_instance_count": error_instance_count,
        "total_instance_count": total_instance_count,
        "running_tasks": _safe_list(cache_data.get("running_tasks")),
        "last_operation": config.last_operation,
        "operation_result": config.operation_result,
        "label": config.label,
        "label_info": _serialize_label_info(config),
        "update_user": getattr(config, "update_user", None),
        "update_time": serialize_value(getattr(config, "update_time", None)),
        "create_user": getattr(config, "create_user", None),
        "create_time": serialize_value(getattr(config, "create_time", None)),
    }


def _build_subscription_summary(
    config: CollectConfigMeta, deployment_config: DeploymentConfigVersion | None = None
) -> dict[str, Any] | None:
    deployment_config = deployment_config or config.deployment_config
    subscription_id = deployment_config.subscription_id
    if not subscription_id:
        return None
    params = _safe_dict(deployment_config.params)
    return {
        "config_id": config.id,
        "deployment_id": deployment_config.id,
        "subscription_id": subscription_id,
        "bk_biz_id": config.bk_biz_id,
        "enable": None,
        "is_deleted": False,
        "config_status": "not_loaded",
        "category": None,
        "scope_summary": {
            "object_type": config.target_object_type,
            "node_type": deployment_config.target_node_type,
            "nodes_count": len(_safe_list(deployment_config.target_nodes)),
        },
        "steps": [
            {
                "id": "bkmonitorlog" if config.collect_type == PluginType.LOG else "bkmonitorbeat",
                "plugin_name": config.plugin_id,
                "plugin_version": deployment_config.plugin_version.version,
                "context_summary": {
                    "params_keys": sorted(params.keys())[:20],
                },
            }
        ],
    }


def _augment_collect_special_design(
    config: CollectConfigMeta,
    plugin_info: dict[str, Any],
    deployment_config: DeploymentConfigVersion | None = None,
) -> dict[str, Any]:
    deployment_config = deployment_config or config.deployment_config
    deployment_params = copy.deepcopy(deployment_config.params or {})
    special_design = plugin_info.get("special_design")
    if isinstance(special_design, dict):
        sections = list(special_design.get("sections") or [])
        sections.append({"title": "采集配置参数", "value": deployment_params})
        special_design["sections"] = sections
        return plugin_info

    if config.collect_type == PluginType.PROCESS:
        plugin_info["special_design"] = {
            "kind": "process",
            "title": "进程采集专属信息",
            "summary": "进程采集重点关注匹配规则、排除规则、维度提取规则和端口采集配置。",
            "sections": [{"title": "采集配置参数", "value": deployment_params}],
        }
    elif config.collect_type == PluginType.LOG:
        plugin_info["special_design"] = {
            "kind": "log_keyword",
            "title": "日志关键字专属信息",
            "summary": "日志关键字采集重点关注日志路径、字符集、过滤 pattern、关键字规则和事件 DataID。",
            "sections": [{"title": "采集配置参数", "value": deployment_params}],
        }
    return plugin_info


def _serialize_plugin_info_for_deployment(
    config: CollectConfigMeta, deployment_config: DeploymentConfigVersion
) -> dict[str, Any]:
    plugin = _get_plugin_for_config(config)
    plugin_version = deployment_config.plugin_version
    if plugin is None:
        plugin_info: dict[str, Any] = {
            "bk_tenant_id": plugin_version.bk_tenant_id,
            "plugin_id": plugin_version.plugin_id,
            "version": plugin_version.version,
            "config_version": plugin_version.config_version,
            "info_version": plugin_version.info_version,
            "stage": plugin_version.stage,
            "plugin_display_name": plugin_version.info.plugin_display_name,
            "plugin_type": config.collect_type,
            "collector_json": copy.deepcopy(plugin_version.config.collector_json or {}),
            "config_json": copy.deepcopy(plugin_version.config.config_json or []),
            "metric_json": copy.deepcopy(plugin_version.info.metric_json or []),
            "description_md": plugin_version.info.description_md,
            "is_support_remote": plugin_version.config.is_support_remote,
            "enable_field_blacklist": plugin_version.info.enable_field_blacklist,
            "result_tables": [],
            "data_ids": [],
            "special_design": None,
        }
    else:
        plugin_info = _serialize_version_detail(plugin_version, plugin)
    return _augment_collect_special_design(config, plugin_info, deployment_config)


def _serialize_deployment_version_summary(
    config: CollectConfigMeta, deployment_config: DeploymentConfigVersion
) -> dict[str, Any]:
    plugin_version = deployment_config.plugin_version
    target_nodes = _safe_list(deployment_config.target_nodes)
    return {
        "id": deployment_config.id,
        "bk_tenant_id": config.bk_tenant_id,
        "config_id": config.id,
        "bk_biz_id": config.bk_biz_id,
        "name": config.name,
        "plugin_id": config.plugin_id,
        "plugin_version": plugin_version.version,
        "config_version": plugin_version.config_version,
        "info_version": plugin_version.info_version,
        "target_object_type": config.target_object_type,
        "target_node_type": deployment_config.target_node_type,
        "target_nodes_count": len(target_nodes),
        "subscription_id": deployment_config.subscription_id or None,
        "parent_id": deployment_config.parent_id,
        "is_current": deployment_config.id == config.deployment_config_id,
        "create_user": getattr(deployment_config, "create_user", None),
        "create_time": serialize_value(getattr(deployment_config, "create_time", None)),
        "update_user": getattr(deployment_config, "update_user", None),
        "update_time": serialize_value(getattr(deployment_config, "update_time", None)),
    }


def _serialize_deployment_version_detail(
    config: CollectConfigMeta, deployment_config: DeploymentConfigVersion
) -> dict[str, Any]:
    cache_data = _safe_dict(config.cache_data) if deployment_config.id == config.deployment_config_id else {}
    detail = _serialize_deployment_version_summary(config, deployment_config)
    detail.update(
        {
            "target_nodes": copy.deepcopy(deployment_config.target_nodes or []),
            "target": cache_data.get("target") or cache_data.get("target_info") or [],
            "params": copy.deepcopy(deployment_config.params or {}),
            "remote_collecting_host": copy.deepcopy(deployment_config.remote_collecting_host),
            "task_ids": copy.deepcopy(deployment_config.task_ids),
            "plugin_info": _serialize_plugin_info_for_deployment(config, deployment_config),
            "subscription_summary": _build_subscription_summary(config, deployment_config),
            "warnings": [],
        }
    )
    return detail


def _serialize_collect_config_detail(config: CollectConfigMeta) -> dict[str, Any]:
    summary = _serialize_collect_config_summary(config)
    cache_data = _safe_dict(config.cache_data)
    summary.update(
        {
            "deployment_id": config.deployment_config_id,
            "target_nodes": copy.deepcopy(config.deployment_config.target_nodes or []),
            "target": cache_data.get("target") or cache_data.get("target_info") or [],
            "params": copy.deepcopy(config.deployment_config.params or {}),
            "remote_collecting_host": copy.deepcopy(config.deployment_config.remote_collecting_host),
            "plugin_info": _serialize_plugin_info_for_deployment(config, config.deployment_config),
            "subscription_summary": _build_subscription_summary(config, config.deployment_config),
            "warnings": [],
        }
    )
    return summary


def _cache_json_contains(field: str, value: Any) -> str:
    if isinstance(value, bool):
        normalized_value = str(value).lower()
    else:
        normalized_value = f'"{value}"'
    return f'"{field}": {normalized_value}'


def _paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


def _get_collect_config(bk_tenant_id: str, config_id: int, bk_biz_id: int | None = None) -> CollectConfigMeta:
    queryset = _get_config_queryset().filter(bk_tenant_id=bk_tenant_id, id=config_id)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    config = queryset.first()
    if config is None:
        raise CustomException(message=f"未找到采集配置: id={config_id}")
    return config


def _get_deployment_version(
    config: CollectConfigMeta,
    *,
    deployment_id: int | None = None,
    config_version: int | None = None,
    info_version: int | None = None,
) -> DeploymentConfigVersion:
    if deployment_id is None and config_version is None and info_version is None:
        return config.deployment_config

    queryset = DeploymentConfigVersion.objects.select_related(
        "plugin_version", "plugin_version__config", "plugin_version__info"
    ).filter(config_meta_id=config.id)
    if deployment_id is not None:
        queryset = queryset.filter(id=deployment_id)
    if config_version is not None:
        queryset = queryset.filter(plugin_version__config_version=config_version)
    if info_version is not None:
        queryset = queryset.filter(plugin_version__info_version=info_version)

    deployment_config = queryset.order_by("-id").first()
    if deployment_config is None:
        raise CustomException(message=f"未找到采集配置 {config.id} 的部署版本")
    return deployment_config


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_LIST,
    summary="Admin 查询插件采集配置列表",
    description="只读分页查询 CollectConfigMeta，展示当前版本、最新版本、状态、订阅 ID 和目标摘要。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID",
        "id": "可选，采集配置 ID",
        "search": "可选，匹配 ID / 名称 / plugin_id",
        "plugin_id": "可选，插件 ID 包含匹配",
        "collect_type": "可选，采集方式",
        "status": "可选，配置状态",
        "task_status": "可选，任务状态",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "need_upgrade": "可选，true / false",
        "target_object_type": "可选，采集对象类型",
        "target_node_type": "可选，采集目标类型",
        "refresh_status": "可选，true / false；保留字段，列表仍不自动访问 NodeMan",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "page": 1, "page_size": 20},
)
def list_collect_configs(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = _normalize_ordering(params.get("ordering"), COLLECT_CONFIG_ORDERING_FIELDS, default="-update_time")

    queryset = filter_by_bk_tenant_id(_get_config_queryset().all(), bk_tenant_id)
    config_id = _normalize_int(params.get("id"), "id")
    if config_id is not None:
        queryset = queryset.filter(id=config_id)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    search = _normalize_string(params.get("search"))
    if search:
        search_query = Q(name__icontains=search) | Q(plugin_id__icontains=search)
        try:
            search_query |= Q(id=int(search))
        except (TypeError, ValueError):
            pass
        queryset = queryset.filter(search_query)
    plugin_id = _normalize_string(params.get("plugin_id"))
    if plugin_id:
        queryset = queryset.filter(plugin_id__icontains=plugin_id)
    collect_type = _normalize_string(params.get("collect_type"))
    if collect_type:
        queryset = queryset.filter(collect_type=collect_type)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id")
    if subscription_id is not None:
        queryset = queryset.filter(deployment_config__subscription_id=subscription_id)
    target_object_type = _normalize_string(params.get("target_object_type"))
    if target_object_type:
        queryset = queryset.filter(target_object_type=target_object_type)
    target_node_type = _normalize_string(params.get("target_node_type"))
    if target_node_type:
        queryset = queryset.filter(deployment_config__target_node_type=target_node_type)

    status = _normalize_string(params.get("status"))
    if status:
        queryset = queryset.filter(cache_data__contains=_cache_json_contains("status", status))
    task_status = _normalize_string(params.get("task_status"))
    if task_status:
        queryset = queryset.filter(cache_data__contains=_cache_json_contains("task_status", task_status))
    need_upgrade = normalize_optional_bool(params.get("need_upgrade"), "need_upgrade")
    if need_upgrade is not None:
        queryset = queryset.filter(cache_data__contains=_cache_json_contains("need_upgrade", need_upgrade))

    type_list = [
        {"id": collect_type_item, "name": collect_type_item}
        for collect_type_item in sorted(
            {
                collect_type_item
                for collect_type_item in queryset.values_list("collect_type", flat=True).distinct()
                if collect_type_item
            }
        )
    ]

    ordered_queryset = queryset.order_by(ordering, "-id")
    total = ordered_queryset.count()
    offset = (page - 1) * page_size
    page_configs = list(ordered_queryset[offset : offset + page_size])
    plugins, latest_versions, upgrade_versions = _load_collect_config_plugin_context(page_configs)
    page_items = [
        _serialize_collect_config_summary(
            config,
            plugin=plugins.get(_plugin_key(config)),
            latest_version=latest_versions.get(_plugin_key(config)),
            upgrade_version=upgrade_versions.get(_plugin_key(config)),
        )
        for config in page_configs
    ]
    return build_response(
        operation="collect_config.list",
        func_name=FUNC_COLLECT_CONFIG_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": page_items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "type_list": type_list,
        },
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_DETAIL,
    summary="Admin 查询插件采集配置详情",
    description="只读查询采集配置、当前插件版本、目标、参数和订阅摘要。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，采集配置 ID", "bk_biz_id": "可选，业务 ID"},
    example_params={"bk_tenant_id": "system", "id": 203, "bk_biz_id": 2},
)
def get_collect_config_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    config_id = _normalize_int(params.get("id"), "id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    config = _get_collect_config(bk_tenant_id, config_id, bk_biz_id)
    return build_response(
        operation="collect_config.detail",
        func_name=FUNC_COLLECT_CONFIG_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"config": _serialize_collect_config_detail(config)},
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_VERSION_LIST,
    summary="Admin 查询插件采集部署版本列表",
    description="只读分页查询单个 CollectConfigMeta 关联的 DeploymentConfigVersion 历史，用于采集详情页切换下发配置版本。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，采集配置 ID",
        "bk_biz_id": "可选，业务 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "id": 203, "bk_biz_id": 2, "page": 1, "page_size": 20},
)
def list_collect_config_versions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    config_id = _normalize_int(params.get("id"), "id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    config = _get_collect_config(bk_tenant_id, config_id, bk_biz_id)

    queryset = (
        DeploymentConfigVersion.objects.select_related(
            "plugin_version", "plugin_version__config", "plugin_version__info"
        )
        .filter(config_meta_id=config.id)
        .order_by("-id")
    )
    summaries = [_serialize_deployment_version_summary(config, deployment_config) for deployment_config in queryset]
    page_items, total = _paginate_items(summaries, page=page, page_size=page_size)
    return build_response(
        operation="collect_config.version_list",
        func_name=FUNC_COLLECT_CONFIG_VERSION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": page_items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_VERSION_DETAIL,
    summary="Admin 查询插件采集部署版本详情",
    description="只读查询单个 DeploymentConfigVersion 的目标、参数、远程采集、订阅摘要和关联插件版本信息。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，采集配置 ID",
        "bk_biz_id": "可选，业务 ID",
        "deployment_id": "可选，DeploymentConfigVersion ID；不传时返回当前部署版本",
        "config_version": "可选，关联插件 config_version",
        "info_version": "可选，关联插件 info_version",
    },
    example_params={"bk_tenant_id": "system", "id": 203, "bk_biz_id": 2, "deployment_id": 92003},
)
def get_collect_config_version_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    config_id = _normalize_int(params.get("id"), "id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    deployment_id = _normalize_int(params.get("deployment_id"), "deployment_id")
    config_version = _normalize_int(params.get("config_version"), "config_version")
    info_version = _normalize_int(params.get("info_version"), "info_version")
    config = _get_collect_config(bk_tenant_id, config_id, bk_biz_id)
    deployment_config = _get_deployment_version(
        config,
        deployment_id=deployment_id,
        config_version=config_version,
        info_version=info_version,
    )
    return build_response(
        operation="collect_config.version_detail",
        func_name=FUNC_COLLECT_CONFIG_VERSION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"version": _serialize_deployment_version_detail(config, deployment_config)},
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_TARGET_STATUS,
    summary="Admin 实时查询插件采集实例状态",
    description="只读按需查询单个采集配置的下发实例状态；不会在列表或详情首屏自动触发。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，采集配置 ID",
        "bk_biz_id": "必填，业务 ID",
        "diff": "可选，是否只返回差异，默认 false",
    },
    example_params={"bk_tenant_id": "system", "id": 203, "bk_biz_id": 2, "diff": False},
)
def get_collect_config_target_status(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    config_id = _normalize_int(params.get("id"), "id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    diff = normalize_optional_bool(params.get("diff"), "diff")
    config = _get_collect_config(bk_tenant_id, config_id, bk_biz_id)
    warnings: list[dict[str, Any]] = []
    try:
        data = resource.collecting.collect_target_status(
            bk_biz_id=bk_biz_id,
            id=config_id,
            diff=False if diff is None else diff,
        )
    except Exception as error:  # noqa: BLE001
        warnings.append({"code": "LOAD_COLLECT_TARGET_STATUS_FAILED", "message": str(error)})
        data = {"config_info": config.get_info(), "contents": []}
    return build_response(
        operation="collect_config.target_status",
        func_name=FUNC_COLLECT_CONFIG_TARGET_STATUS,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_CONFIG_SUBSCRIPTION_DETAIL,
    summary="Admin 实时查询插件采集 NodeMan 订阅详情",
    description="只读按需查询单个采集配置的 NodeMan 订阅配置和实例状态，返回前遮罩敏感字段。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，采集配置 ID",
        "bk_biz_id": "可选，业务 ID",
        "deployment_id": "可选，DeploymentConfigVersion ID；用于查询历史下发版本关联订阅",
        "subscription_id": "必填，NodeMan 订阅 ID",
    },
    example_params={"bk_tenant_id": "system", "id": 203, "bk_biz_id": 2, "subscription_id": 82003},
)
def get_collect_config_subscription_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    config_id = _normalize_int(params.get("id"), "id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    deployment_id = _normalize_int(params.get("deployment_id"), "deployment_id")
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id", required=True)
    config = _get_collect_config(bk_tenant_id, config_id, bk_biz_id)
    deployment_config = _get_deployment_version(config, deployment_id=deployment_id)
    if deployment_config.subscription_id and deployment_config.subscription_id != subscription_id:
        raise CustomException(message=f"采集配置 {config_id} 未关联订阅: subscription_id={subscription_id}")

    info_map, info_warnings = _load_subscription_infos(bk_tenant_id=bk_tenant_id, subscription_ids=[subscription_id])
    status_detail, status_warnings = _load_subscription_status_detail(
        bk_tenant_id=bk_tenant_id,
        subscription_id=subscription_id,
    )
    info = info_map.get(subscription_id)
    subscription = {
        "config_id": config.id,
        "subscription_id": subscription_id,
        "config_status": "available" if info else "missing",
        "subscription": _sanitize_subscription_detail_value(info) if info else None,
        "config_detail": _sanitize_subscription_detail_value(info) if info else None,
        "status_detail": _sanitize_subscription_detail_value(status_detail) if status_detail is not None else None,
        "warnings": info_warnings + status_warnings,
    }
    return build_response(
        operation="collect_config.subscription_detail",
        func_name=FUNC_COLLECT_CONFIG_SUBSCRIPTION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"subscription": subscription},
        warnings=info_warnings + status_warnings,
    )
