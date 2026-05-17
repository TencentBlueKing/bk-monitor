"""采集配置新旧格式兼容转换工具。

提供 旧格式 dict ↔ bk-monitor-base 领域模型 之间的双向转换：

* ``convert_save_params_to_base``            旧版 Save 入参 → CreateOrUpdateDeploymentParams
* ``convert_deployment_to_legacy``           MetricPluginDeployment → 旧版详情格式
* ``convert_deployment_to_legacy_list_item`` MetricPluginDeployment → 旧版列表项格式
* ``convert_deployment_status_to_legacy``    Base 状态 → 旧版 OperationResult
* ``convert_deployment_status_to_task_status`` Base 状态 → 旧版 TaskStatus
* ``convert_plugin_to_legacy_info``          MetricPlugin → 旧版 plugin_info
* ``label_to_object_type``                   插件 label → 旧版 target_object_type
* ``convert_scope_to_remote_host``           Base remote_scope → 旧版 remote_collecting_host
* ``convert_remote_host_to_scope``           旧版 remote_collecting_host → Base remote_scope
"""

from __future__ import annotations

import logging
from typing import Any

from bk_monitor_base.domains.metric_plugin.define import (
    CreateOrUpdateDeploymentParams,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    VersionTuple,
)

from monitor_web.collecting.constant import OperationResult, TaskStatus
from monitor_web.plugin.compat import convert_metric_json_to_legacy, convert_plugin_type_to_legacy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 状态枚举映射
# ---------------------------------------------------------------------------
#
# 注意：
# 1. 这里的 `status` / `task_status` 仍然是“列表返回值兼容映射”，并不等同于
#    CollectConfigListResource 的服务端筛选语义。
# 2. 列表筛选语义已按“运行态(status) / 任务态(task_status)”在 resource 层单独翻译为
#    base 原子部署状态与实例统计过滤；本处仅负责兼容旧字段返回。

_DEPLOYMENT_STATUS_TO_OPERATION_RESULT: dict[str, str] = {
    MetricPluginDeploymentStatusEnum.INITIALIZING.value: OperationResult.PREPARING,
    MetricPluginDeploymentStatusEnum.DEPLOYING.value: OperationResult.DEPLOYING,
    MetricPluginDeploymentStatusEnum.RUNNING.value: OperationResult.SUCCESS,
    MetricPluginDeploymentStatusEnum.STOPPED.value: OperationResult.SUCCESS,
    MetricPluginDeploymentStatusEnum.STOPPING.value: OperationResult.DEPLOYING,
    MetricPluginDeploymentStatusEnum.STARTING.value: OperationResult.DEPLOYING,
    MetricPluginDeploymentStatusEnum.FAILED.value: OperationResult.FAILED,
}

_DEPLOYMENT_STATUS_TO_TASK_STATUS: dict[str, str] = {
    MetricPluginDeploymentStatusEnum.INITIALIZING.value: TaskStatus.PREPARING,
    MetricPluginDeploymentStatusEnum.DEPLOYING.value: TaskStatus.DEPLOYING,
    MetricPluginDeploymentStatusEnum.RUNNING.value: TaskStatus.STARTED,
    MetricPluginDeploymentStatusEnum.STOPPED.value: TaskStatus.STOPPED,
    MetricPluginDeploymentStatusEnum.STOPPING.value: TaskStatus.STOPPING,
    MetricPluginDeploymentStatusEnum.STARTING.value: TaskStatus.STARTING,
    MetricPluginDeploymentStatusEnum.FAILED.value: TaskStatus.FAILED,
}


def convert_deployment_status_to_legacy(status: str) -> str:
    """将 base 部署状态转换为旧版 OperationResult 枚举值。

    Args:
        status: base 的 MetricPluginDeploymentStatusEnum 值。

    Returns:
        旧版 OperationResult 字符串。未知状态返回 DEPLOYING。
    """
    return _DEPLOYMENT_STATUS_TO_OPERATION_RESULT.get(status, OperationResult.DEPLOYING)


def convert_deployment_status_to_task_status(status: str) -> str:
    """将 base 部署状态转换为旧版 TaskStatus 枚举值。

    Args:
        status: base 的 MetricPluginDeploymentStatusEnum 值。

    Returns:
        旧版 TaskStatus 字符串。未知状态返回 DEPLOYING。
    """
    return _DEPLOYMENT_STATUS_TO_TASK_STATUS.get(status, TaskStatus.DEPLOYING)


# ---------------------------------------------------------------------------
# 标签 / 对象类型转换
# ---------------------------------------------------------------------------

_SERVICE_LABELS = {"component", "service_module", "service_process"}


def label_to_object_type(label: str) -> str:
    """根据插件的 label 推导旧版的 target_object_type（HOST / SERVICE）。

    Args:
        label: 插件标签，如 "os", "component" 等。

    Returns:
        "HOST" 或 "SERVICE"。
    """
    if label in _SERVICE_LABELS:
        return "SERVICE"
    return "HOST"


# ---------------------------------------------------------------------------
# remote_collecting_host ↔ remote_scope 互转
# ---------------------------------------------------------------------------


def convert_remote_host_to_scope(
    remote_host: dict[str, Any] | None,
) -> MetricPluginDeploymentScope | None:
    """将旧版的 remote_collecting_host 转换为 base 的 MetricPluginDeploymentScope。

    Args:
        remote_host: 旧版远程采集主机配置，如 {"bk_host_id": 100, "is_collecting_only": True}。

    Returns:
        base 的 MetricPluginDeploymentScope，或 None。
    """
    if not remote_host:
        return None
    node: dict[str, Any] = {}
    if "bk_host_id" in remote_host:
        node["bk_host_id"] = remote_host["bk_host_id"]
    elif "ip" in remote_host and "bk_cloud_id" in remote_host:
        node["ip"] = remote_host["ip"]
        node["bk_cloud_id"] = remote_host["bk_cloud_id"]
    if "bk_supplier_id" in remote_host:
        node["bk_supplier_id"] = remote_host["bk_supplier_id"]
    if "is_collecting_only" in remote_host:
        node["is_collecting_only"] = remote_host["is_collecting_only"]
    return MetricPluginDeploymentScope(node_type="INSTANCE", nodes=[node])


def convert_scope_to_remote_host(
    scope: MetricPluginDeploymentScope | None,
) -> dict[str, Any] | None:
    """将 base 的 remote_scope 转换回旧版 remote_collecting_host 格式。

    Args:
        scope: base 的远程部署范围。

    Returns:
        旧版远程采集主机 dict，或 None。
    """
    if not scope or not scope.nodes:
        return None
    return scope.nodes[0]


# ---------------------------------------------------------------------------
# 版本号转换
# ---------------------------------------------------------------------------


def convert_version_to_legacy(version: VersionTuple) -> str:
    """VersionTuple(1, 10) → "1.10"。"""
    return f"{version.major}.{version.minor}"


def convert_legacy_version_to_tuple(version_str: str) -> VersionTuple:
    """`"1.10"` → `VersionTuple(1, 10)`。"""
    parts = version_str.split(".")
    return VersionTuple(major=int(parts[0]), minor=int(parts[1]))


# ---------------------------------------------------------------------------
# 入参转换
# ---------------------------------------------------------------------------


def resolve_plugin_version(
    bk_tenant_id: str,
    plugin_id: str,
) -> VersionTuple:
    """获取插件的最新已发布版本号。

    Args:
        bk_tenant_id: 租户ID。
        plugin_id: 插件ID。

    Returns:
        最新已发布版本的 VersionTuple。
    """
    from bk_monitor_base.domains.metric_plugin.operation import get_metric_plugin

    plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    return plugin.version


def convert_save_params_to_base(
    data: dict[str, Any],
    bk_tenant_id: str,
    plugin_version: VersionTuple | None = None,
) -> CreateOrUpdateDeploymentParams:
    """将旧版 SaveCollectConfig 的请求参数转换为 base 的 CreateOrUpdateDeploymentParams。

    Args:
        data: 旧版请求数据（经过 Serializer 校验后的）。
        bk_tenant_id: 租户ID。
        plugin_version: 显式指定的插件版本，为 None 时自动获取最新版本。

    Returns:
        base 的 CreateOrUpdateDeploymentParams。
    """
    if plugin_version is None:
        plugin_version = resolve_plugin_version(bk_tenant_id, data["plugin_id"])

    return CreateOrUpdateDeploymentParams(
        id=data.get("id"),
        name=data["name"],
        plugin_id=data["plugin_id"],
        plugin_version=plugin_version,
        target_scope=MetricPluginDeploymentScope(
            node_type=data["target_node_type"],
            nodes=data["target_nodes"],
        ),
        remote_scope=convert_remote_host_to_scope(data.get("remote_collecting_host")),
        params=data.get("params", {}),
    )


# ---------------------------------------------------------------------------
# 出参转换
# ---------------------------------------------------------------------------


def convert_plugin_to_legacy_info(plugin: MetricPlugin) -> dict[str, Any]:
    """将 base MetricPlugin 转换为旧版 plugin_info 字典。

    Args:
        plugin: base 的 MetricPlugin 实例。

    Returns:
        旧版 plugin_info 格式的字典。
    """
    # 将 params 转为 config_json 格式
    config_json: list[dict[str, Any]] = []
    for param in plugin.params:
        param_dict = param.model_dump() if hasattr(param, "model_dump") else dict(param)
        config_json.append(
            {
                "name": param_dict.get("name", ""),
                "type": param_dict.get("type", "text"),
                "mode": param_dict.get("mode", "collector"),
                "default": param_dict.get("default"),
                "description": param_dict.get("description", ""),
            }
        )

    metric_json = convert_metric_json_to_legacy(
        [m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in plugin.metrics]
    )

    return {
        "plugin_id": plugin.id,
        "plugin_display_name": plugin.name,
        "plugin_type": convert_plugin_type_to_legacy(plugin.type),
        "config_json": config_json,
        "metric_json": metric_json,
        "description_md": plugin.description_md,
        "logo": plugin.logo,
        "label": plugin.label,
        "is_support_remote": plugin.is_support_remote,
    }


def convert_deployment_to_legacy(
    deployment: MetricPluginDeployment,
    version: MetricPluginDeploymentVersion | None,
    plugin: MetricPlugin,
) -> dict[str, Any]:
    """将 base 的 MetricPluginDeployment + Version + Plugin 转换为旧版 API 的详情格式。

    Args:
        deployment: base 部署项。
        version: base 部署版本（最新版）。
        plugin: base 插件信息。

    Returns:
        旧版采集配置详情字典。
    """
    return {
        "id": deployment.id,
        "deployment_id": deployment.id,
        "name": deployment.name,
        "bk_biz_id": deployment.bk_biz_id,
        "collect_type": convert_plugin_type_to_legacy(plugin.type),
        "plugin_id": deployment.plugin_id,
        "target_object_type": label_to_object_type(plugin.label),
        "target_node_type": version.target_scope.node_type if version else "",
        "target_nodes": version.target_scope.nodes if version else [],
        "params": version.params if version else {},
        "remote_collecting_host": convert_scope_to_remote_host(version.remote_scope) if version else None,
        "plugin_info": convert_plugin_to_legacy_info(plugin),
        "subscription_id": deployment.related_params.get("subscription_id", 0),
        "label": plugin.label,
        "label_info": _build_label_info(plugin.label),
        "status": convert_deployment_status_to_legacy(deployment.status),
        "task_status": convert_deployment_status_to_task_status(deployment.status),
        "create_time": deployment.created_at,
        "create_user": deployment.created_by,
        "update_time": deployment.updated_at,
        "update_user": deployment.updated_by,
    }


def convert_deployment_to_legacy_list_item(
    deployment: MetricPluginDeployment,
    version: MetricPluginDeploymentVersion | None,
    plugin: MetricPlugin,
    *,
    space_name: str = "",
    need_upgrade: bool = False,
) -> dict[str, Any]:
    """将 base 的 MetricPluginDeployment 转换为旧版列表项格式。

    Args:
        deployment: base 部署项。
        version: base 部署版本（最新版）。
        plugin: base 插件信息。
        space_name: 空间名称。
        need_upgrade: 是否需要升级。

    Returns:
        旧版列表项字典。
    """
    config_version = version.plugin_version.minor if version else 0
    info_version = version.plugin_version.major if version else 0
    return {
        "id": deployment.id,
        "name": deployment.name,
        "bk_biz_id": deployment.bk_biz_id,
        "space_name": space_name,
        "collect_type": convert_plugin_type_to_legacy(plugin.type),
        "status": convert_deployment_status_to_legacy(deployment.status),
        "task_status": convert_deployment_status_to_task_status(deployment.status),
        "target_object_type": label_to_object_type(plugin.label),
        "target_node_type": version.target_scope.node_type if version else "",
        "plugin_id": deployment.plugin_id,
        "target_nodes_count": len(version.target_scope.nodes) if version else 0,
        "need_upgrade": need_upgrade,
        "config_version": config_version,
        "info_version": info_version,
        "error_instance_count": 0,
        "total_instance_count": 0,
        "running_tasks": [],
        "label_info": _build_label_info(plugin.label),
        "label": plugin.label,
        "update_time": deployment.updated_at,
        "update_user": deployment.updated_by,
    }


def _build_label_info(label: str) -> dict[str, Any]:
    """构建旧版 label_info 结构。

    Args:
        label: 插件标签。

    Returns:
        label_info 字典，包含 first_label_name 和 second_label_name。
    """
    parts = label.split("/") if label else []
    first_label = parts[0] if parts else ""
    second_label = parts[1] if len(parts) > 1 else ""
    return {
        "first_label_name": first_label,
        "second_label_name": second_label,
    }
