"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Set

from django.utils.translation import ugettext as _
from rest_framework import serializers

from api.cmdb.define import TopoNode, TopoTree
from bkmonitor.data_source import BkMonitorLogDataSource
from bkmonitor.utils.local import local
from constants.cmdb import TargetNodeType
from core.drf_resource import Resource, api
from core.errors.api import BKAPIError
from monitor_web.collecting.constant import CollectStatus
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.collecting.utils import fetch_sub_statistics
from monitor_web.commons.data_access import ResultTable
from monitor_web.models import CollectConfigMeta, CustomEventGroup
from monitor_web.models.plugin import PluginVersionHistory
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from utils import business
from utils.query_data import TSDataBase

logger = logging.getLogger(__name__)


class CollectTargetStatusResource(Resource):
    """
    获取采集配置下发状态（默认进行差异比对）
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=True)
        auto_running_tasks = serializers.ListField(required=False, label="自动运行的任务")

    def perform_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(id=params["id"])
        installer = get_collect_installer(collect_config)
        return {
            "config_info": collect_config.get_info(),
            "contents": installer.status(diff=params["diff"]),
        }


class CollectRunningStatusResource(CollectTargetStatusResource):
    """
    获取采集配置主机的运行状态（默认不进行差异比对）
    TODO: 和前端讨论后续是否弃用
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=False)


class CollectInstanceStatusResource(CollectTargetStatusResource):
    """
    获取采集配置下发实例的运行状态（默认不进行差异比对）
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置id")
        diff = serializers.BooleanField(required=False, label="是否只返回差异", default=False)


class CollectTargetStatusTopoResource(Resource):
    """
    获取检查视图左侧数据（ip列表或topo树）的接口
    """

    # 拓扑类型的采集配置
    topo_node_types = {TargetNodeType.TOPO, TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务ID"))
        id = serializers.IntegerField(label=_("采集配置ID"))

    @staticmethod
    def fetch_latest_version_by_config(collect_config: CollectConfigMeta) -> PluginVersionHistory:
        """
        根据主配置拿最新子配置版本号
        """
        config_version = collect_config.deployment_config.plugin_version.config_version
        latest_info_version = PluginVersionHistory.objects.filter(
            plugin=collect_config.plugin, config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE
        ).latest("info_version")
        return latest_info_version

    @classmethod
    def nodata_test(cls, collect_config: CollectConfigMeta, target_list: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        无数据检测
        """
        if not target_list:
            return {}

        # 取3个采集周期内的数据，若3个采集周期都无数据则判断为无数据
        period = collect_config.deployment_config.params["collector"]["period"]

        filter_dict = {"bk_collect_config_id": str(collect_config.id)}

        # 日志关键字无数据判断
        if (
            collect_config.plugin.plugin_type == PluginType.LOG
            or collect_config.plugin.plugin_type == PluginType.SNMP_TRAP
        ):
            version = collect_config.deployment_config.plugin_version
            event_group_name = "{}_{}".format(version.plugin.plugin_type, version.plugin_id)
            group_info = CustomEventGroup.objects.get(name=event_group_name)

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
            has_data_targets = set()
            for record in records:
                has_data_targets.add("|".join(str(record[field]) for field in group_by))

            target_status = {}
            for target in target_list:
                key = "|".join(str(target[field]) for field in group_by)
                target_status[key] = key not in has_data_targets

            return target_status

        # 获取结果表配置
        if collect_config.plugin.is_split_measurement:
            db_name = f"{collect_config.plugin.plugin_type}_{collect_config.plugin.plugin_id}".lower()
            group_result = api.metadata.query_time_series_group(bk_biz_id=0, time_series_group_name=db_name)
            result_tables = [ResultTable.time_series_group_to_result_table(group_result)]
        else:
            if collect_config.plugin.plugin_type == PluginType.PROCESS:
                db_name = "process:perf"
                metric_json = PluginManagerFactory.get_manager(
                    plugin=collect_config.plugin.plugin_id, plugin_type=collect_config.plugin.plugin_type
                ).gen_metric_info()

                metric_json = [table for table in metric_json if table["table_name"] == "perf"]
            else:
                db_name = "{plugin_type}_{plugin_id}".format(
                    plugin_type=collect_config.plugin.plugin_type, plugin_id=collect_config.plugin.plugin_id
                )
                latest_info_version = cls.fetch_latest_version_by_config(collect_config)
                metric_json = latest_info_version.info.metric_json
            result_tables = [ResultTable.new_result_table(table) for table in metric_json]

        # 获取3个采集周期内的数据
        if period < 60:
            filter_dict["time__gt"] = f"{period * 3 // 60 + 1}m"
        else:
            filter_dict["time__gt"] = f"{period // 60 * 3}m"

        ts_database = TSDataBase(
            db_name=db_name.lower(), result_tables=result_tables, bk_biz_id=collect_config.bk_biz_id
        )
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
    def get_instance_info(instance: Dict) -> Dict:
        """
        获取实例信息
        """
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
        cls, topo_node: TopoNode, module_mapping: Dict[int, List[Dict[str, Any]]], result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        创建拓扑树
        """
        # 如果是模块节点，直接返回
        if topo_node.bk_obj_id == "module":
            if topo_node.bk_inst_id in module_mapping:
                result.extend(module_mapping[topo_node.bk_inst_id])
            return

        sub_nodes = []
        for child in topo_node.child:
            sub_result = []
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

    def perform_request(self, params: Dict[str, Any]):
        collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
            id=params["id"], bk_biz_id=params["bk_biz_id"]
        )
        target_node_type = collect_config.deployment_config.target_node_type

        if target_node_type == TargetNodeType.CLUSTER:
            return []

        # 获取拓扑信息用于后续处理
        if collect_config.deployment_config.target_node_type in self.topo_node_types:
            topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=collect_config.bk_biz_id)
        else:
            topo_tree = None

        installer = get_collect_installer(collect_config, topo_tree=topo_tree)

        # 获取实例采集状态并搜集节点信息，避免服务模板还需要进行转换
        collect_status = installer.status(diff=False)
        topo_nodes: Set[str] = set()
        instance_status: Dict[str, Dict[str, Any]] = {}
        targets: List[Dict[str, Any]] = []
        for node in collect_status:
            # 记录节点信息
            if node.get("bk_obj_id"):
                topo_nodes.add(f"{node['bk_obj_id']}|{node['bk_inst_id']}")

            for instance in node.get("child", []):
                # 记录实例信息
                instance_status[instance["instance_id"]] = instance

                # 准备目标列表，用于后续获取数据状态
                if "service_instance_id" in instance:
                    targets.append({"bk_target_service_instance_id": instance["service_instance_id"]})
                else:
                    targets.append({"bk_target_ip": instance["ip"], "bk_target_cloud_id": instance["bk_cloud_id"]})

        # 获取数据状态
        no_data_info = self.nodata_test(collect_config, targets)

        # 填充数据状态
        for instance in instance_status.values():
            # 获取实例数据状态
            if instance.get("service_instance_id"):
                no_data = no_data_info.get(str(instance["service_instance_id"]), True)
            else:
                no_data = no_data_info.get(f"{instance['ip']}|{instance['bk_cloud_id']}", True)

            if no_data and instance["status"] == CollectStatus.SUCCESS:
                instance["status"] = CollectStatus.NODATA

        result = []
        if target_node_type in self.topo_node_types:
            module_mapping = defaultdict(list)
            for instance in instance_status.values():
                instance_info = self.get_instance_info(instance)
                for module_id in instance.get("bk_module_ids") or [instance["bk_module_id"]]:
                    module_mapping[module_id].append(instance_info)
            self.create_topo_tree(topo_tree, module_mapping, result)
        elif target_node_type == TargetNodeType.INSTANCE:
            for instance in instance_status.values():
                result.append(self.get_instance_info(instance))
        else:
            # TODO: k8s插件下发
            pass
        return result


class UpdateConfigInstanceCountResource(Resource):
    """
    更新启用中的采集配置的主机总数和异常数
    """

    def perform_request(self, data):
        if data.get("id"):
            logger.info("start async celery task: update config instance count")
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(id=data.get("id"))
            config_list = [collect_config]
        else:
            logger.info("start period celery task: update config instance count")
            config_list = list(CollectConfigMeta.objects.select_related("deployment_config").all())

        if config_list:
            local.username = business.maintainer(str(config_list[0].bk_biz_id))
        else:
            return

        try:
            __, collect_statistics_data = fetch_sub_statistics(config_list)
        except BKAPIError as e:
            logger.error("请求节点管理状态统计接口失败: {}".format(e))
            return

        # 统计节点管理订阅的正常数、异常数
        result_dict = {}
        for item in collect_statistics_data:
            status_number = {}
            for status_result in item.get("status", []):
                status_number[status_result["status"]] = status_result["count"]
            result_dict[item["subscription_id"]] = {
                "total_instance_count": item.get("instances", 0),
                "error_instance_count": status_number.get(CollectStatus.FAILED, 0),
            }

        for config in config_list:
            cache_data = result_dict.get(config.deployment_config.subscription_id)
            CollectConfigMeta.objects.filter(id=config.id).update(cache_data=cache_data)
