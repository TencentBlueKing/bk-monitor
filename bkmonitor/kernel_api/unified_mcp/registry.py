"""Deterministic catalog for the unified monitoring MCP facade.

The catalog is generated from the existing APIGW MCP OpenAPI YAML files.  Only
small, product-owned metadata (category, capability, permission and
prerequisites) is maintained here; request schemas and backend routes keep the
existing YAML files as their source of truth.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

CATEGORY_ACTIONS = {
    "metrics": "using_metrics_mcp",
    "log": "using_log_mcp",
    "alert": "using_alarm_mcp",
    "event": "using_log_mcp",
    "apm": "using_apm_mcp",
    "dashboard": "using_dashboard_mcp",
    "relation": "using_metrics_mcp",
}

SOURCE_FILES = {
    "metrics": "metrics_mcp.yaml",
    "log": "log_mcp.yaml",
    "alert": "alert_mcp.yaml",
    "event": "event_mcp.yaml",
    "apm": "apm_mcp.yaml",
    "dashboard": "dashboard_mcp.yaml",
    "relation": "relation_mcp.yaml",
}

# One permission catalog for standalone MCP routes, the facade, and introspection.
# Unlisted tools retain their existing MCP actions. Native mode is opt-in.
NATIVE_PERMISSIONS = {
    name: {
        "system_id": "bk_monitorv3",
        "action_id": "explore_metric_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    for name in ("list_time_series_groups", "list_time_series_metrics", "execute_range_query")
}
# SQL stays legacy until actual SQL source tables (not just table_id) are verified.
NATIVE_PERMISSIONS.update(
    {
        name: {
            "system_id": "bk_log_search",
            "action_id": "search_log_v2",
            "resource_type": "indices",
            "resource_arg": "index_set_id",
        }
        for name in (
            "get_index_set_fields",
            "search_logs",
            "search_index_set_context",
            "analyze_field",
            "search_log_clustering_pattern",
        )
    }
)
NATIVE_PERMISSIONS["list_index_sets"] = {
    "system_id": "bk_log_search",
    "action_id": "view_business_v2",
    "resource_type": "space",
    "resource_arg": "bk_biz_id",
}

# Alert-page queries use VIEW_EVENT; the current strategy configuration uses VIEW_RULE.
# target_arg is a business-bound lookup target, NOT a new IAM resource type.
for _name, _target_arg in {
    "list_alerts": "",
    "get_alert_top_n": "",
    "get_strategy_snapshot": "id",
    "get_strategy_detail": "id",
    "get_alert_info": "id",
    "get_alert_events": "alert_id",
    "get_alert_event_ts": "alert_id",
    "get_alert_event_tag_detail": "alert_id",
    "get_alert_k8s_target": "alert_id",
    "get_alert_host_target": "alert_id",
    "get_alert_traces": "alert_id",
    "get_alert_log_relations": "alert_id",
}.items():
    NATIVE_PERMISSIONS[_name] = {
        "system_id": "bk_monitorv3",
        "action_id": "view_rule_v2" if _name == "get_strategy_detail" else "view_event_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    if _target_arg:
        NATIVE_PERMISSIONS[_name].update(
            target_kind="strategy" if _name == "get_strategy_detail" else "alert",
            target_arg=_target_arg,
        )


def native_tool_names() -> tuple[str, ...]:
    names = getattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    if not isinstance(names, list | tuple) or any(not isinstance(name, str) for name in names):
        raise ImproperlyConfigured("MCP_NATIVE_PERMISSION_TOOLS must be a list of tool names")
    unknown = set(names) - NATIVE_PERMISSIONS.keys()
    if unknown:
        raise ImproperlyConfigured(f"Unsupported native MCP tools: {sorted(unknown)}")
    return tuple(sorted(set(names)))


EXCLUDED_OPERATION_IDS = {"create_dashboard", "update_dashboard"}
PUBLIC_TOOL_NAMES = {"apm_mcp_calculate_by_range": "calculate_by_range"}

CAPABILITIES = {
    # Metrics
    "list_time_series_groups": ("discovery",),
    "list_time_series_metrics": ("discovery",),
    "execute_range_query": ("query",),
    "execute_sql_query": ("query",),
    # Logs
    "list_index_sets": ("discovery",),
    "get_index_set_fields": ("discovery",),
    "search_logs": ("query",),
    "search_index_set_context": ("detail",),
    "list_log_scenes": ("discovery",),
    "list_scene_dimension_values": ("discovery",),
    "get_scene_log_fields": ("discovery",),
    "analyze_field": ("analysis",),
    "search_log_clustering_pattern": ("analysis",),
    # Alerts
    "list_alerts": ("query",),
    "get_alert_top_n": ("analysis",),
    "get_strategy_snapshot": ("detail",),
    "get_strategy_detail": ("detail",),
    "get_alert_info": ("detail",),
    "get_alert_events": ("detail",),
    "get_alert_event_ts": ("detail", "analysis"),
    "get_alert_event_tag_detail": ("detail",),
    "get_alert_k8s_target": ("relation",),
    "get_alert_host_target": ("relation",),
    "get_alert_traces": ("relation",),
    "get_alert_log_relations": ("relation",),
    # Events
    "list_events": ("discovery",),
    "get_event_view_config": ("discovery",),
    "search_event_log": ("query",),
    # APM tracing and profiling
    "list_apm_applications": ("discovery",),
    "get_apm_filter_fields": ("discovery",),
    "search_spans": ("query",),
    "get_trace_detail": ("detail",),
    "get_span_detail": ("detail",),
    "get_profile_application_service": ("discovery",),
    "get_profile_type": ("discovery",),
    "get_profile_label": ("discovery",),
    "query_graph_profile": ("query", "analysis"),
    "calculate_by_range": ("analysis",),
    "list_apm_services": ("discovery",),
    # Dashboards
    "get_dashboard_tree_list": ("discovery",),
    "get_dashboard_detail_by_uid": ("detail",),
    # Resource relations
    "find_relations": ("relation",),
    "find_relations_range": ("relation",),
}

TITLES = {
    "list_time_series_groups": "列出时序分组",
    "list_time_series_metrics": "列出时序指标",
    "execute_range_query": "执行 PromQL 范围查询",
    "execute_sql_query": "执行 SQL 原始数据查询",
    "list_index_sets": "列出日志索引集",
    "get_index_set_fields": "获取索引集字段",
    "search_logs": "查询日志",
    "search_index_set_context": "查询日志上下文",
    "list_log_scenes": "列出日志场景",
    "list_scene_dimension_values": "查询场景维度值",
    "get_scene_log_fields": "获取场景日志字段",
    "analyze_field": "分析日志字段",
    "search_log_clustering_pattern": "查询日志聚类模式",
    "list_alerts": "查询告警列表",
    "get_alert_top_n": "分析告警 Top N",
    "get_strategy_snapshot": "获取策略快照",
    "get_strategy_detail": "获取策略详情",
    "get_alert_info": "获取告警详情",
    "get_alert_events": "获取告警关联事件",
    "get_alert_event_ts": "获取告警事件时序",
    "get_alert_event_tag_detail": "获取告警事件标签详情",
    "get_alert_k8s_target": "获取告警 K8s 目标",
    "get_alert_host_target": "获取告警主机目标",
    "get_alert_traces": "获取告警关联 Trace",
    "get_alert_log_relations": "获取告警关联日志",
    "list_events": "列出事件源",
    "get_event_view_config": "获取事件视图配置",
    "search_event_log": "查询事件",
    "list_apm_applications": "列出 APM 应用",
    "get_apm_filter_fields": "获取 APM 过滤字段",
    "search_spans": "查询 Span",
    "get_trace_detail": "获取 Trace 详情",
    "get_span_detail": "获取 Span 详情",
    "get_profile_application_service": "列出 Profile 应用与服务",
    "get_profile_type": "获取 Profile 数据类型",
    "get_profile_label": "获取 Profile 标签",
    "query_graph_profile": "查询 Profile 火焰图",
    "calculate_by_range": "分析 APM 指标",
    "list_apm_services": "列出 APM 服务",
    "get_dashboard_tree_list": "获取仪表盘目录树",
    "get_dashboard_detail_by_uid": "获取仪表盘详情",
    "find_relations": "查询资源关联",
    "find_relations_range": "查询资源关联变化",
}

PREREQUISITES: dict[str, tuple[str, ...]] = {
    "list_time_series_metrics": ("list_time_series_groups",),
    "execute_range_query": ("list_time_series_groups", "list_time_series_metrics"),
    "execute_sql_query": ("list_time_series_groups",),
    "get_index_set_fields": ("list_index_sets",),
    "search_logs": ("list_index_sets", "get_index_set_fields"),
    "search_index_set_context": ("search_logs",),
    "list_scene_dimension_values": ("list_log_scenes",),
    "get_scene_log_fields": ("list_log_scenes", "list_scene_dimension_values"),
    "analyze_field": ("list_index_sets", "get_index_set_fields"),
    "search_log_clustering_pattern": ("list_index_sets",),
    "get_alert_top_n": ("list_alerts",),
    "get_strategy_snapshot": ("list_alerts",),
    "get_strategy_detail": ("list_alerts",),
    "get_alert_info": ("list_alerts",),
    "get_alert_events": ("list_alerts", "get_alert_info"),
    "get_alert_event_ts": ("list_alerts", "get_alert_info"),
    "get_alert_event_tag_detail": ("get_alert_event_ts",),
    "get_alert_k8s_target": ("list_alerts", "get_alert_info"),
    "get_alert_host_target": ("list_alerts", "get_alert_info"),
    "get_alert_traces": ("list_alerts", "get_alert_info"),
    "get_alert_log_relations": ("list_alerts", "get_alert_info"),
    "get_event_view_config": ("list_events",),
    "search_event_log": ("list_events", "get_event_view_config"),
    "get_apm_filter_fields": ("list_apm_applications",),
    "search_spans": ("list_apm_applications", "get_apm_filter_fields"),
    "get_trace_detail": ("search_spans",),
    "get_span_detail": ("search_spans",),
    "get_profile_type": ("get_profile_application_service",),
    "get_profile_label": ("get_profile_application_service",),
    "query_graph_profile": ("get_profile_application_service", "get_profile_type"),
    "calculate_by_range": ("list_apm_applications",),
    "list_apm_services": ("list_apm_applications",),
    "get_dashboard_detail_by_uid": ("get_dashboard_tree_list",),
}

BACKEND_DERIVED_FIELDS = {
    "list_alerts": ("bk_biz_ids",),
    "get_alert_top_n": ("bk_biz_ids",),
}

UNIFIED_HIDDEN_FIELDS = {
    # ponytail: Global labels lack profile_id scoping; remove this override after APM Web owns that validation.
    "get_profile_label": ("global_query",),
}


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    category: str
    capabilities: tuple[str, ...]
    description: str
    input_schema: dict[str, Any]
    backend_method: str
    backend_path: str
    iam_action: str
    prerequisites: tuple[str, ...] = ()
    risk: str = "query"
    resource_arg: str = "bk_biz_id"
    backend_derived_fields: tuple[str, ...] = ()
    native_permission: dict[str, str] | None = None

    def permission_payload(self) -> dict[str, str]:
        if self.native_permission:
            payload = {
                **self.native_permission,
                "mode": "native_then_legacy",
                "fallback_system_id": settings.BK_IAM_SYSTEM_ID,
                "fallback_action_id": self.iam_action,
                "fallback_on": "explicit_denial_only",
            }
            if payload["system_id"] == "bk_monitorv3":
                payload["system_id"] = settings.BK_IAM_SYSTEM_ID
            elif payload["system_id"] == "bk_log_search":
                payload["iam_model"] = "v3-current"
                if payload["resource_type"] == "indices":
                    payload["resource_scope"] = "ordinary_same_space"
            return payload
        return {"action_id": self.iam_action, "resource_type": "space", "resource_arg": self.resource_arg}

    def summary(self, permission_state: str = "unknown") -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "capabilities": list(self.capabilities),
            "description": self.description,
            "risk": self.risk,
            "required_context": list(dict.fromkeys([self.resource_arg, self.native_permission["resource_arg"]]))
            if self.native_permission
            else [self.resource_arg],
            "prerequisites": list(self.prerequisites),
            "permission_state": permission_state,
        }

    def schema_payload(self, catalog_version: str) -> dict[str, Any]:
        return {
            "catalog_version": catalog_version,
            "tool_name": self.name,
            "description": self.description,
            "input_schema": deepcopy(self.input_schema),
            "guidelines": _build_guidelines(self),
            "prerequisites": [
                {
                    "tool": tool_name,
                    "kind": "conditional",
                    "condition": f"缺少 {tool_name} 提供的参数时",
                }
                for tool_name in self.prerequisites
            ],
            "permission": self.permission_payload(),
            "limits": _extract_limits(self.input_schema),
            "returns": "返回结构沿用现有业务 API。",
            "backend_derived_fields": list(self.backend_derived_fields),
        }


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolDefinition], catalog_version: str):
        self._tools = tools
        self.catalog_version = catalog_version
        self._backend_tools = {}
        for tool in tools.values():
            key = (tool.backend_method, tool.backend_path.rstrip("/"))
            if key in self._backend_tools:
                raise RuntimeError(f"duplicate MCP backend route: {key}")
            self._backend_tools[key] = tool

    def get_by_backend(self, method: str, path: str) -> ToolDefinition | None:
        # DRF JSON suffixes and implicit HEAD must not become legacy-permission aliases.
        method = "GET" if method.upper() == "HEAD" else method.upper()
        return self._backend_tools.get((method, path.rstrip("/").removesuffix(".json")))

    def __len__(self) -> int:
        return len(self._tools)

    def get(self, tool_name: str) -> ToolDefinition:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(f"unknown unified MCP tool: {tool_name}") from exc

    def list(
        self,
        *,
        tool_name: str | None = None,
        category: str | None = None,
        capability: str | None = None,
    ) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if tool_name:
            tools = [tool for tool in tools if tool.name == tool_name]
        if category:
            tools = [tool for tool in tools if tool.category == category]
        if capability:
            tools = [tool for tool in tools if capability in tool.capabilities]
        return sorted(tools, key=lambda tool: (tool.category, tool.name))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


def _extract_input_schema(operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    body_schema = (content.get("application/json") or {}).get("schema")
    if body_schema:
        return deepcopy(body_schema)

    properties: dict[str, Any] = {}
    required: list[str] = []
    for parameter in operation.get("parameters") or []:
        name = parameter["name"]
        schema = deepcopy(parameter.get("schema") or {"type": "string"})
        if parameter.get("description"):
            schema["description"] = parameter["description"]
        properties[name] = schema
        if parameter.get("required"):
            required.append(name)
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _normalize_public_schema(tool_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)
    result.setdefault("type", "object")
    properties = result.setdefault("properties", {})
    required = list(result.get("required") or [])

    # All unified data tools are space-scoped even when a legacy OpenAPI file
    # forgot to mark bk_biz_id as required.
    if "bk_biz_id" in properties and "bk_biz_id" not in required:
        required.append("bk_biz_id")
    if "bk_biz_id" in properties:
        properties["bk_biz_id"]["type"] = "string"

    # These are backend serializer compatibility fields.  The facade derives
    # them from bk_biz_id so the Agent only supplies one business identifier.
    for field_name in BACKEND_DERIVED_FIELDS.get(tool_name, ()):
        properties.pop(field_name, None)
        required = [name for name in required if name != field_name]
    for field_name in UNIFIED_HIDDEN_FIELDS.get(tool_name, ()):
        properties.pop(field_name, None)
        required = [name for name in required if name != field_name]

    if required:
        result["required"] = required
    else:
        result.pop("required", None)
    _close_object_schemas(result)
    return result


def _close_object_schemas(schema: dict[str, Any]) -> None:
    if schema.get("type") == "object" and "properties" in schema:
        schema.setdefault("additionalProperties", False)
    for child in (schema.get("properties") or {}).values():
        if isinstance(child, dict):
            _close_object_schemas(child)
    if isinstance(schema.get("items"), dict):
        _close_object_schemas(schema["items"])
    for keyword in ("allOf", "anyOf", "oneOf"):
        for child in schema.get(keyword) or []:
            if isinstance(child, dict):
                _close_object_schemas(child)


def _extract_limits(schema: dict[str, Any]) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    properties = schema.get("properties") or {}
    if "limit" in properties and properties["limit"].get("maximum") is not None:
        limits["max_results"] = properties["limit"]["maximum"]
    description = " ".join(
        str(value.get("description", "")) for value in properties.values() if isinstance(value, dict)
    )
    if "86400" in description:
        limits["max_time_span_seconds"] = 86400
    if "1800" in description:
        limits["max_time_span_seconds"] = 1800
    return limits


def _build_guidelines(tool: ToolDefinition) -> list[str]:
    guidelines: list[str] = []
    if tool.native_permission and tool.native_permission["resource_type"] == "indices":
        guidelines.append("原生权限首版仅支持普通、非分组、同空间索引集；不支持场景或平台级跨空间检索。")
    properties = tool.input_schema.get("properties") or {}
    if "start_time" in properties or "end_time" in properties:
        guidelines.append("start_time 和 end_time 必须按当前时间动态计算，不能使用固定历史时间戳。")
    if tool.prerequisites:
        guidelines.append("标识和字段必须来自前置工具返回，不能自行猜测。")
    if tool.backend_derived_fields:
        guidelines.append("后台兼容字段由统一 MCP Server 派生，Agent 不需要填写。")
    return guidelines


def _catalog_root() -> Path:
    return Path(settings.BASE_DIR) / "support-files" / "apigw" / "resources" / "internal" / "user"


def load_tool_registry(root: Path | None = None) -> ToolRegistry:
    root = root or _catalog_root()
    enabled = native_tool_names()
    tools: dict[str, ToolDefinition] = {}
    discovered_operation_ids: set[str] = set()
    digest = hashlib.sha256()

    for category, filename in SOURCE_FILES.items():
        path = root / filename
        raw = path.read_bytes()
        digest.update(raw)
        document = yaml.safe_load(raw) or {}
        for api_path, path_item in (document.get("paths") or {}).items():
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                operation_id = operation.get("operationId")
                if not operation_id:
                    continue
                tool_name = PUBLIC_TOOL_NAMES.get(operation_id, operation_id)
                if tool_name in discovered_operation_ids:
                    raise RuntimeError(f"duplicate unified MCP tool name: {tool_name}")
                discovered_operation_ids.add(tool_name)
                if operation_id in EXCLUDED_OPERATION_IDS:
                    continue
                if tool_name not in CAPABILITIES:
                    continue
                backend = (operation.get("x-bk-apigateway-resource") or {}).get("backend") or {}
                schema = _normalize_public_schema(tool_name, _extract_input_schema(operation))
                description = operation.get("description", "")
                if tool_name in enabled:
                    description += (
                        " Native permissions are checked first; explicit denial falls back to the original MCP action. "
                        "Errors and invalid resource scopes never trigger fallback. 原生权限优先，明确无权时检查原 MCP 权限；"
                        "异常或资源校验失败不回退。"
                    )
                    if NATIVE_PERMISSIONS[tool_name]["resource_type"] == "indices":
                        description = (
                            "Native mode only supports ordinary, non-grouped index sets in the requested space. "
                            "Scene/platform modes are unavailable. 原生模式仅支持普通、非分组、同空间索引集；"
                            "不支持场景或平台级检索。以下为底层通用接口说明： " + description
                        )
                    if tool_name == "search_logs":
                        schema["properties"]["target_type"]["enum"] = ["index_set"]
                        schema["properties"].pop("table_id_conditions", None)
                        schema["required"] = list(dict.fromkeys([*schema.get("required", []), "index_set_id"]))
                    if tool_name == "list_time_series_groups":
                        schema["properties"]["is_platform"]["enum"] = [False]
                tools[tool_name] = ToolDefinition(
                    name=tool_name,
                    title=TITLES[tool_name],
                    category=category,
                    capabilities=CAPABILITIES[tool_name],
                    description=description,
                    input_schema=schema,
                    backend_method=str(backend.get("method") or method).upper(),
                    backend_path=str(backend.get("path") or api_path),
                    iam_action=CATEGORY_ACTIONS[category],
                    prerequisites=PREREQUISITES.get(tool_name, ()),
                    backend_derived_fields=BACKEND_DERIVED_FIELDS.get(tool_name, ()),
                    native_permission=deepcopy(NATIVE_PERMISSIONS[tool_name]) if tool_name in enabled else None,
                )

    expected = set(CAPABILITIES)
    actual = set(tools)
    expected_source = expected | EXCLUDED_OPERATION_IDS
    if actual != expected or discovered_operation_ids != expected_source:
        raise RuntimeError(
            "unified MCP registry drift: "
            f"missing_metadata={sorted(discovered_operation_ids - expected_source)}, "
            f"missing_source={sorted(expected - discovered_operation_ids)}, "
            f"missing_tools={sorted(expected - actual)}, extra_tools={sorted(actual - expected)}"
        )
    digest.update(
        yaml.safe_dump(
            {
                "category_actions": CATEGORY_ACTIONS,
                "native_permissions": NATIVE_PERMISSIONS,
                "native_tools": enabled,
                "monitor_system_id": settings.BK_IAM_SYSTEM_ID,
                "source_files": SOURCE_FILES,
                "excluded_operation_ids": sorted(EXCLUDED_OPERATION_IDS),
                "public_tool_names": PUBLIC_TOOL_NAMES,
                "capabilities": CAPABILITIES,
                "titles": TITLES,
                "prerequisites": PREREQUISITES,
                "backend_derived_fields": BACKEND_DERIVED_FIELDS,
                "unified_hidden_fields": UNIFIED_HIDDEN_FIELDS,
            },
            allow_unicode=True,
            sort_keys=True,
        ).encode()
    )
    return ToolRegistry(tools, digest.hexdigest()[:12])


@lru_cache(maxsize=1)
def _cached_tool_registry(enabled: tuple[str, ...], monitor_system_id: str) -> ToolRegistry:
    return load_tool_registry()


def get_tool_registry() -> ToolRegistry:
    return _cached_tool_registry(native_tool_names(), settings.BK_IAM_SYSTEM_ID)
