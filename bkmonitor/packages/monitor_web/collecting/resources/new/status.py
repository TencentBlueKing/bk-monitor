"""采集配置 status Resource —— 适配 bk-monitor-base 的新实现。

与旧版 ``resources/old/status.py`` 保持完全相同的入参/出参契约，
内部调用 ``bk_monitor_base.domains.metric_plugin.installer`` 完成核心逻辑。

Base 的 ``NodemanInstaller.status(diff)`` 已完整实现旧版兼容的 status 返回格式，
包括 diff 模式、实例状态转换、节点分组（TOPO/HOST/DYNAMIC_GROUP/TEMPLATE）等，
SaaS 层只需做简单的调用转发和 config_info 构建。
"""

import logging
import time
from collections import defaultdict
from typing import Any

from django.utils.translation import gettext as _
from rest_framework import serializers

from bk_monitor_base.domains.metric_plugin.installer.tools import get_installer
from bk_monitor_base.domains.metric_plugin.operation import (
    get_metric_plugin,
    get_metric_plugin_deployment,
)
from bkmonitor.data_source import BkMonitorLogDataSource
from bkmonitor.utils.request import get_request_tenant_id
from constants.cmdb import TargetNodeType
from core.drf_resource import Resource, api
from core.errors.api import BKAPIError
from core.errors.collecting import CollectConfigNotExist
from monitor_web.collecting.compat import (
    convert_deployment_status_to_task_status,
    label_to_object_type,
)
from monitor_web.collecting.constant import CollectStatus
from monitor_web.collecting.utils import fetch_sub_statistics
from monitor_web.commons.data_access import ResultTable
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import CustomEventGroup
from monitor_web.plugin.compat import convert_plugin_type_to_legacy
from utils.query_data import TSDataBase

logger = logging.getLogger(__name__)


def _build_config_info(deployment, version, plugin) -> dict[str, Any]:
    """从 base 领域对象构建旧版 collect_config.get_info() 格式。

    Args:
        deployment: base 部署项。
        version: base 部署版本。
        plugin: base 插件信息。

    Returns:
        旧版 config_info 字典。
    """
    return {
        "id": deployment.id,
        "name": deployment.name,
        "bk_biz_id": deployment.bk_biz_id,
        "target_object_type": label_to_object_type(plugin.label),
        "target_node_type": version.target_scope.node_type if version else "",
        "plugin_id": deployment.plugin_id,
        "label": plugin.label,
        "config_version": version.plugin_version.minor if version else 0,
        "info_version": version.plugin_version.major if version else 0,
        "last_operation": convert_deployment_status_to_task_status(deployment.status),
    }


class CollectTargetStatusResource(Resource):
    """获取采集配置下发状态（默认进行差异比对）。

    通过 base ``installer.status(diff)`` 获取旧版兼容格式的状态结果。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=True)
        auto_running_tasks = serializers.ListField(required=False, label="自动运行的任务")

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = get_request_tenant_id()

        try:
            deployment, version = get_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                deployment_id=params["id"],
                bk_biz_id=params["bk_biz_id"],
            )
        except Exception:
            raise CollectConfigNotExist({"msg": params["id"]})

        plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=deployment.plugin_id)
        installer = get_installer(deployment, operator="")

        return {
            "config_info": _build_config_info(deployment, version, plugin),
            "contents": installer.status(diff=params["diff"]),
        }


class CollectRunningStatusResource(CollectTargetStatusResource):
    """获取采集配置主机的运行状态（默认不进行差异比对）。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=False)


class CollectInstanceStatusResource(CollectTargetStatusResource):
    """获取采集配置下发实例的运行状态（默认不进行差异比对）。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=False)


class CollectTargetStatusTopoResource(Resource):
    """获取检查视图左侧数据（ip列表或topo树）的接口。

    消费 ``installer.status(diff=False)`` 的结果，结合 NoData 检测、拓扑树构建。
    """

    topo_node_types = {TargetNodeType.TOPO, TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务ID"))
        id = serializers.IntegerField(label=_("采集配置ID"))

    @classmethod
    def nodata_test(
        cls,
        bk_tenant_id: str,
        deployment,
        version,
        plugin,
        target_list: list[dict[str, Any]],
    ) -> dict[str, bool]:
        """无数据检测。

        Args:
            bk_tenant_id: 租户ID。
            deployment: base 部署项。
            version: base 部署版本。
            plugin: base 插件信息。
            target_list: 目标实例列表。

        Returns:
            key->是否无数据的映射。
        """
        if not target_list:
            return {}

        period = version.params.get("collector", {}).get("period", 60)
        plugin_type = convert_plugin_type_to_legacy(plugin.type)
        filter_dict: dict[str, Any] = {"bk_collect_config_id": str(deployment.id)}

        if plugin_type in ("LOG", "SNMP_TRAP"):
            plugin_id = deployment.plugin_id
            event_group_name = f"{plugin_type}_{plugin_id}"
            try:
                group_info = CustomEventGroup.objects.get(
                    bk_biz_id=deployment.bk_biz_id, type=EVENT_TYPE.KEYWORDS, name=event_group_name
                )
            except CustomEventGroup.DoesNotExist:
                return {key: True for key in ("dummy",)}

            if "bk_target_ip" in target_list[0]:
                group_by = ["bk_target_ip", "bk_target_cloud_id"]
            else:
                group_by = ["bk_target_service_instance_id"]

            data_source = BkMonitorLogDataSource(
                table=group_info.table_id,
                group_by=group_by,
                metrics=[{"field": "_index", "method": "COUNT"}],
                filter_dict=filter_dict,
            )
            records = data_source.query_data(start_time=int(time.time()) * 1000 - period * 3000)
            has_data_targets: set[str] = set()
            for record in records:
                has_data_targets.add("|".join(str(record[field]) for field in group_by))

            target_status: dict[str, bool] = {}
            for target in target_list:
                key = "|".join(str(target[field]) for field in group_by)
                target_status[key] = key not in has_data_targets
            return target_status

        plugin_id = deployment.plugin_id
        db_name = f"{plugin_type}_{plugin_id}".lower()

        if plugin.is_split_measurement:
            group_result = api.metadata.query_time_series_group(bk_biz_id=0, time_series_group_name=db_name)
            result_tables = [ResultTable.time_series_group_to_result_table(group_result)]
        else:
            if plugin_type == "PROCESS":
                db_name = "process:perf"
                from monitor_web.plugin.manager import PluginManagerFactory

                from monitor_web.models.plugin import CollectorPluginMeta

                try:
                    old_plugin = CollectorPluginMeta.objects.get(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
                    metric_json = PluginManagerFactory.get_manager(plugin=old_plugin).gen_metric_info()
                    metric_json = [table for table in metric_json if table["table_name"] == "perf"]
                except CollectorPluginMeta.DoesNotExist:
                    metric_json = []
            else:
                metric_json_raw = [m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in plugin.metrics]
                metric_json = []
                for table in metric_json_raw:
                    metric_json.append(
                        {
                            "table_name": table.get("table_name", ""),
                            "table_desc": table.get("table_desc", ""),
                            "fields": table.get("fields", []),
                        }
                    )
            result_tables = [ResultTable.new_result_table(table) for table in metric_json]

        if period < 60:
            filter_dict["time__gt"] = f"{period * 3 // 60 + 1}m"
        else:
            filter_dict["time__gt"] = f"{period // 60 * 3}m"

        ts_database = TSDataBase(db_name=db_name.lower(), result_tables=result_tables, bk_biz_id=deployment.bk_biz_id)
        target_status_list = ts_database.no_data_test(test_target_list=target_list, filter_dict=filter_dict)
        target_status = {}
        for target in target_status_list:
            if "bk_target_ip" in target:
                key = f"{target['bk_target_ip']}|{target['bk_target_cloud_id']}"
            else:
                key = str(target["bk_target_service_instance_id"])
            target_status[key] = target["no_data"]

        return target_status

    @staticmethod
    def get_instance_info(instance: dict) -> dict:
        """获取实例信息。"""
        if "service_instance_id" in instance:
            return {
                "id": instance["service_instance_id"],
                "name": instance["instance_name"],
                "service_instance_id": instance["service_instance_id"],
                "status": instance["status"],
                "ip": instance["ip"],
                "bk_cloud_id": instance["bk_cloud_id"],
                "bk_host_id": instance["bk_host_id"],
            }
        else:
            return {
                "id": instance["bk_host_id"],
                "name": instance["ip"],
                "ip": instance["ip"],
                "bk_cloud_id": instance["bk_cloud_id"],
                "status": instance["status"],
                "bk_host_id": instance["bk_host_id"],
                "alias_name": instance["bk_host_name"],
            }

    @classmethod
    def create_topo_tree(
        cls,
        topo_node,
        module_mapping: dict[int, list[dict[str, Any]]],
        result: list[dict[str, Any]],
    ) -> None:
        """创建拓扑树。"""
        if topo_node.bk_obj_id == "module":
            if topo_node.bk_inst_id in module_mapping:
                result.extend(module_mapping[topo_node.bk_inst_id])
            return

        sub_nodes = []
        for child in topo_node.child:
            sub_result: list[dict[str, Any]] = []
            cls.create_topo_tree(child, module_mapping, sub_result)
            if not sub_result:
                continue
            sub_nodes.append(
                {
                    "id": f"{child.bk_obj_id}|{child.bk_inst_id}",
                    "name": child.bk_inst_name,
                    "bk_obj_id": child.bk_obj_id,
                    "bk_obj_name": child.bk_obj_name,
                    "bk_inst_id": child.bk_inst_id,
                    "bk_inst_name": child.bk_inst_name,
                    "children": sub_result,
                }
            )
        if sub_nodes:
            result.extend(sub_nodes)

    def perform_request(self, params: dict[str, Any]):
        bk_tenant_id = get_request_tenant_id()

        try:
            deployment, version = get_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                deployment_id=params["id"],
                bk_biz_id=params["bk_biz_id"],
            )
        except Exception:
            raise CollectConfigNotExist({"msg": params["id"]})

        plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=deployment.plugin_id)
        target_node_type = version.target_scope.node_type if version else ""

        if target_node_type == TargetNodeType.CLUSTER:
            return []

        installer = get_installer(deployment, operator="")
        collect_status = installer.status(diff=False)

        instance_status: dict[str, dict[str, Any]] = {}
        targets: list[dict[str, Any]] = []
        for node in collect_status:
            for instance in node.get("child", []):
                instance_status[instance["instance_id"]] = instance
                if "service_instance_id" in instance:
                    targets.append({"bk_target_service_instance_id": instance["service_instance_id"]})
                else:
                    targets.append({"bk_target_ip": instance["ip"], "bk_target_cloud_id": instance["bk_cloud_id"]})

        no_data_info = self.nodata_test(bk_tenant_id, deployment, version, plugin, targets)

        for instance in instance_status.values():
            if instance.get("service_instance_id"):
                no_data = no_data_info.get(str(instance["service_instance_id"]), True)
            else:
                no_data = no_data_info.get(f"{instance['ip']}|{instance['bk_cloud_id']}", True)

            if no_data and instance["status"] == CollectStatus.SUCCESS:
                instance["status"] = CollectStatus.NODATA

        result: list[dict[str, Any]] = []
        if target_node_type in self.topo_node_types:
            from api.cmdb.define import TopoTree

            topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=deployment.bk_biz_id)
            module_mapping: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for instance in instance_status.values():
                instance_info = self.get_instance_info(instance)
                for module_id in instance.get("bk_module_ids") or [instance.get("bk_module_id")]:
                    if module_id is not None:
                        module_mapping[module_id].append(instance_info)
            self.create_topo_tree(topo_tree, module_mapping, result)
        elif target_node_type == TargetNodeType.INSTANCE:
            for instance in instance_status.values():
                result.append(self.get_instance_info(instance))
        elif target_node_type == TargetNodeType.HOST:
            for instance in instance_status.values():
                result.append(self.get_instance_info(instance))
        elif target_node_type == TargetNodeType.DYNAMIC_GROUP:
            for node in collect_status:
                for child in node.get("child", []):
                    instance_id = child.get("instance_id")
                    if instance_id in instance_status:
                        instance_info = self.get_instance_info(instance_status[instance_id])
                        child.update(instance_info)
                result.append(node)

        return result


class UpdateConfigInstanceCountResource(Resource):
    """更新启用中的采集配置的主机总数和异常数。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        id = serializers.IntegerField(required=True)

    def perform_request(self, params: dict):
        from monitor_web.models import CollectConfigMeta

        bk_tenant_id = get_request_tenant_id()

        try:
            deployment, version = get_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                deployment_id=params["id"],
                bk_biz_id=params["bk_biz_id"],
            )
        except Exception:
            raise CollectConfigNotExist({"msg": params["id"]})

        plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=deployment.plugin_id)
        plugin_type = convert_plugin_type_to_legacy(plugin.type)

        cache_data: dict[str, int] | None = None
        if plugin_type == "K8S":
            error_count, total_count = 0, 0
            installer = get_installer(deployment, operator="")
            for node in installer.status():
                for instance in node["child"]:
                    if instance["status"] in [CollectStatus.FAILED, CollectStatus.UNKNOWN]:
                        error_count += 1
                    total_count += 1
            cache_data = {"error_instance_count": error_count, "total_instance_count": total_count}
        else:
            try:
                collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                    bk_biz_id=params["bk_biz_id"], id=params["id"]
                )
            except CollectConfigMeta.DoesNotExist:
                logger.warning("UpdateConfigInstanceCount: ORM CollectConfigMeta not found for id=%s", params["id"])
                return

            try:
                _, collect_statistics_data = fetch_sub_statistics([collect_config])
            except BKAPIError as e:
                logger.error("请求节点管理状态统计接口失败: %s", e)
                return

            result_dict: dict[int, dict[str, int]] = {}
            for item in collect_statistics_data:
                status_number: dict[str, int] = {}
                for status_result in item.get("status", []):
                    status_number[status_result["status"]] = status_result["count"]
                result_dict[item["subscription_id"]] = {
                    "total_instance_count": item.get("instances", 0),
                    "error_instance_count": status_number.get(CollectStatus.FAILED, 0),
                }

            cache_data = result_dict.get(collect_config.deployment_config.subscription_id)

        try:
            collect_config = CollectConfigMeta.objects.get(bk_biz_id=params["bk_biz_id"], id=params["id"])
        except CollectConfigMeta.DoesNotExist:
            return

        if collect_config.cache_data != cache_data:
            collect_config.cache_data = cache_data
            collect_config.save(not_update_user=True, update_fields=["cache_data"])
