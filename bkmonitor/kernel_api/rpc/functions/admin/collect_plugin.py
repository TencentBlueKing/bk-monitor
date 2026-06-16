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
from collections import defaultdict
from typing import Any

from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value, When

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
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
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.signature import Signature

FUNC_COLLECT_PLUGIN_LIST = "admin.collect_plugin.list"
FUNC_COLLECT_PLUGIN_DETAIL = "admin.collect_plugin.detail"
FUNC_COLLECT_PLUGIN_VERSION_LIST = "admin.collect_plugin.version_list"
FUNC_COLLECT_PLUGIN_VERSION_DETAIL = "admin.collect_plugin.version_detail"

PLUGIN_ORDERING_FIELDS = {"plugin_id", "bk_biz_id", "plugin_type", "tag", "label", "update_time", "create_time"}
VERSION_ORDERING_FIELDS = {"config_version", "info_version", "stage", "create_time", "update_time"}


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


def _version_sort_key(version: PluginVersionHistory) -> tuple[int, int, int, str, str]:
    return (
        int(getattr(version, "config_version", 0) or 0),
        int(getattr(version, "info_version", 0) or 0),
        int(getattr(version, "id", 0) or 0),
        str(getattr(version, "create_time", "") or ""),
        str(getattr(version, "update_time", "") or ""),
    )


def _select_current_version(versions: list[PluginVersionHistory]) -> PluginVersionHistory | None:
    release_versions = [version for version in versions if version.stage == PluginVersionHistory.Stage.RELEASE]
    candidates = release_versions or versions
    if not candidates:
        return None
    return sorted(candidates, key=_version_sort_key)[-1]


def _plugin_key(instance: Any) -> tuple[str | None, str]:
    return getattr(instance, "bk_tenant_id", None), str(getattr(instance, "plugin_id", ""))


def _serialize_logo(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _safe_signature(version: PluginVersionHistory) -> str:
    signature = getattr(version, "signature", "")
    if not signature:
        return ""
    try:
        return Signature(signature).dumps2yaml()
    except Exception:  # noqa: BLE001
        return ""


def _safe_is_safety(version: PluginVersionHistory) -> bool:
    try:
        return bool(version.is_safety)
    except Exception:  # noqa: BLE001
        return False


def _safe_os_type_list(version: PluginVersionHistory) -> list[str]:
    try:
        return list(version.os_type_list)
    except Exception:  # noqa: BLE001
        return []


def _safe_collecting_config_count(version: PluginVersionHistory) -> int:
    try:
        return int(version.collecting_config_count)
    except Exception:  # noqa: BLE001
        return 0


def _extract_data_ids(value: Any) -> list[int]:
    data_ids: set[int] = set()

    def walk(item: Any, key: str | None = None) -> None:
        if isinstance(item, dict):
            for child_key, child_value in item.items():
                walk(child_value, str(child_key))
            return
        if isinstance(item, list):
            for child in item:
                walk(child, key)
            return
        if key and key.lower() in {"dataid", "data_id", "bk_data_id", "metric_data_id", "event_data_id"}:
            try:
                data_id = int(item)
            except (TypeError, ValueError):
                return
            if data_id > 0:
                data_ids.add(data_id)

    walk(value)
    return sorted(data_ids)


def _metric_json_with_table_ids(plugin: CollectorPluginMeta, version: PluginVersionHistory) -> list[dict[str, Any]]:
    metric_json = copy.deepcopy(version.info.metric_json or [])
    if not isinstance(metric_json, list):
        return []

    for table in metric_json:
        if not isinstance(table, dict):
            continue
        if table.get("table_id"):
            continue
        table_name = table.get("table_name")
        if not table_name:
            continue
        try:
            table["table_id"] = PluginVersionHistory.get_result_table_id(plugin, str(table_name))
        except Exception:  # noqa: BLE001
            table["table_id"] = f"{plugin.plugin_type}_{plugin.plugin_id}.{table_name}".lower()
    return metric_json


def _build_special_design(
    plugin: CollectorPluginMeta,
    version: PluginVersionHistory,
    metric_json: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if plugin.plugin_type == PluginType.PROCESS:
        return {
            "kind": "process",
            "title": "进程采集专属信息",
            "summary": "进程插件固定使用 bkmonitorbeat 的进程配置，重点关注匹配规则、端口和性能指标归属。",
            "sections": [
                {
                    "title": "指标归属",
                    "items": [
                        {"name": table.get("table_name"), "table_id": table.get("table_id")}
                        for table in metric_json
                        if isinstance(table, dict)
                    ],
                },
                {"title": "采集器配置", "value": version.config.collector_json or {}},
                {"title": "参数配置", "value": version.config.config_json or []},
            ],
        }

    if plugin.plugin_type == PluginType.LOG:
        return {
            "kind": "log_keyword",
            "title": "日志关键字专属信息",
            "summary": "日志关键字插件属于监控事件采集，重点关注日志路径、过滤规则、关键字规则和事件 DataID。",
            "sections": [
                {"title": "参数配置", "value": version.config.config_json or []},
                {
                    "title": "事件结果表",
                    "items": [
                        {"name": table.get("table_name"), "table_id": table.get("table_id")}
                        for table in metric_json
                        if isinstance(table, dict)
                    ],
                },
            ],
        }

    if plugin.plugin_type in {PluginType.SNMP, PluginType.SNMP_TRAP}:
        return {
            "kind": "snmp",
            "title": "SNMP 专属设计暂缓",
            "summary": "本期只展示基础信息和原始配置，OID、认证和 Trap 参数后续单独展开。",
            "sections": [],
        }

    return None


def _serialize_version_summary(version: PluginVersionHistory, plugin: CollectorPluginMeta) -> dict[str, Any]:
    version.plugin = plugin
    return {
        "id": getattr(version, "id", None),
        "bk_tenant_id": version.bk_tenant_id,
        "plugin_id": version.plugin_id,
        "version": version.version,
        "config_version": version.config_version,
        "info_version": version.info_version,
        "stage": version.stage,
        "version_log": version.version_log,
        "is_packaged": version.is_packaged,
        "is_official": version.is_official,
        "is_safety": _safe_is_safety(version),
        "os_type_list": _safe_os_type_list(version),
        "collecting_config_count": _safe_collecting_config_count(version),
        "create_user": getattr(version, "create_user", None),
        "create_time": serialize_value(getattr(version, "create_time", None)),
        "update_user": getattr(version, "update_user", None),
        "update_time": serialize_value(getattr(version, "update_time", None)),
    }


def _serialize_version_detail(version: PluginVersionHistory, plugin: CollectorPluginMeta) -> dict[str, Any]:
    version.plugin = plugin
    metric_json = _metric_json_with_table_ids(plugin, version)
    config_json = copy.deepcopy(version.config.config_json or [])
    collector_json = copy.deepcopy(version.config.collector_json or {})
    result_tables = sorted(
        {str(table.get("table_id")) for table in metric_json if isinstance(table, dict) and table.get("table_id")}
    )
    data_ids = sorted(
        set(_extract_data_ids(config_json) + _extract_data_ids(collector_json) + _extract_data_ids(metric_json))
    )
    return {
        **_serialize_version_summary(version, plugin),
        "plugin_display_name": version.info.plugin_display_name,
        "plugin_type": plugin.plugin_type,
        "tag": plugin.tag,
        "label": plugin.label,
        "logo": _serialize_logo(version.info.logo_content),
        "collector_json": collector_json,
        "config_json": config_json,
        "metric_json": metric_json,
        "description_md": version.info.description_md,
        "signature": _safe_signature(version),
        "is_support_remote": version.config.is_support_remote,
        "enable_field_blacklist": version.info.enable_field_blacklist,
        "is_split_measurement": _safe_is_split_measurement(plugin),
        "result_tables": result_tables,
        "data_ids": data_ids,
        "special_design": _build_special_design(plugin, version, metric_json),
    }


def _safe_is_split_measurement(plugin: CollectorPluginMeta) -> bool | None:
    try:
        return bool(plugin.is_split_measurement)
    except Exception:  # noqa: BLE001
        return None


def _serialize_plugin_summary(
    plugin: CollectorPluginMeta,
    version: PluginVersionHistory | None,
    related_conf_count: int,
) -> dict[str, Any]:
    if version is None:
        return {
            "bk_tenant_id": plugin.bk_tenant_id,
            "plugin_id": plugin.plugin_id,
            "plugin_display_name": plugin.plugin_id,
            "plugin_type": plugin.plugin_type,
            "tag": plugin.tag,
            "label": plugin.label,
            "label_info": None,
            "bk_biz_id": plugin.bk_biz_id,
            "is_global": plugin.is_global,
            "is_internal": plugin.is_internal,
            "is_official": False,
            "is_safety": False,
            "is_support_remote": False,
            "stage": "",
            "status": "missing_version",
            "config_version": 0,
            "info_version": 0,
            "version": "0.0",
            "related_conf_count": related_conf_count,
            "release_version_count": 0,
            "os_type_list": [],
            "create_user": getattr(plugin, "create_user", None),
            "create_time": serialize_value(getattr(plugin, "create_time", None)),
            "update_user": getattr(plugin, "update_user", None),
            "update_time": serialize_value(getattr(plugin, "update_time", None)),
        }

    version.plugin = plugin
    return {
        "bk_tenant_id": plugin.bk_tenant_id,
        "plugin_id": plugin.plugin_id,
        "plugin_display_name": version.info.plugin_display_name or plugin.plugin_id,
        "plugin_type": plugin.plugin_type,
        "tag": plugin.tag,
        "label": plugin.label,
        "label_info": None,
        "bk_biz_id": plugin.bk_biz_id,
        "is_global": plugin.is_global,
        "is_internal": plugin.is_internal,
        "is_official": version.is_official,
        "is_safety": _safe_is_safety(version),
        "is_support_remote": version.config.is_support_remote,
        "stage": version.stage,
        "status": "normal" if version.is_release else "draft",
        "config_version": version.config_version,
        "info_version": version.info_version,
        "version": version.version,
        "related_conf_count": related_conf_count,
        "release_version_count": 0,
        "os_type_list": _safe_os_type_list(version),
        "create_user": getattr(plugin, "create_user", None),
        "create_time": serialize_value(getattr(plugin, "create_time", None)),
        "update_user": getattr(version, "update_user", None),
        "update_time": serialize_value(getattr(version, "update_time", None)),
    }


def _load_versions_by_plugin_key(
    plugin_pairs: set[tuple[str | None, str]],
) -> dict[tuple[str | None, str], list[PluginVersionHistory]]:
    if not plugin_pairs:
        return {}
    queryset = filter_by_tenant_resource_pairs(
        PluginVersionHistory.objects.select_related("config", "info"),
        "plugin_id",
        plugin_pairs,
    )
    versions: dict[tuple[str | None, str], list[PluginVersionHistory]] = defaultdict(list)
    for version in queryset.order_by("bk_tenant_id", "plugin_id", "config_version", "info_version", "id"):
        versions[_plugin_key(version)].append(version)
    return versions


def _collect_config_counts(plugin_pairs: set[tuple[str | None, str]]) -> dict[tuple[str | None, str], int]:
    if not plugin_pairs:
        return {}
    queryset = filter_by_tenant_resource_pairs(CollectConfigMeta.objects.all(), "plugin_id", plugin_pairs)
    counts: dict[tuple[str | None, str], int] = {}
    for item in queryset.values("bk_tenant_id", "plugin_id").annotate(total=Count("id")).order_by():
        counts[(item["bk_tenant_id"], str(item["plugin_id"]))] = int(item["total"])
    return counts


def _release_version_counts(
    versions_by_plugin: dict[tuple[str | None, str], list[PluginVersionHistory]],
) -> dict[tuple[str | None, str], int]:
    return {
        plugin_id: len([version for version in versions if version.stage == PluginVersionHistory.Stage.RELEASE])
        for plugin_id, versions in versions_by_plugin.items()
    }


def _current_version_queryset() -> Any:
    return (
        PluginVersionHistory.objects.filter(
            bk_tenant_id=OuterRef("bk_tenant_id"),
            plugin_id=OuterRef("plugin_id"),
        )
        .annotate(
            release_order=Case(
                When(stage=PluginVersionHistory.Stage.RELEASE, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-release_order", "-config_version", "-info_version", "-id")
    )


def _annotate_current_version_fields(queryset: Any) -> Any:
    current_version_queryset = _current_version_queryset()
    return queryset.annotate(
        current_config_version=Subquery(current_version_queryset.values("config_version")[:1]),
        current_stage=Subquery(current_version_queryset.values("stage")[:1]),
        current_plugin_display_name=Subquery(current_version_queryset.values("info__plugin_display_name")[:1]),
        current_is_support_remote=Subquery(current_version_queryset.values("config__is_support_remote")[:1]),
    )


def _annotate_has_collect_config(queryset: Any) -> Any:
    collect_config_queryset = CollectConfigMeta.objects.filter(
        bk_tenant_id=OuterRef("bk_tenant_id"),
        plugin_id=OuterRef("plugin_id"),
    )
    return queryset.annotate(has_collect_config_flag=Exists(collect_config_queryset))


def _paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


def _get_plugin(bk_tenant_id: str, plugin_id: str) -> CollectorPluginMeta:
    try:
        return CollectorPluginMeta.objects.get(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    except CollectorPluginMeta.DoesNotExist as error:
        raise CustomException(message=f"未找到采集插件: plugin_id={plugin_id}") from error


def _resolve_version(plugin: CollectorPluginMeta, params: dict[str, Any]) -> PluginVersionHistory:
    queryset = PluginVersionHistory.objects.select_related("config", "info").filter(
        bk_tenant_id=plugin.bk_tenant_id,
        plugin_id=plugin.plugin_id,
    )
    config_version = _normalize_int(params.get("config_version"), "config_version")
    info_version = _normalize_int(params.get("info_version"), "info_version")
    if config_version is not None:
        queryset = queryset.filter(config_version=config_version)
    if info_version is not None:
        queryset = queryset.filter(info_version=info_version)
    versions = list(queryset)
    version = _select_current_version(versions)
    if version is None:
        raise CustomException(message=f"插件 {plugin.plugin_id} 没有可展示版本")
    return version


@KernelRPCRegistry.register(
    FUNC_COLLECT_PLUGIN_LIST,
    summary="Admin 查询采集插件列表",
    description="只读分页查询 CollectorPluginMeta，并默认补齐每个插件的最新版本摘要。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "search": "可选，匹配 plugin_id / 展示名",
        "plugin_id": "可选，插件 ID 包含匹配",
        "plugin_type": "可选，插件类型",
        "stage": "可选，版本阶段 release / debug / unregister",
        "bk_biz_id": "可选，业务 ID；0 表示全局插件",
        "label": "可选，二级标签包含匹配",
        "is_official": "可选，true / false",
        "is_internal": "可选，true / false",
        "has_collect_config": "可选，true / false",
        "is_support_remote": "可选，true / false",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "plugin_type": "Exporter", "page": 1, "page_size": 20},
)
def list_collect_plugins(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = _normalize_ordering(params.get("ordering"), PLUGIN_ORDERING_FIELDS, default="-update_time")

    queryset = filter_by_bk_tenant_id(CollectorPluginMeta.objects.all(), bk_tenant_id)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    plugin_type = _normalize_string(params.get("plugin_type"))
    if plugin_type:
        queryset = queryset.filter(plugin_type=plugin_type)
    plugin_id = _normalize_string(params.get("plugin_id"))
    if plugin_id:
        queryset = queryset.filter(plugin_id__icontains=plugin_id)
    label = _normalize_string(params.get("label"))
    if label:
        queryset = queryset.filter(label__icontains=label)
    is_internal = normalize_optional_bool(params.get("is_internal"), "is_internal")
    if is_internal is not None:
        queryset = queryset.filter(is_internal=is_internal)

    search = _normalize_string(params.get("search"))
    stage = _normalize_string(params.get("stage"))
    is_official = normalize_optional_bool(params.get("is_official"), "is_official")
    is_support_remote = normalize_optional_bool(params.get("is_support_remote"), "is_support_remote")
    needs_current_version_fields = bool(search or stage or is_official is not None or is_support_remote is not None)
    if needs_current_version_fields:
        queryset = _annotate_current_version_fields(queryset)
    if search:
        queryset = queryset.filter(Q(plugin_id__icontains=search) | Q(current_plugin_display_name__icontains=search))
    if stage:
        queryset = queryset.filter(current_stage=stage)
    if is_official is True:
        queryset = queryset.filter(plugin_id__startswith="bkplugin_", current_config_version__isnull=False)
    elif is_official is False:
        queryset = queryset.exclude(plugin_id__startswith="bkplugin_", current_config_version__isnull=False)
    if is_support_remote is True:
        queryset = queryset.filter(current_is_support_remote=True)
    elif is_support_remote is False:
        queryset = queryset.filter(Q(current_is_support_remote=False) | Q(current_config_version__isnull=True))

    has_collect_config = normalize_optional_bool(params.get("has_collect_config"), "has_collect_config")
    if has_collect_config is not None:
        queryset = _annotate_has_collect_config(queryset).filter(has_collect_config_flag=has_collect_config)

    total = queryset.count()
    type_count = {
        str(item["plugin_type"]): int(item["total"])
        for item in queryset.order_by().values("plugin_type").annotate(total=Count("id"))
    }

    offset = (page - 1) * page_size
    page_plugins = list(queryset.order_by(ordering, "plugin_id")[offset : offset + page_size])
    plugin_pairs = {_plugin_key(plugin) for plugin in page_plugins}
    versions_by_plugin = _load_versions_by_plugin_key(plugin_pairs)
    collect_config_counts = _collect_config_counts(plugin_pairs)
    release_counts = _release_version_counts(versions_by_plugin)

    page_items: list[dict[str, Any]] = []
    for plugin in page_plugins:
        key = _plugin_key(plugin)
        current_version = _select_current_version(versions_by_plugin.get(key, []))
        item = _serialize_plugin_summary(plugin, current_version, collect_config_counts.get(key, 0))
        item["release_version_count"] = release_counts.get(key, 0)
        page_items.append(item)

    return build_response(
        operation="collect_plugin.list",
        func_name=FUNC_COLLECT_PLUGIN_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": page_items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "type_count": dict(type_count),
        },
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_PLUGIN_DETAIL,
    summary="Admin 查询采集插件详情",
    description="只读查询单个采集插件基础信息、当前版本、历史版本和关联采集配置摘要。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "plugin_id": "必填，插件 ID",
        "config_version": "可选，指定 config_version",
        "info_version": "可选，指定 info_version",
    },
    example_params={"bk_tenant_id": "system", "plugin_id": "bkprocessbeat"},
)
def get_collect_plugin_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    plugin_id = _normalize_string(params.get("plugin_id"))
    if not plugin_id:
        raise CustomException(message="plugin_id 为必填项")
    plugin = _get_plugin(bk_tenant_id, plugin_id)
    current_version = _resolve_version(plugin, params)
    versions = list(
        PluginVersionHistory.objects.select_related("config", "info")
        .filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        .order_by("-config_version", "-info_version", "-id")
    )
    related_collect_configs = [
        _serialize_related_collect_config(config)
        for config in CollectConfigMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id).order_by("-id")[
            :100
        ]
    ]
    plugin_summary = _serialize_plugin_summary(plugin, current_version, len(related_collect_configs))
    plugin_summary["release_version_count"] = len(
        [version for version in versions if version.stage == PluginVersionHistory.Stage.RELEASE]
    )
    current_version_detail = _serialize_version_detail(current_version, plugin)

    return build_response(
        operation="collect_plugin.detail",
        func_name=FUNC_COLLECT_PLUGIN_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "plugin": plugin_summary,
            "current_version": current_version_detail,
            "versions": [_serialize_version_summary(version, plugin) for version in versions],
            "related_collect_configs": related_collect_configs,
            "warnings": [],
        },
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_PLUGIN_VERSION_LIST,
    summary="Admin 查询采集插件历史版本",
    description="只读分页查询单个插件的 PluginVersionHistory 历史版本。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "plugin_id": "必填，插件 ID",
        "stage": "可选，版本阶段",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "plugin_id": "node_exporter", "page": 1, "page_size": 20},
)
def list_collect_plugin_versions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    plugin_id = _normalize_string(params.get("plugin_id"))
    if not plugin_id:
        raise CustomException(message="plugin_id 为必填项")
    plugin = _get_plugin(bk_tenant_id, plugin_id)
    page, page_size = normalize_pagination(params)
    ordering = _normalize_ordering(params.get("ordering"), VERSION_ORDERING_FIELDS, default="-config_version")
    queryset = PluginVersionHistory.objects.select_related("config", "info").filter(
        bk_tenant_id=bk_tenant_id,
        plugin_id=plugin_id,
    )
    stage = _normalize_string(params.get("stage"))
    if stage:
        queryset = queryset.filter(stage=stage)
    versions = list(queryset.order_by(ordering, "-info_version", "-id"))
    page_versions, total = _paginate_items(
        [_serialize_version_summary(version, plugin) for version in versions],
        page=page,
        page_size=page_size,
    )
    return build_response(
        operation="collect_plugin.version_list",
        func_name=FUNC_COLLECT_PLUGIN_VERSION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": page_versions, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_COLLECT_PLUGIN_VERSION_DETAIL,
    summary="Admin 查询采集插件指定版本详情",
    description="只读查询单个插件指定或默认版本的参数、采集器和指标 JSON。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "plugin_id": "必填，插件 ID",
        "config_version": "必填，config_version",
        "info_version": "必填，info_version",
    },
    example_params={"bk_tenant_id": "system", "plugin_id": "node_exporter", "config_version": 1, "info_version": 1},
)
def get_collect_plugin_version_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    plugin_id = _normalize_string(params.get("plugin_id"))
    if not plugin_id:
        raise CustomException(message="plugin_id 为必填项")
    plugin = _get_plugin(bk_tenant_id, plugin_id)
    config_version = _normalize_int(params.get("config_version"), "config_version", required=True)
    info_version = _normalize_int(params.get("info_version"), "info_version", required=True)
    version = _resolve_version(plugin, {"config_version": config_version, "info_version": info_version})
    return build_response(
        operation="collect_plugin.version_detail",
        func_name=FUNC_COLLECT_PLUGIN_VERSION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"version": _serialize_version_detail(version, plugin)},
    )


def _serialize_related_collect_config(config: CollectConfigMeta) -> dict[str, Any]:
    return {
        "id": config.id,
        "bk_tenant_id": config.bk_tenant_id,
        "bk_biz_id": config.bk_biz_id,
        "name": config.name,
        "collect_type": config.collect_type,
        "plugin_id": config.plugin_id,
        "status": _safe_attr(config, "config_status"),
        "task_status": _safe_attr(config, "task_status"),
        "subscription_id": getattr(config.deployment_config, "subscription_id", None),
        "config_version": getattr(config.deployment_config.plugin_version, "config_version", None),
        "info_version": getattr(config.deployment_config.plugin_version, "info_version", None),
        "update_time": serialize_value(getattr(config, "update_time", None)),
    }


def _safe_attr(instance: Any, attr: str) -> Any:
    try:
        return getattr(instance, attr)
    except Exception:  # noqa: BLE001
        return None
