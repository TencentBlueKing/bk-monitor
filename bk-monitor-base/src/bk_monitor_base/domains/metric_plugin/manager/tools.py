import shutil
from pathlib import Path
from typing import Any, cast

import yaml

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.define import MetricPlugin, VersionTuple
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginManagerNotFoundError, MetricPluginNotFoundError
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager
from bk_monitor_base.domains.metric_plugin.manager.job.base import JobPluginManager, SQLPluginManager
from bk_monitor_base.domains.metric_plugin.manager.k8s import K8sPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import NodemanPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.built_in import BuiltInPluginManager
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel

from .job.db2 import DB2PluginManager
from .job.mssql import MSSQLPluginManager
from .job.mysql import MysqlPluginManager
from .job.oracle import OraclePluginManager
from .node_man.datadog import DataDogPluginManager
from .node_man.exporter import ExporterPluginManager
from .node_man.jmx import JMXPluginManager
from .node_man.log import LogPluginManager
from .node_man.process import ProcessPluginManager
from .node_man.pushgateway import PushgatewayPluginManager
from .node_man.script import ScriptPluginManager
from .node_man.snmp import SNMPPluginManager
from .node_man.snmp_trap import SNMPTrapPluginManager

# 节点管理插件管理器映射
NODEMAN_PLUGIN_MANGERS: dict[str, type[NodemanPluginManager]] = {
    PluginType.EXPORTER: ExporterPluginManager,
    PluginType.SCRIPT: ScriptPluginManager,
    PluginType.JMX: JMXPluginManager,
    PluginType.DATADOG: DataDogPluginManager,
    PluginType.PUSHGATEWAY: PushgatewayPluginManager,
    PluginType.SNMP: SNMPPluginManager,
}

NODEMAN_BUILT_IN_PLUGIN_MANGERS: dict[str, type[BuiltInPluginManager]] = {
    PluginType.PROCESS: ProcessPluginManager,
    PluginType.LOG: LogPluginManager,
    PluginType.SNMP_TRAP: SNMPTrapPluginManager,
}

NODEMAN_DEPLOY_PLUGIN_MANAGERS: dict[str, type[NodemanPluginManager] | type[BuiltInPluginManager]] = {
    **NODEMAN_PLUGIN_MANGERS,
    **NODEMAN_BUILT_IN_PLUGIN_MANGERS,
}

# 作业平台插件管理器映射
JOB_PLUGIN_MANGERS: dict[str, type[JobPluginManager]] = {
    "job_mysql": MysqlPluginManager,
    "job_oracle": OraclePluginManager,
    "job_db2": DB2PluginManager,
    "job_mssql": MSSQLPluginManager,
}

PLUGIN_MANAGERS: dict[str, type[BaseMetricPluginManager]] = {
    **NODEMAN_DEPLOY_PLUGIN_MANAGERS,
    **JOB_PLUGIN_MANGERS,
    PluginType.K8S: K8sPluginManager,
}


def get_plugin_type_from_package(package_file: Path) -> str:
    """从插件包中识别插件类型。

    类型识别发生在路由到具体插件管理器之前，因此这里遍历已注册的管理器，让各管理器
    通过自身的包目录规则寻找 ``info/meta.yaml``。
    """
    is_dir = package_file.is_dir()

    if not is_dir:
        filename = package_file.name
        parts = filename.split("__")
        if len(parts) == 3:
            return parts[1].lower()

    extract_dir = package_file if is_dir else BaseMetricPluginManager.extract_package(package_file)
    try:
        tried_manager_classes: set[type[BaseMetricPluginManager]] = set()
        for manager_class in PLUGIN_MANAGERS.values():
            if manager_class in tried_manager_classes:
                continue
            tried_manager_classes.add(manager_class)

            try:
                meta_file = manager_class.find_plugin_type_meta_file(extract_dir)
            except ValueError:
                continue

            with meta_file.open("r", encoding="utf-8") as f:
                meta_data = yaml.safe_load(f)
            meta_data_dict = cast(dict[str, Any], meta_data) if isinstance(meta_data, dict) else {}
            plugin_type = str(meta_data_dict.get("plugin_type", "")).lower()
            if not plugin_type:
                raise ValueError(f"meta.yaml文件中未找到plugin_type字段: {meta_file}")
            return plugin_type

        raise ValueError(f"插件包中未找到可用于识别类型的 meta.yaml 文件: {extract_dir}")
    except Exception as e:
        raise ValueError("解析插件包获取插件类型失败") from e
    finally:
        if not is_dir:
            shutil.rmtree(extract_dir)


def get_nodeman_plugin_manager(plugin: MetricPlugin) -> NodemanPluginManager:
    """获取节点管理插件管理器

    Args:
        plugin: 插件

    Returns:
        NodemanPluginManager: 节点管理插件管理器

    Raises:
        MetricPluginManagerNotFoundError: 节点管理插件管理器不存在
    """
    try:
        return NODEMAN_PLUGIN_MANGERS[plugin.type.lower()](plugin)
    except KeyError:
        raise MetricPluginManagerNotFoundError(f"节点管理插件管理器不存在: {plugin.type}")


def get_job_plugin_manager(plugin: MetricPlugin) -> JobPluginManager:
    """获取作业平台插件管理器

    Args:
        plugin: 插件

    Returns:
        JobPluginManager: 作业平台插件管理器

    Raises:
        MetricPluginManagerNotFoundError: 作业平台插件管理器不存在
    """
    try:
        return JOB_PLUGIN_MANGERS[plugin.type.lower()](plugin)
    except KeyError:
        raise MetricPluginManagerNotFoundError(f"作业平台插件管理器不存在: {plugin.type}")


def get_nodeman_built_in_plugin_manager(plugin: MetricPlugin) -> BuiltInPluginManager:
    """获取节点管理内置插件管理器

    Args:
        plugin: 插件

    Returns:
        BuiltInPluginManager: 节点管理内置插件管理器

    Raises:
        MetricPluginManagerNotFoundError: 节点管理内置插件管理器不存在
    """

    try:
        return NODEMAN_BUILT_IN_PLUGIN_MANGERS[plugin.type.lower()](plugin)
    except KeyError:
        raise MetricPluginManagerNotFoundError(f"内置插件管理器不存在: {plugin.type}")


def get_nodeman_deploy_plugin_manager(plugin: MetricPlugin) -> NodemanPluginManager | BuiltInPluginManager:
    """获取可用于节点管理部署的插件管理器。

    Args:
        plugin: 插件

    Returns:
        NodemanPluginManager | BuiltInPluginManager: 可用于部署的插件管理器

    Raises:
        MetricPluginManagerNotFoundError: 节点管理部署插件管理器不存在
    """
    try:
        return NODEMAN_DEPLOY_PLUGIN_MANAGERS[plugin.type.lower()](plugin)
    except KeyError:
        raise MetricPluginManagerNotFoundError(f"节点管理部署插件管理器不存在: {plugin.type}")


def get_plugin_manager_class(plugin_type: str) -> type[BaseMetricPluginManager]:
    """获取插件管理器类

    Args:
        plugin_type: 插件类型

    Returns:
        BaseMetricPluginManager: 插件管理器类

    Raises:
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    if plugin_type.lower() in PLUGIN_MANAGERS:
        return PLUGIN_MANAGERS[plugin_type.lower()]

    raise MetricPluginManagerNotFoundError(f"插件管理器不存在: {plugin_type}")


def get_plugin_manager(
    bk_tenant_id: str, plugin_id: str, version: VersionTuple | None = None
) -> BaseMetricPluginManager:
    """获取插件管理器（通用方法）

    根据插件类型自动判断是 nodeman 还是 job 类型，并返回对应的管理器实例。

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID

    Returns:
        BaseMetricPluginManager: 插件管理器实例

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """

    plugin_model = MetricPluginModel.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
    ).first()
    if not plugin_model:
        raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

    plugin_manager_class = get_plugin_manager_class(plugin_model.type)
    return plugin_manager_class(plugin=plugin_model.to_plugin(version=version), plugin_model=plugin_model)


def get_sql_plugin_manager(plugin: MetricPlugin) -> SQLPluginManager:
    """获取SQL类作业平台插件管理器

    Args:
        plugin: 插件

    Returns:
        SQLPluginManager: SQL类作业平台插件管理器

    Raises:
        MetricPluginManagerNotFoundError: SQL类作业平台插件管理器不存在
    """
    job_plugin_manager = get_job_plugin_manager(plugin)
    if not isinstance(job_plugin_manager, SQLPluginManager):
        raise MetricPluginManagerNotFoundError(f"SQL类作业平台插件管理器不存在: {plugin.type}")
    return job_plugin_manager
