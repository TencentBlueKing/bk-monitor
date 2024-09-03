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
import traceback
from collections import OrderedDict, defaultdict

from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.data_source import BkMonitorLogDataSource
from bkmonitor.utils.local import local
from bkmonitor.utils.thread_backend import ThreadPool
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import Resource, api, resource
from core.errors.api import BKAPIError
from core.errors.collecting import SubscriptionStatusError
from monitor_web.collecting.constant import (
    COMPLEX_OPETATION_TYPE,
    CollectStatus,
    OperationType,
    TaskStatus,
)
from monitor_web.collecting.utils import fetch_sub_statistics
from monitor_web.commons.cc.utils import foreach_topo_tree, topo_tree_tools
from monitor_web.commons.data_access import ResultTable
from monitor_web.models import (
    CollectConfigMeta,
    CustomEventGroup,
    DeploymentConfigVersion,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from utils import business
from utils.query_data import TSDataBase

logger = logging.getLogger(__name__)


class BaseCollectTargetStatusResource(Resource):
    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置id")
        auto_running_tasks = serializers.ListField(required=False, label="自动运行的任务")

    def __init__(self):
        super(BaseCollectTargetStatusResource, self).__init__()
        self.bk_biz_id = None
        self.config_id = None
        self.config = None
        self.auto_running_tasks = []  # 节点管理自动执行的任务
        self.is_task_result = True  # 如果是true，则查询任务执行结果，如果是false, 则查询主机运行状况
        self.is_auto = False  # 是否是自动执行的情况
        self._service_collect_status = None  # 实例下发状态结果
        self._host_collect_status = None  # 主机下发状态结果

    def perform_request(self, validated_request_data):
        self.config_id = validated_request_data["id"]
        self.auto_running_tasks = validated_request_data.get("auto_running_tasks")
        self.init_data()

        # 是否拓扑
        if self.config.deployment_config.target_node_type == TargetNodeType.INSTANCE:
            # snmp直接获取节点状态展示
            if self.config.collect_type == "SNMP":
                self.is_task_result = False
            return self.handle_host_instance_data()

        # 是否模板
        if self.config.deployment_config.target_node_type in [
            TargetNodeType.SERVICE_TEMPLATE,
            TargetNodeType.SET_TEMPLATE,
        ]:
            if self.config.target_object_type == TargetObjectType.SERVICE:
                return self.handle_template_service_data()
            if self.config.target_object_type == TargetObjectType.HOST:
                return self.handle_template_host_data()

        # 查询模块下的主机或实例
        collect_target = []
        if self.config.target_object_type == TargetObjectType.HOST:
            collect_target = self.handle_host_topo_data()

        if self.config.target_object_type == TargetObjectType.SERVICE:
            collect_target = self.handle_service_topo_data()

        return collect_target

    def init_data(self):
        # 查询采集对象
        self.config = CollectConfigMeta.objects.select_related("deployment_config").get(id=self.config_id)

        # 判断此时任务是否是自动执行
        if self.is_task_result and self.auto_running_tasks:
            self.is_auto = True

    @staticmethod
    def get_host_key(host):
        return "{}|{}".format(host["ip"], host["bk_cloud_id"])

    @property
    def config_info(self):
        config_info = {
            "id": self.config.id,
            "name": self.config.name,
            "bk_biz_id": self.config.bk_biz_id,
            "target_object_type": self.config.target_object_type,
            "target_node_type": self.config.deployment_config.target_node_type,
            "plugin_id": self.config.plugin.plugin_id,
            "label": self.config.label,
            "config_version": self.config.deployment_config.plugin_version.config_version,
            "info_version": self.config.deployment_config.plugin_version.info_version,
            "last_operation": "AUTO_DEPLOYING" if self.is_auto else self.config.last_operation,
        }
        return config_info

    def get_target_status(self):
        if not self.config.deployment_config.subscription_id:
            return []
        instance_status_result = api.node_man.batch_task_result(
            subscription_id=self.config.deployment_config.subscription_id, need_detail=bool(self.is_task_result)
        )
        return instance_status_result

    @staticmethod
    def get_instance_action(instance):
        # 获取step里面的action信息
        for step in instance.get("steps", []):
            if step.get("action") in ["UNINSTALL", "REMOVE_CONFIG"]:
                return "uninstall"
            elif step.get("action") in ["INSTALL"]:
                return "install"
            elif step.get("action") in ["PUSH_CONFIG"]:
                return "update"

        return "install"

    @staticmethod
    def get_instance_log(instance):
        # 获取采集配置下发的阶段性日志
        for step in instance.get("steps", []):
            if step["status"] != CollectStatus.SUCCESS:
                for sub_step in step["target_hosts"][0]["sub_steps"]:
                    if sub_step["status"] != CollectStatus.SUCCESS:
                        return "{}-{}".format(step["node_name"], sub_step["node_name"])
        return ""

    @property
    def host_instance_status(self):
        if self._host_collect_status is not None:
            return self._host_collect_status

        # 获得采集配置和下发主机/实例的状态
        result = self.get_target_status()

        instance_list = []
        for instance in result:
            instance_list.append(
                {
                    "instance_id": instance["instance_id"],
                    "bk_host_id": instance["instance_info"]["host"]["bk_host_id"],
                    "ip": instance["instance_info"]["host"]["bk_host_innerip"],
                    "instance_name": instance["instance_info"]["host"]["bk_host_innerip"]
                    or instance["instance_info"]["host"].get("bk_host_innerip_v6", ""),
                    "bk_host_name": instance["instance_info"]["host"].get("bk_host_name", ""),
                    "bk_cloud_id": int(instance["instance_info"]["host"]["bk_cloud_id"]),
                    "bk_supplier_id": instance["instance_info"]["host"]["bk_supplier_account"],
                    "status": instance["status"],
                    "log": self.get_instance_log(instance),
                    "action": self.get_instance_action(instance),
                    "steps": {step["id"]: step["action"] for step in instance.get("steps", []) if step["action"]},
                    "plugin_version": self.config.deployment_config.plugin_version.version,
                    "task_id": instance.get("task_id"),
                }
            )

        self._host_collect_status = instance_list
        return instance_list

    @property
    def service_instance_status(self):
        if self._service_collect_status is not None:
            return self._service_collect_status

        # 获得采集配置和下发主机/实例的状态
        result = self.get_target_status()

        instance_list = []
        for instance in result:
            instance_list.append(
                {
                    "instance_id": instance["instance_id"],
                    "instance_name": instance["instance_info"]["service"]["name"],
                    "service_instance_id": instance["instance_info"]["service"]["id"],
                    "ip": instance["instance_info"]["host"]["bk_host_innerip"],
                    "bk_host_id": instance["instance_info"]["host"]["bk_host_id"],
                    "bk_cloud_id": int(instance["instance_info"]["host"]["bk_cloud_id"]),
                    "bk_supplier_id": instance["instance_info"]["host"]["bk_supplier_account"],
                    "bk_host_name": instance["instance_info"]["host"].get("bk_host_name", ""),
                    "status": instance["status"],
                    "log": self.get_instance_log(instance),
                    "bk_module_id": instance["instance_info"]["service"]["bk_module_id"],
                    "action": self.get_instance_action(instance),
                    "steps": {step["id"]: step["action"] for step in instance.get("steps", []) if step["action"]},
                    "plugin_version": self.config.deployment_config.plugin_version.version,
                    "task_id": instance.get("task_id"),
                }
            )

        self._service_collect_status = instance_list
        return instance_list

    @property
    def default_status(self):
        # 如果有机器未能在此次下发结果中匹配到相应的状态，则返回此对象
        return {
            "status": CollectStatus.FAILED,
            "log": "",
        }

    def generate_host_status_dict(self):
        """
        生成主机状态信息的字典格式
        """
        return {item["bk_host_id"]: item for item in self.host_instance_status}

    def generate_service_status_dict(self):
        # 生成实例状态信息的字典格式
        service_status_dict = {}
        for item in self.service_instance_status:
            service_status_dict[item["service_instance_id"]] = item
        return service_status_dict

    def handle_host_instance_data(self):
        return self.host_instance_status

    def handle_host_topo_data(self):
        return []

    def handle_service_topo_data(self):
        return []

    def handle_template_service_data(self):
        return []

    def handle_template_host_data(self):
        return []

    def fetch_latest_version_by_config(self):
        """
        根据主配置拿最新子配置版本号
        """
        config_version = self.config.deployment_config.plugin_version.config_version
        latest_info_version = PluginVersionHistory.objects.filter(
            plugin=self.config.plugin, config_version=config_version, stage=PluginVersionHistory.Stage.RELEASE
        ).latest("info_version")
        return latest_info_version


class CollectTargetStatusResource(BaseCollectTargetStatusResource):
    def __init__(self):
        super(CollectTargetStatusResource, self).__init__()
        self.parent_deployment_config = None  # 父配置
        self.diff_label_mapping = OrderedDict(
            [("added", "ADD"), ("removed", "REMOVE"), ("updated", "UPDATE"), ("unchanged", "RETRY")]
        )  # diff标签映射

    def init_data(self):
        super(CollectTargetStatusResource, self).init_data()

        # 如果不是自动执行，并且是查询上一次的任务结果，且该任务类型为复合操作类型（编辑，增删目标，回滚时），获取上一次部署配置
        if not self.is_auto and self.is_task_result and self.config.last_operation in COMPLEX_OPETATION_TYPE:
            try:
                self.parent_deployment_config = DeploymentConfigVersion.objects.get(
                    id=self.config.deployment_config.parent_id
                )
            except DeploymentConfigVersion.DoesNotExist:
                pass

    def get_contained_target(self):
        node_scope = self.config.deployment_config.target_nodes[:]
        # 如果是查询任务执行结果，且上一次操作是编辑/增删目标/回滚，且父配置是拓扑/模板类型，则获取当前配置和父配置的节点之和
        if self.parent_deployment_config and self.parent_deployment_config.target_node_type in [
            TargetNodeType.TOPO,
            TargetNodeType.SET_TEMPLATE,
            TargetNodeType.SERVICE_TEMPLATE,
        ]:
            for node in self.parent_deployment_config.target_nodes:
                if not [x for x in node_scope if topo_tree_tools.get_inst_key(x) == topo_tree_tools.get_inst_key(node)]:
                    node_scope.append(node)

        return node_scope

    @property
    def node_type_changed(self):
        # 和父配置的节点类型进行对比，判断节点类型是否改变
        return (
            self.parent_deployment_config
            and self.parent_deployment_config.target_node_type != self.config.deployment_config.target_node_type
        )

    def classify_instances(self, instance_list):
        # 对采集下发获取到的主机实例进行分类，给前端展示
        if self.is_task_result and self.parent_deployment_config:
            # 如果是查询任务执行结果，并且需要获得特定操作（编辑、增删、回滚）的复合标签结果，则把主机/服务实例放在相应的标签分类里
            classify_result = defaultdict(list)

            # 与父配置的节点差异
            diff_node = self.parent_deployment_config.show_diff(self.config.deployment_config)["nodes"]

            # 根据diff结果，依次把主机/实例放进相应的标签里
            for instance in instance_list:
                for key, label in list(self.diff_label_mapping.items()):
                    if [x for x in diff_node[key] if x.get("bk_host_id") == instance["bk_host_id"]]:
                        classify_result[label].append(instance)
                        break

            # 数据格式处理，获得结果
            contents = []
            for label, instances in list(classify_result.items()):
                contents.append({"is_label": True, "label_name": label, "node_path": _("主机"), "child": instances})

            data = {"config_info": self.config_info, "contents": contents}
        else:
            # 如果是查询主机运行状态，或者只需要获得特定操作（新增，启停，升级）的单一结果，则把所有主机/服务实例放在一个默认标签里
            if instance_list:
                contents = [{"is_label": False, "label_name": "", "node_path": _("主机"), "child": instance_list}]
            else:
                contents = []

            data = {"config_info": self.config_info, "contents": contents}
        return data

    def filter_template_nodes(self, config):
        """
        将配置中属于模板的节点格式化成拓扑节点组成的列表
        """
        if config.target_nodes and config.target_nodes[0].get("bk_obj_id") in [
            TargetNodeType.SERVICE_TEMPLATE,
            TargetNodeType.SET_TEMPLATE,
        ]:
            node_ids = [node["bk_inst_id"] for node in config.target_nodes]
            nodes = resource.commons.get_nodes_by_template(
                dict(
                    bk_biz_id=self.config_info["bk_biz_id"],
                    bk_obj_id=config.target_nodes[0]["bk_obj_id"],
                    bk_inst_ids=node_ids,
                    bk_inst_type=self.config_info["target_object_type"],
                )
            )
            config.target_nodes = nodes

    def classify_nodes(self, node_list):
        # 节点的diff结果进行分类，给前端展示
        if self.is_task_result and self.parent_deployment_config:
            # 如果是查询任务执行结果，并且需要获得特定操作（编辑、增删、回滚）的复合标签结果，则把节点放在相应的标签分类里
            classify_result = defaultdict(list)

            # 如果原配置和本配置中存在集群模板、服务模板，需进行节点提取
            temp_parent_deployment_config = self.parent_deployment_config
            temp_config_deployment_config = self.config.deployment_config

            self.filter_template_nodes(temp_parent_deployment_config)
            self.filter_template_nodes(temp_config_deployment_config)

            # 与父配置的节点差异
            diff_node = temp_parent_deployment_config.show_diff(temp_config_deployment_config)["nodes"]

            # 用于从删除的节点中剔除掉其他节点已经包含的主机
            alive_instance_list = []

            # 根据diff结果，依次把节点放进相应的标签里
            for node in node_list:
                for key, label in list(self.diff_label_mapping.items()):
                    if [
                        x
                        for x in diff_node[key]
                        if x.get("bk_obj_id") == node["bk_obj_id"] and x.get("bk_inst_id") == node["bk_inst_id"]
                    ]:
                        # 如果未变化的节点(unchanged) 下面没有变化的主机，则不对该节点做处理
                        if node["child"] or key != "unchanged":
                            classify_result[label].append(node)
                        # 用于后面剔除掉 删除标签 里的主机
                        if key != "removed":
                            alive_instance_list.extend(node["child"])
                        break

            # 对于一个主机属于多个节点的场景，若删除标签里有该主机，其他标签也存在该主机，则将删除标签里的这一台删除
            if self.config.target_object_type == TargetObjectType.HOST:
                for node in classify_result["REMOVE"]:
                    node["child"] = [instance for instance in node["child"] if instance not in alive_instance_list]

            # 数据格式转换，组成以node为单位的列表
            contents = []
            for label, nodes in list(classify_result.items()):
                for node in nodes:
                    node.update({"is_label": True, "label_name": label})
                    contents.append(node)

            data = {"config_info": self.config_info, "contents": contents}
        else:
            # 如果是查询主机运行状态，或者只需要获得特定操作（新增，启停，升级）的单一结果，则把所有节点放在一个默认标签里
            contents = []
            for node in node_list:
                node.update({"is_label": False, "label_name": ""})
                contents.append(node)
            data = {"config_info": self.config_info, "contents": contents}
        return data

    def classify_auto_deploying_topo(self, target_object_type):
        # 如果是自动执行的情况，根据实例的action进行分类
        action_mapping = {"install": "ADD", "uninstall": "REMOVE", "update": "RETRY"}
        nodes_category = OrderedDict([("ADD", []), ("REMOVE", []), ("RETRY", [])])  # 自动下发中的节点分类

        # 获取topo信息
        topo_tree = resource.cc.topo_tree(self.config.bk_biz_id)
        node_mapping = topo_tree_tools.get_node_mapping(topo_tree)

        # 对于主机的情况，将节点管理的结果转化为主机字典，并获取业务下所有的主机信息
        extra_info = {}
        if target_object_type == TargetObjectType.HOST:
            extra_info["host_status_dict"] = self.generate_host_status_dict()
            extra_info["host_list"] = api.cmdb.get_host_by_topo_node(bk_biz_id=self.config.bk_biz_id)

        # 遍历节点
        for node in self.config.deployment_config.target_nodes:
            inst_key = topo_tree_tools.get_inst_key(node)
            inst = node_mapping.get(inst_key, {})
            if not inst:
                continue
            node_with_host_dict = {
                "default": inst.get("default"),
                "bk_inst_id": node["bk_inst_id"],
                "bk_inst_name": inst.get("bk_inst_name"),
                "bk_obj_id": node["bk_obj_id"],
                "child": [],
            }

            # 节点全路径
            node_link_str = "/".join([node_mapping.get(key).get("bk_inst_name") for key in inst["node_link"]])
            node_with_host_dict["node_path"] = node_link_str or node_with_host_dict["bk_inst_name"]
            # 节点包含的模块
            contained_modules = topo_tree_tools.get_module_by_node(inst)

            instance_category = defaultdict(list)
            if target_object_type == TargetObjectType.HOST:
                # 遍历全业务下的主机，先找到归属该节点下的主机，然后若节点管理下有该主机的运行数据，根据主机的action进行分类
                for host in extra_info["host_list"]:
                    if not set(host.bk_module_ids) & contained_modules:
                        continue
                    status = extra_info["host_status_dict"].get(host.bk_host_id)
                    if status:
                        label = action_mapping[status["action"]]
                        instance_category[label].append(status)
            else:
                # 遍历节点管理的数据，若属于这一节点，则根据实例的action进行分类
                for item in self.service_instance_status:
                    if item["bk_module_id"] not in contained_modules:
                        continue
                    item["instance_name"] = "{}({})".format(item["instance_name"], item["ip"])
                    label = action_mapping[item["action"]]
                    instance_category[label].append(item)

            # 继续将节点进行分类，同一个节点下可能包含不同分类的主机
            for label, nodes in list(nodes_category.items()):
                if instance_category.get(label):
                    nodes.append(dict(node_with_host_dict, child=instance_category.get(label)))

        # 数据格式转换，按照增、删、重试的顺序组成以node为单位的列表
        contents = []
        for label, nodes in list(nodes_category.items()):
            for node in nodes:
                node.update({"is_label": True, "label_name": label})
                contents.append(node)

        return {"config_info": self.config_info, "contents": contents}

    def _handle_host_topo_data(self, target_nodes=None):
        """
        格式化Host Type的node，使其带child
        """
        # 获取节点管理下发状态
        host_status_dict = self.generate_host_status_dict()

        # 遍历节点
        node_list = []
        if target_nodes is None:
            node_scope = self.get_contained_target()
        else:
            node_scope = target_nodes

        # 获取topo信息
        topo_tree = resource.cc.topo_tree(self.config.bk_biz_id)
        node_mapping = topo_tree_tools.get_node_mapping(topo_tree)

        # 所有的主机信息
        host_list = api.cmdb.get_host_by_topo_node(bk_biz_id=self.config.bk_biz_id)

        for node in node_scope:
            inst_key = topo_tree_tools.get_inst_key(node)
            inst = node_mapping.get(inst_key, {})
            if not inst:
                continue
            node_with_host_dict = {
                "default": inst.get("default"),
                "bk_inst_id": node["bk_inst_id"],
                "bk_inst_name": inst.get("bk_inst_name"),
                "bk_obj_id": node["bk_obj_id"],
                "child": [],
            }

            node_link_str = "/".join([node_mapping.get(key).get("bk_inst_name") for key in inst["node_link"]])
            node_with_host_dict["node_path"] = node_link_str or node_with_host_dict["bk_inst_name"]
            # 节点包含的模块
            contained_modules = topo_tree_tools.get_module_by_node(inst)

            # 遍历全业务下的主机，先找到归属该节点下的主机，然后若节点管理下有该主机的运行数据，则填充到child里
            for host in host_list:
                if not set(host.bk_module_ids) & contained_modules:
                    continue

                status = host_status_dict.get(host.bk_host_id)
                if status:
                    node_with_host_dict["child"].append(status)

            node_list.append(node_with_host_dict)

        return node_list

    def _handle_host_instance_data(self):
        return super(CollectTargetStatusResource, self).handle_host_instance_data()

    def handle_host_instance_data(self):
        instance_list = self._handle_host_instance_data()
        if self.is_auto:
            return {
                "config_info": self.config_info,
                "contents": [{"is_label": True, "label_name": "RETRY", "node_path": _("主机"), "child": instance_list}],
            }
        result_data = self.classify_instances(instance_list)

        # 动静切换逻辑
        if self.node_type_changed:
            node_list = self._handle_host_topo_data(target_nodes=self.parent_deployment_config.target_nodes)
            node_data = self.classify_nodes(node_list)
            result_data["contents"].extend(node_data["contents"])

        return result_data

    def handle_host_topo_data(self):
        if self.is_auto:
            return self.classify_auto_deploying_topo(TargetObjectType.HOST)

        result_data = self.handle_template_host_data()

        # 动静切换逻辑
        if self.node_type_changed:
            instance_list = self._handle_host_instance_data()
            instance_data = self.classify_instances(instance_list)
            result_data["contents"].extend(instance_data["contents"])

        return result_data

    def handle_service_topo_data(self):
        if self.is_auto:
            return self.classify_auto_deploying_topo(TargetObjectType.SERVICE)
        return self.handle_template_service_data()

    def handle_template_service_data(self):
        node_list = []
        node_scope = self.get_contained_target()
        nodes = []
        # 获取模板下的节点信息
        for node in node_scope:
            if node["bk_obj_id"] in [TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE]:
                nodes.extend(
                    resource.commons.get_nodes_by_template(
                        dict(
                            bk_biz_id=self.config_info["bk_biz_id"],
                            bk_obj_id=node["bk_obj_id"],
                            bk_inst_ids=[node["bk_inst_id"]],
                            bk_inst_type=self.config_info["target_object_type"],
                        )
                    )
                )
            else:
                nodes.append(node)

        # 获取topo信息
        topo_tree = resource.cc.topo_tree(self.config.bk_biz_id)
        node_mapping = topo_tree_tools.get_node_mapping(topo_tree)

        for node in nodes:
            inst_key = topo_tree_tools.get_inst_key(node)
            inst = node_mapping.get(inst_key, {})
            if not inst:
                continue
            node_with_service_dict = {
                "default": inst.get("default"),
                "bk_inst_id": node["bk_inst_id"],
                "bk_inst_name": inst.get("bk_inst_name"),
                "bk_obj_id": node["bk_obj_id"],
                "child": [],
            }

            node_link_str = "/".join([node_mapping.get(key).get("bk_inst_name") for key in inst["node_link"]])
            node_with_service_dict["node_path"] = node_link_str or node_with_service_dict["bk_inst_name"]

            # 节点包含的模块
            contained_modules = topo_tree_tools.get_module_by_node(inst)

            # 遍历节点管理的数据，若属于这一节点，则填充到该节点的child里

            for item in self.service_instance_status:
                if item["bk_module_id"] not in contained_modules:
                    continue
                item["instance_name"] = "{}({})".format(item["instance_name"], item["ip"])
                node_with_service_dict["child"].append(item)
            node_list.append(node_with_service_dict)

        return self.classify_nodes(node_list)

    def handle_template_host_data(self):
        node_scope = self.get_contained_target()
        nodes = []

        # 获取模板下的节点信息
        for node in node_scope:
            if node["bk_obj_id"] in [TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE]:
                nodes.extend(
                    resource.commons.get_nodes_by_template(
                        dict(
                            bk_biz_id=self.config_info["bk_biz_id"],
                            bk_obj_id=node["bk_obj_id"],
                            bk_inst_ids=[node["bk_inst_id"]],
                            bk_inst_type=self.config_info["target_object_type"],
                        )
                    )
                )
            else:
                nodes.append(node)

        # 处理数据
        node_list = self._handle_host_topo_data(nodes)
        result_data = self.classify_nodes(node_list)
        return result_data


class CollectNodeStatusResource(CollectTargetStatusResource):
    """
    特意为前端提供的接口，对于前端来说获取主机实例的下发状态和获取topo节点的下发状态是2个接口
    """

    pass


class CollectTargetStatusTopoResource(BaseCollectTargetStatusResource):
    """
    获取检查视图左侧数据（ip列表或topo树）的接口
    """

    def __init__(self):
        super(CollectTargetStatusTopoResource, self).__init__()
        self.is_task_result = False
        self.inst_dict = {}
        self.target_nodes_link = {}
        self.target_nodes_key_set = set()
        self._need_nodes = []

    @property
    def need_nodes(self):
        # 将需要的节点转化为集合
        if not self._need_nodes:
            node_set = set()
            for link in list(self.target_nodes_link.values()):
                node_set = node_set | set(link)

            self._need_nodes = node_set

        return self._need_nodes

    def get_module_mapping(self, node, node_link):
        # 判断module是否为采集配置目标节点下的module， 将需要用到的module构建映射关系
        if node.get("bk_obj_id") == "module" and len(set(node_link) & self.target_nodes_key_set) > 0:
            self.inst_dict[node_link[-1]] = node
            self.target_nodes_link[node_link[-1]] = node_link

    def delete_surplus_node(self, node, node_link):
        # 删除多余的节点
        childs = node.get("child", [])
        new_child = []
        for child in childs:
            child_inst_key = topo_tree_tools.get_inst_key(child)
            # 如果child_inst_key为空，则将视为child视为主机或实例保留下来
            if not child_inst_key or child_inst_key in self.need_nodes:
                new_child.append(child)

        node["child"] = new_child

    def nodata_test(self, target_list):
        if not target_list:
            return []

        # 取3个采集周期内的数据，若3个采集周期都无数据则判断为无数据
        period = self.config.deployment_config.params["collector"]["period"]

        filter_dict = {"bk_collect_config_id": str(self.config.id)}

        # 日志关键字无数据判断
        if self.config.plugin.plugin_type == PluginType.LOG or self.config.plugin.plugin_type == PluginType.SNMP_TRAP:
            version = self.config.deployment_config.plugin_version
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

            new_target_list = []
            for target in target_list:
                key = "|".join(str(target[field]) for field in group_by)
                new_target = {"no_data": key not in has_data_targets}
                new_target.update(target)
                new_target_list.append(new_target)

            return new_target_list
        else:
            if self.config.plugin.is_split_measurement:
                db_name = f"{self.config.plugin.plugin_type}_{self.config.plugin.plugin_id}".lower()
                group_result = api.metadata.query_time_series_group(bk_biz_id=0, time_series_group_name=db_name)
                result_tables = [ResultTable.time_series_group_to_result_table(group_result)]
            else:
                # 获取结果表配置
                if self.config.plugin.plugin_type == PluginType.PROCESS:
                    db_name = "process:perf"
                    metric_json = PluginManagerFactory.get_manager(
                        plugin=self.config.plugin.plugin_id, plugin_type=self.config.plugin.plugin_type
                    ).gen_metric_info()

                    metric_json = [table for table in metric_json if table["table_name"] == "perf"]
                else:
                    db_name = "{plugin_type}_{plugin_id}".format(
                        plugin_type=self.config.plugin.plugin_type, plugin_id=self.config.plugin.plugin_id
                    )
                    latest_info_version = self.fetch_latest_version_by_config()
                    metric_json = latest_info_version.info.metric_json
                result_tables = [ResultTable.new_result_table(table) for table in metric_json]
            if period < 60:
                filter_dict["time__gt"] = f"{period * 3 // 60 + 1}m"
            else:
                filter_dict["time__gt"] = f"{period // 60 * 3}m"
            ts_database = TSDataBase(
                db_name=db_name.lower(), result_tables=result_tables, bk_biz_id=self.config.bk_biz_id
            )
            result = ts_database.no_data_test(test_target_list=target_list, filter_dict=filter_dict)
            return result

    @staticmethod
    def batch_request(params):
        """
        执行并发操作
        """
        pool = ThreadPool(2)
        futures = []

        for param in params:
            if param:
                func, args = param[0], param[1:]
                futures.append(pool.apply_async(func, args))
        pool.close()
        pool.join()
        data = []
        for future in futures:
            data.append(future.get())
        return data

    def handle_host_topo_data(self):
        """处理采集目标为主机topo类型的数据"""
        self.target_nodes_key_set = {
            topo_tree_tools.get_inst_key(node) for node in self.config.deployment_config.target_nodes
        }
        # 获取topo树
        topo_tree = resource.cc.topo_tree(self.config.bk_biz_id)
        # 遍历topo树，获取每个节点ID和节点的mapping
        foreach_topo_tree(topo_tree, self.get_module_mapping)
        # 获取业务下的主机
        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=self.config.bk_biz_id)

        target_list = [{"bk_target_ip": host.bk_host_innerip, "bk_target_cloud_id": host.bk_cloud_id} for host in hosts]
        host_normal_data_set = set()

        all_params = [(self.generate_host_status_dict,), (self.nodata_test, target_list)]
        data = self.batch_request(all_params)
        # 获取当前配置采集实例下发状态的mapping
        host_status_dict = data[0]
        for item in data[1]:
            if not item["no_data"]:
                host_normal_data_set.add("{}|{}".format(item["bk_target_ip"], item["bk_target_cloud_id"]))

        # 将主机以及主机下发状态，填充到topo树对应的module下
        for host in hosts:
            # 标识主机所对应的状态
            status = host_status_dict.get(host.bk_host_id)

            if not status:
                status = dict(
                    ip=host.bk_host_innerip,
                    bk_cloud_id=host.bk_cloud_id,
                    bk_host_id=host.bk_host_id,
                    instance_id=host.bk_host_innerip,
                    **self.default_status,
                )

            if status.get("status") == CollectStatus.SUCCESS and self.get_host_key(status) not in host_normal_data_set:
                status.update(status=CollectStatus.NODATA)

            for module_id in host.bk_module_ids:
                inst_key = "module|{}".format(module_id)
                if inst_key in self.inst_dict:
                    host_info = {
                        "bk_host_id": host.bk_host_id,
                        "ip": host.bk_host_innerip,
                        "bk_cloud_id": host.bk_cloud_id,
                        "bk_host_name": host.bk_host_name,
                    }
                    host_info.update(status)
                    # 将主机添加到相应的模块下
                    self.inst_dict[inst_key].setdefault("child", []).append(host_info)

        # 删除topo树中不需要的节点
        foreach_topo_tree(topo_tree, self.delete_surplus_node)
        return topo_tree["child"]

    def _handle_template_data(self):
        templates = self.config.deployment_config.target_nodes
        new_target_nodes = []
        for template in templates:
            nodes = resource.commons.get_nodes_by_template(
                bk_biz_id=self.config_info["bk_biz_id"],
                bk_obj_id=template["bk_obj_id"],
                bk_inst_ids=[template["bk_inst_id"]],
                bk_inst_type=self.config_info["target_object_type"],
            )
            new_target_nodes.extend(
                [{"bk_inst_id": node["bk_inst_id"], "bk_obj_id": node["bk_obj_id"]} for node in nodes]
            )
        self.config.deployment_config.target_nodes = new_target_nodes
        return self.handle_service_topo_data()

    def handle_template_service_data(self):
        return self._handle_template_data()

    def handle_template_host_data(self):
        return self._handle_template_data()

    def handle_service_topo_data(self):
        """处理采集目标为服务topo类型的数据"""
        self.target_nodes_key_set = {
            topo_tree_tools.get_inst_key(node) for node in self.config.deployment_config.target_nodes
        }
        service_instances = self.service_instance_status
        target_list = [
            {"bk_target_service_instance_id": service["service_instance_id"]} for service in service_instances
        ]
        host_normal_data_set = set()
        for item in self.nodata_test(target_list):
            if not item["no_data"]:
                host_normal_data_set.add(int(item["bk_target_service_instance_id"]))
        # 获取实例下发状态
        topo_tree = resource.cc.topo_tree(self.config.bk_biz_id)
        foreach_topo_tree(topo_tree, self.get_module_mapping)
        for instance in service_instances:
            if (
                instance.get("status") == CollectStatus.SUCCESS
                and instance["service_instance_id"] not in host_normal_data_set
            ):
                instance.update(status=CollectStatus.NODATA)

            inst_key = "{}|{}".format("module", instance["bk_module_id"])
            if inst_key in self.inst_dict:
                inst_child = self.inst_dict[inst_key].setdefault("child", [])
                inst_child.append(instance)

        # 删除topo树中不需要的节点
        foreach_topo_tree(topo_tree, self.delete_surplus_node)
        return topo_tree["child"]

    def handle_host_instance_data(self):
        """处理主机实例的数据"""
        host_data = super(CollectTargetStatusTopoResource, self).handle_host_instance_data()
        host_normal_data_set = set()
        target_list = [{"bk_target_ip": host["ip"], "bk_target_cloud_id": host["bk_cloud_id"]} for host in host_data]
        for item in self.nodata_test(target_list):
            if not item["no_data"]:
                host_normal_data_set.add("{}|{}".format(item["bk_target_ip"], item["bk_target_cloud_id"]))

        for data in host_data:
            if data["status"] == CollectStatus.SUCCESS and self.get_host_key(data) not in host_normal_data_set:
                data.update(status=CollectStatus.NODATA)

        return host_data


class CollectRunningStatusResource(CollectTargetStatusResource):
    """
    获取采集配置下发主机的运行状态
    """

    def __init__(self):
        super(CollectRunningStatusResource, self).__init__()
        self.is_task_result = False


class CollectInstanceStatusResource(CollectTargetStatusResource):
    running_status = {OperationType.START: TaskStatus.STARTING, OperationType.STOP: TaskStatus.STOPPING}

    def get_target_status(self):
        res_data = api.node_man.batch_task_result(
            subscription_id=self.config.deployment_config.subscription_id, need_detail=True
        )
        for instance in res_data:
            if instance["status"] in [TaskStatus.DEPLOYING, TaskStatus.RUNNING]:
                instance["status"] = self.running_status.get(self.config.last_operation, TaskStatus.DEPLOYING)
        return res_data

    def classify_instances(self, instance_list):
        if instance_list:
            contents = [{"is_label": False, "label_name": "", "node_path": _("主机"), "child": instance_list}]
        else:
            contents = []

        data = {"config_info": self.config_info, "contents": contents}
        return data

    def classify_nodes(self, node_list):
        contents = []
        for node in node_list:
            node.update({"is_label": False, "label_name": ""})
            contents.append(node)

        data = {"config_info": self.config_info, "contents": contents}
        return data

    def get_contained_target(self):
        node_scope = self.config.deployment_config.target_nodes[:]
        return node_scope


class UpdateConfigStatusResource(Resource):
    """
    更新采集配置的状态，用于后台celery周期任务
    """

    def __init__(self):
        super(UpdateConfigStatusResource, self).__init__()

    def perform_request(self, data):
        logger.info("start celery period task: update collect config status")
        config_biz_list = list(set(CollectConfigMeta.objects.all().values_list("bk_biz_id", flat=True)))

        errors = []
        for bk_biz_id in config_biz_list:
            try:
                resource.collecting.collect_config_list(page=-1, bk_biz_id=bk_biz_id)
            except SubscriptionStatusError as e:
                errors.append(str(e))
            except Exception:
                errors.append("Unknown error for updagte CollectConfigMeta: {}".format(traceback.format_exc()))
        if errors:
            logger.error("Error statistics for periodic task update_config_status: %s", "\n".join(errors))


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
