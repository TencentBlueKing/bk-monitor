"""Unified MCP 的确定性工具目录。

工具名、请求 Schema 和后端路由以现有 APIGW MCP OpenAPI YAML 为真相源；本模块只补充
分类、能力、权限、风险和前置关系等产品元信息，并将两部分合成为 ToolDefinition。
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

CATEGORY_ACTIONS = {
    "metrics": "using_metrics_mcp",
    "log": "using_log_mcp",
    "alert": "using_alarm_mcp",
    "event": "using_log_mcp",
    "apm": "using_apm_mcp",
    "dashboard": "using_dashboard_mcp",
    "relation": "using_metrics_mcp",
    "alert_handling": "using_alarm_handling_mcp",
    "log_collection": "using_log_collection_mcp",
    "log_extract": "using_log_extract_mcp",
    "metadata": "using_metadata_mcp",
    "operation": "using_operation_mcp",
}

# ops 没有登记 MCP Server 后缀权限；OpenClaw 自愈使用专用的用户身份隔离，
# 两者都不能套普通业务级 IAM Action。

# 显式维护公开 Source：新增 APIGW MCP YAML 必须经过评审，不能因文件名匹配就自动进入目录。
SOURCE_FILES = {
    "metrics": ("metrics_mcp.yaml",),
    "log": ("log_mcp.yaml",),
    "alert": ("alert_mcp.yaml",),
    "event": ("event_mcp.yaml",),
    "apm": ("apm_mcp.yaml",),
    "dashboard": ("dashboard_mcp.yaml",),
    "relation": ("relation_mcp.yaml",),
    "alert_handling": ("alert_handling_mcp.yaml",),
    "log_collection": (
        "log_collection_mcp.yaml",
        "log_collection_clean_config_mcp.yaml",
        "log_collection_create_mcp.yaml",
        "log_collection_discovery_mcp.yaml",
        "log_collection_etl_preview_mcp.yaml",
        "log_collection_index_set_mcp.yaml",
        "log_collection_special_create_mcp.yaml",
        "log_collection_special_update_mcp.yaml",
        "log_collection_status_mcp.yaml",
        "log_collection_update_mcp.yaml",
    ),
    "log_extract": ("log_extract_mcp.yaml",),
    "metadata": ("metadata_mcp.yaml",),
    "operation": ("operation_mcp.yaml",),
}
# 私有／专用 MCP 保留原入口，不进入 Tool Search 和 Unified 执行。
IGNORED_SOURCE_FILES = frozenset({"openclaw_recovering_mcp.yaml", "ops_mcp.yaml"})
CATEGORIES = tuple(SOURCE_FILES)

# standalone、Unified 门面和权限探测共用同一份权限目录。
# 未声明原生映射的工具继续使用原 MCP Action；原生模式必须显式启用。
NATIVE_PERMISSIONS = {
    name: {
        "system_id": "bk_monitorv3",
        "action_id": "explore_metric_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    for name in ("list_time_series_groups", "list_time_series_metrics", "execute_range_query")
}
# SQL 在真实访问表范围完成验证前保持旧权限，不能只凭 table_id 推断授权资源。
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

# 告警查询复用事件查看权限，当前策略配置使用策略查看权限。
# target_arg 只用于校验目标归属业务，不代表新增了告警／策略实例级 IAM 资源。
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
    """读取并校验动态启用的原生权限工具白名单。"""
    names = getattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    if not isinstance(names, list | tuple) or any(not isinstance(name, str) for name in names):
        raise ImproperlyConfigured("MCP_NATIVE_PERMISSION_TOOLS must be a list of tool names")
    unknown = set(names) - NATIVE_PERMISSIONS.keys()
    if unknown:
        raise ImproperlyConfigured(f"Unsupported native MCP tools: {sorted(unknown)}")
    return tuple(sorted(set(names)))


# 对外工具名与历史 operationId 不一致时，在这里做唯一别名归一。
PUBLIC_TOOL_NAMES = {"apm_mcp_calculate_by_range": "calculate_by_range"}

# 能力标签是人工评审的产品语义，不能根据 GET／POST 或函数名前缀猜测。
CAPABILITIES = {
    # 指标查询
    "list_time_series_groups": ("discovery",),
    "list_time_series_metrics": ("discovery",),
    "execute_range_query": ("query",),
    "execute_sql_query": ("query",),
    # 日志查询
    "list_index_sets": ("discovery",),
    "get_index_set_fields": ("discovery",),
    "search_logs": ("query",),
    "search_index_set_context": ("detail",),
    "list_log_scenes": ("discovery",),
    "list_scene_dimension_values": ("discovery",),
    "get_scene_log_fields": ("discovery",),
    "analyze_field": ("analysis",),
    "search_log_clustering_pattern": ("analysis",),
    # 告警查询
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
    # 事件查询
    "list_events": ("discovery",),
    "get_event_view_config": ("discovery",),
    "search_event_log": ("query",),
    # APM 链路与性能分析
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
    # 仪表盘
    "get_dashboard_tree_list": ("discovery",),
    "get_dashboard_detail_by_uid": ("detail",),
    # 资源关联
    "find_relations": ("relation",),
    "find_relations_range": ("relation",),
}

CAPABILITIES.update(
    {
        # 仪表盘写入
        "create_dashboard": ("mutation",),
        "update_dashboard": ("mutation",),
        # 告警处理
        "search_alarm_strategies": ("discovery",),
        "get_alarm_strategy": ("detail",),
        "create_alarm_strategy": ("mutation",),
        "update_alarm_strategy": ("mutation",),
        "search_alarm_shields": ("discovery",),
        "get_alarm_shield": ("detail",),
        "create_alarm_shield": ("mutation",),
        "update_alarm_shield": ("mutation",),
        "disable_alarm_shield": ("mutation",),
        "search_alarm_notice_groups": ("discovery",),
        "create_alarm_notice_group": ("mutation",),
        "update_alarm_notice_group": ("mutation",),
        "search_alarm_action_configs": ("discovery",),
        "get_alarm_action_config": ("detail",),
        "update_alarm_action_config": ("mutation",),
        "search_alarm_assign_groups": ("discovery",),
        "save_alarm_assign_group": ("mutation",),
        "delete_alarm_assign_group": ("mutation",),
        # 日志采集
        "list_log_collectors": ("discovery",),
        "get_log_collector": ("detail",),
        "get_log_index_set": ("detail",),
        "update_log_collector_clean_config": ("mutation",),
        "fast_create_log_collector": ("mutation",),
        "list_third_party_es_clusters": ("discovery",),
        "list_result_tables": ("discovery",),
        "preview_log_etl": ("analysis",),
        "list_log_index_set_groups": ("discovery",),
        "create_custom_report": ("mutation",),
        "create_bkdata_index_set": ("mutation",),
        "create_third_party_es": ("mutation",),
        "update_custom_report": ("mutation",),
        "update_third_party_es": ("mutation",),
        "update_bkdata_index_set": ("mutation",),
        "get_log_collector_status": ("detail",),
        "fast_update_log_collector": ("mutation",),
        # 日志提取
        "list_log_extract_topology": ("discovery",),
        "search_log_extract_hosts": ("discovery",),
        "list_log_extract_allowed_paths": ("discovery",),
        "search_log_extract_files": ("discovery", "mutation"),
        "create_log_extract_task": ("mutation", "export"),
        "get_log_extract_task": ("detail",),
        "get_log_extract_download_url": ("export",),
        # 元数据
        "list_bcs_clusters": ("discovery",),
        "search_spaces": ("discovery",),
        # 平台运营数据
        "list_operation_metrics": ("discovery",),
        "get_operation_metric": ("query",),
        "get_operation_overview": ("analysis",),
    }
)

# 只有补齐能力 Metadata 的工具才允许进入 dispatcher。
EXECUTABLE_TOOL_NAMES = frozenset(CAPABILITIES)
# 空间目录沿用平台可见语义；这里只豁免发现，不授权后续业务数据访问。
PERMISSION_EXEMPT_TOOL_NAMES = frozenset({"search_spaces"})

# Unified 直调 Resource 时，显式补回原 ViewSet 上的附加 IAM Action。
ADDITIONAL_IAM_ACTIONS = {
    **{
        name: ("view_business_v2",)
        for name in (
            "list_log_collectors",
            "get_log_collector",
            "get_log_index_set",
            "list_log_index_set_groups",
            "list_third_party_es_clusters",
            "list_result_tables",
        )
    },
    **{
        name: ("view_collection_v2",)
        for name in (
            "preview_log_etl",
            "get_log_collector_status",
        )
    },
    **{
        name: ("manage_collection_v2",)
        for name in (
            "update_log_collector_clean_config",
            "fast_create_log_collector",
            "create_custom_report",
            "create_bkdata_index_set",
            "create_third_party_es",
            "update_custom_report",
            "update_third_party_es",
            "update_bkdata_index_set",
            "fast_update_log_collector",
        )
    },
}

# Tool Search 展示标题；工具描述本身仍来自 Source OpenAPI。
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
TITLES.update(
    {
        "create_dashboard": "创建仪表盘",
        "update_dashboard": "更新仪表盘",
        "search_alarm_strategies": "查询告警策略",
        "get_alarm_strategy": "获取告警策略",
        "create_alarm_strategy": "创建告警策略",
        "update_alarm_strategy": "更新告警策略",
        "search_alarm_shields": "查询告警屏蔽",
        "get_alarm_shield": "获取告警屏蔽",
        "create_alarm_shield": "创建告警屏蔽",
        "update_alarm_shield": "更新告警屏蔽",
        "disable_alarm_shield": "解除告警屏蔽",
        "search_alarm_notice_groups": "查询告警组",
        "create_alarm_notice_group": "创建告警组",
        "update_alarm_notice_group": "更新告警组",
        "search_alarm_action_configs": "查询处理套餐",
        "get_alarm_action_config": "获取处理套餐",
        "update_alarm_action_config": "更新处理套餐",
        "search_alarm_assign_groups": "查询告警分派组",
        "save_alarm_assign_group": "保存告警分派组",
        "delete_alarm_assign_group": "删除告警分派组",
        "list_log_collectors": "列出日志采集项",
        "get_log_collector": "获取日志采集项",
        "get_log_index_set": "获取日志索引集",
        "update_log_collector_clean_config": "更新日志清洗配置",
        "fast_create_log_collector": "快速创建日志采集项",
        "list_third_party_es_clusters": "列出第三方 ES 集群",
        "list_result_tables": "列出结果表",
        "preview_log_etl": "预览日志清洗",
        "list_log_index_set_groups": "列出日志索引集分组",
        "create_custom_report": "创建自定义上报",
        "create_bkdata_index_set": "创建计算平台索引集",
        "create_third_party_es": "创建第三方 ES 索引集",
        "update_custom_report": "更新自定义上报",
        "update_third_party_es": "更新第三方 ES 索引集",
        "update_bkdata_index_set": "更新计算平台索引集",
        "get_log_collector_status": "获取日志采集状态",
        "fast_update_log_collector": "快速更新日志采集项",
        "list_log_extract_topology": "列出日志提取拓扑",
        "search_log_extract_hosts": "查询日志提取主机",
        "list_log_extract_allowed_paths": "列出日志提取允许路径",
        "search_log_extract_files": "查询可提取日志文件",
        "create_log_extract_task": "创建日志提取任务",
        "get_log_extract_task": "获取日志提取任务",
        "get_log_extract_download_url": "获取日志提取下载地址",
        "list_bcs_clusters": "列出 BCS 集群",
        "search_spaces": "查询业务空间",
        "list_operation_metrics": "列出运营指标",
        "get_operation_metric": "查询运营指标",
        "get_operation_overview": "获取运营概览",
    }
)

# 参数应从哪些前置工具取得；这是调用建议，不是绕过最终校验的凭据。
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
PREREQUISITES.update(
    {
        "update_dashboard": ("get_dashboard_detail_by_uid",),
        "get_alarm_strategy": ("search_alarm_strategies",),
        "create_alarm_strategy": (
            "search_alarm_strategies",
            "search_alarm_notice_groups",
            "search_alarm_action_configs",
        ),
        "update_alarm_strategy": ("get_alarm_strategy",),
        "get_alarm_shield": ("search_alarm_shields",),
        "create_alarm_shield": ("search_alarm_shields",),
        "update_alarm_shield": ("get_alarm_shield",),
        "disable_alarm_shield": ("get_alarm_shield",),
        "create_alarm_notice_group": ("search_alarm_notice_groups",),
        "update_alarm_notice_group": ("search_alarm_notice_groups",),
        "get_alarm_action_config": ("search_alarm_action_configs",),
        "update_alarm_action_config": ("get_alarm_action_config",),
        "save_alarm_assign_group": ("search_alarm_assign_groups",),
        "delete_alarm_assign_group": ("search_alarm_assign_groups",),
        "get_log_collector": ("list_log_collectors",),
        "get_log_index_set": ("list_log_collectors",),
        "update_log_collector_clean_config": ("get_log_collector",),
        "create_bkdata_index_set": ("list_result_tables",),
        "create_third_party_es": ("list_third_party_es_clusters", "list_result_tables"),
        "update_custom_report": ("get_log_collector",),
        "update_third_party_es": ("get_log_index_set",),
        "update_bkdata_index_set": ("get_log_index_set",),
        "fast_update_log_collector": ("get_log_collector",),
        "search_log_extract_hosts": ("list_log_extract_topology",),
        "list_log_extract_allowed_paths": ("search_log_extract_hosts",),
        "search_log_extract_files": ("list_log_extract_allowed_paths",),
        "create_log_extract_task": ("search_log_extract_files",),
        "get_log_extract_task": ("create_log_extract_task",),
        "get_log_extract_download_url": ("get_log_extract_task",),
        "list_bcs_clusters": ("search_spaces",),
        "get_operation_metric": ("list_operation_metrics",),
        "get_operation_overview": ("list_operation_metrics",),
    }
)

BACKEND_DERIVED_FIELDS = {
    "list_alerts": ("bk_biz_ids",),
    "get_alert_top_n": ("bk_biz_ids",),
}

UNIFIED_HIDDEN_FIELDS = {
    # ponytail: 全局标签缺少 profile_id 范围；APM Web 接管该校验后移除此覆盖。
    "get_profile_label": ("global_query",),
}


@dataclass(frozen=True)
class ToolDefinition:
    """模型可见工具的完整元信息和执行契约。"""

    name: str  # 对外工具名，默认取 OpenAPI operationId。
    title: str  # 便于模型和人工阅读的中文标题。
    category: str  # 工具所属 MCP Server／领域，用于检索和旧权限路由。
    capabilities: tuple[str, ...]  # discovery/query/mutation/export 等能力标签。
    description: str  # 来源 OpenAPI 的工具说明，原生模式可追加边界提示。
    input_schema: dict[str, Any]  # 提供给模型的归一化 JSON Schema。
    backend_method: str  # 原 APIGW 后端 HTTP 方法，仅用于路由和审计。
    backend_path: str  # 原 APIGW 后端路径，用于匹配 standalone 请求。
    iam_action: str  # 工具所属 Server 的原 using_xxx_mcp 权限点。
    prerequisites: tuple[str, ...] = ()  # 参数应从哪些前置工具取得。
    risk: str = "query"  # query、mutation 或 data_export。
    permission_exempt: bool = False  # 是否沿用平台可见目录等免业务权限语义。
    additional_iam_actions: tuple[str, ...] = ()  # Unified 直调时仍须保留的原路由权限。
    requires_confirmation: bool = False  # 是否必须先取得用户确认并传 confirm=true。
    forwards_confirmation: bool = False  # 原 Resource 是否原生接收 confirm 字段。
    resource_arg: str = "bk_biz_id"  # 默认从哪个参数取得业务／资源上下文。
    backend_derived_fields: tuple[str, ...] = ()  # 由服务端派生、模型无需传入的字段。
    native_permission: dict[str, str] | None = None  # 可选的原生权限及资源映射。

    def normalize_standalone_args(self, tool_args):
        """适配 standalone 历史标量字符串，Schema 和资源校验仍由执行器负责。

        不解析 JSON 容器、不丢弃未知字段，只转换整数文本和 true/false 文本，
        避免把 DRF 更宽松的隐式类型转换暴露成新的接口契约。
        """
        if not isinstance(tool_args, dict):
            return tool_args
        args = dict(tool_args)
        for name, schema in self.input_schema.get("properties", {}).items():
            value = args.get(name)
            if not isinstance(value, str):
                continue
            if schema.get("type") == "integer" and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
                args[name] = serializers.IntegerField().run_validation(value)
            elif schema.get("type") == "boolean" and value.lower() in {"true", "false"}:
                args[name] = value.lower() == "true"
        return args

    @property
    def legacy_action_ids(self) -> tuple[str, ...]:
        """返回执行时必须同时满足的旧 MCP 与原路由附加权限。"""
        if self.permission_exempt or not self.iam_action:
            return ()
        return (self.iam_action, *self.additional_iam_actions)

    def permission_payload(self) -> dict[str, Any]:
        """生成模型可读的权限契约，不执行真实权限查询。"""
        if self.permission_exempt:
            return {"mode": "exempt", "reason": "platform-visible metadata discovery"}
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
        payload = {"action_id": self.iam_action, "resource_type": "space", "resource_arg": self.resource_arg}
        if self.additional_iam_actions:
            payload["additional_action_ids"] = list(self.additional_iam_actions)
        return payload

    def summary(self, permission_state: str = "unknown") -> dict[str, Any]:
        """生成 lookup_tool 使用的轻量工具卡片。"""
        properties = self.input_schema.get("properties", {})
        required_context = (
            list(dict.fromkeys([self.resource_arg, self.native_permission["resource_arg"]]))
            if self.native_permission
            else [self.resource_arg]
            if self.resource_arg in properties
            else []
        )
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "capabilities": list(self.capabilities),
            "description": self.description,
            "risk": self.risk,
            "execution_status": "executable",
            "requires_confirmation": self.requires_confirmation,
            "required_context": required_context,
            "prerequisites": list(self.prerequisites),
            "permission_state": permission_state,
        }

    def schema_payload(self, catalog_version: str) -> dict[str, Any]:
        """生成 lookup_tool_schema 返回的完整调用契约。"""
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
            "execution": {
                "status": "executable",
                "requires_confirmation": self.requires_confirmation,
                "reason": "",
            },
            "limits": _extract_limits(self.input_schema),
            "returns": "返回结构沿用现有业务 API。",
            "backend_derived_fields": list(self.backend_derived_fields),
        }


class ToolRegistry:
    """按工具名或后端路由提供确定性查询的只读目录。"""

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
        """供 standalone 请求按后端 method/path 找到同一个 ToolDefinition。"""
        # `.json` 后缀和隐式 HEAD 只做协议兼容，不能成为旧权限旁路。
        method = "GET" if method.upper() == "HEAD" else method.upper()
        return self._backend_tools.get((method, path.rstrip("/").removesuffix(".json")))

    def __len__(self) -> int:
        return len(self._tools)

    def get(self, tool_name: str) -> ToolDefinition:
        """按精确名称获取工具，未知名称明确失败。"""
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
        """按精确工具名、分类和能力做确定性过滤，不执行语义搜索。"""
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
        """返回稳定排序后的全部公开工具名。"""
        return tuple(sorted(self._tools))


def _extract_input_schema(operation: dict[str, Any]) -> dict[str, Any]:
    """把 OpenAPI requestBody 或 query parameters 统一转换成对象 Schema。"""
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
    """将原 MCP Schema 收敛为模型可直接使用的 Unified 公共契约。"""
    result = deepcopy(schema)
    result.setdefault("type", "object")
    properties = result.setdefault("properties", {})
    required = list(result.get("required") or [])

    # 统一数据工具必须显式携带业务上下文；兼容旧 OpenAPI 遗漏 required 的情况。
    if "bk_biz_id" in properties and "bk_biz_id" not in required:
        required.append("bk_biz_id")
    if "bk_biz_id" in properties:
        properties["bk_biz_id"]["type"] = "string"
    if tool_name in {"create_dashboard", "update_dashboard"}:
        # standalone 历史 wire-format 将 configs 描述为字符串；Unified 直接接收 JSON，
        # 而后端 Resource 实际需要字典，因此在公共 Schema 中修正类型。
        properties["configs"].update(
            type="object",
            minProperties=1,
            additionalProperties={"type": "string"},
        )

    # 后端兼容字段由 Unified 从 bk_biz_id 派生，模型只提交一个业务标识。
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
    """递归拒绝对象中的未声明字段，避免身份和权限参数被夹带。"""
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
    """提取模型需要关注的结果数量和时间跨度限制。"""
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
    """根据风险、时间参数和资源类型生成模型执行提示。"""
    guidelines: list[str] = []
    if tool.requires_confirmation:
        guidelines.append("该工具会产生写入、任务或数据导出；必须在用户明确确认后传 confirm=true。")
    if tool.risk == "data_export":
        guidelines.append("返回内容或下载地址可能进入模型上下文，只返回用户明确要求的数据。")
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
    """返回 APIGW MCP OpenAPI 的仓库目录。"""
    return Path(settings.BASE_DIR) / "support-files" / "apigw" / "resources" / "internal" / "user"


def load_tool_registry(root: Path | None = None) -> ToolRegistry:
    """读取全部公开 Source，合成并校验唯一的 ToolRegistry。"""
    root = root or _catalog_root()
    enabled = native_tool_names()
    tools: dict[str, ToolDefinition] = {}
    discovered_operation_ids: set[str] = set()
    digest = hashlib.sha256()

    # Step 1: 校验公开 Source 白名单，新增文件必须先补齐元信息再进入目录。
    declared_files = {filename for filenames in SOURCE_FILES.values() for filename in filenames}
    repository_files = {path.name for path in root.glob("*mcp*.yaml")} - {"unified_mcp.yaml"} - IGNORED_SOURCE_FILES
    if repository_files != declared_files:
        raise RuntimeError(
            "unified MCP source-file drift: "
            f"unreviewed={sorted(repository_files - declared_files)}, "
            f"missing={sorted(declared_files - repository_files)}"
        )

    # Step 2: 从每个 OpenAPI operation 提取名称、Schema 和后端路由。
    for category, filenames in SOURCE_FILES.items():
        for filename in filenames:
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
                    if tool_name not in CAPABILITIES:
                        continue
                    backend = (operation.get("x-bk-apigateway-resource") or {}).get("backend") or {}

                    # Step 3: 注入人工评审过的能力标签，并据此计算风险等级。
                    capabilities = CAPABILITIES[tool_name]
                    risk = (
                        "data_export"
                        if "export" in capabilities
                        else "mutation"
                        if "mutation" in capabilities
                        else "query"
                    )
                    # Step 4: 归一化 Schema；写入、任务和导出工具统一要求显式确认。
                    source_schema = _extract_input_schema(operation)
                    forwards_confirmation = "confirm" in source_schema.get("properties", {})
                    requires_confirmation = risk != "query"
                    schema = _normalize_public_schema(tool_name, source_schema)
                    if requires_confirmation:
                        schema.setdefault("properties", {})["confirm"] = {
                            "type": "boolean",
                            "enum": [True],
                            "description": "Must be true after explicit user confirmation. 用户明确确认后必须传 true。",
                        }
                        schema["required"] = list(dict.fromkeys([*schema.get("required", []), "confirm"]))
                    # Step 5: 只有动态配置显式启用的工具才注入 native-first 权限契约。
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
                    # Step 6: 将 YAML 契约和代码元信息合成为不可变 ToolDefinition。
                    tools[tool_name] = ToolDefinition(
                        name=tool_name,
                        title=TITLES[tool_name],
                        category=category,
                        capabilities=capabilities,
                        description=description,
                        input_schema=schema,
                        backend_method=str(backend.get("method") or method).upper(),
                        backend_path=str(backend.get("path") or api_path),
                        iam_action=CATEGORY_ACTIONS.get(category, ""),
                        prerequisites=PREREQUISITES.get(tool_name, ()),
                        risk=risk,
                        permission_exempt=tool_name in PERMISSION_EXEMPT_TOOL_NAMES,
                        additional_iam_actions=ADDITIONAL_IAM_ACTIONS.get(tool_name, ()),
                        requires_confirmation=requires_confirmation,
                        forwards_confirmation=forwards_confirmation,
                        backend_derived_fields=BACKEND_DERIVED_FIELDS.get(tool_name, ()),
                        native_permission=deepcopy(NATIVE_PERMISSIONS[tool_name]) if tool_name in enabled else None,
                    )

    # Step 7: 校验工具、Metadata 和权限契约一一对应，避免静默漏注册或无权限开放。
    expected = set(CAPABILITIES)
    actual = set(tools)
    unprotected = sorted(
        tool.name
        for tool in tools.values()
        if not tool.native_permission and not tool.legacy_action_ids and not tool.permission_exempt
    )
    if unprotected:
        raise RuntimeError(f"executable Unified MCP tools require a permission contract: {unprotected}")
    if actual != expected or discovered_operation_ids != expected:
        raise RuntimeError(
            "unified MCP registry drift: "
            f"missing_metadata={sorted(discovered_operation_ids - expected)}, "
            f"missing_source={sorted(expected - discovered_operation_ids)}, "
            f"missing_tools={sorted(expected - actual)}, extra_tools={sorted(actual - expected)}"
        )
    # Step 8: YAML、Metadata 或启用配置任一变化都会生成新的目录版本。
    digest.update(
        yaml.safe_dump(
            {
                "category_actions": CATEGORY_ACTIONS,
                "additional_iam_actions": ADDITIONAL_IAM_ACTIONS,
                "ignored_source_files": sorted(IGNORED_SOURCE_FILES),
                "permission_exempt_tools": sorted(PERMISSION_EXEMPT_TOOL_NAMES),
                "native_permissions": NATIVE_PERMISSIONS,
                "native_tools": enabled,
                "monitor_system_id": settings.BK_IAM_SYSTEM_ID,
                "source_files": SOURCE_FILES,
                "executable_tools": sorted(EXECUTABLE_TOOL_NAMES),
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
    """按当前动态配置返回进程内缓存的工具目录。"""
    return _cached_tool_registry(native_tool_names(), settings.BK_IAM_SYSTEM_ID)
