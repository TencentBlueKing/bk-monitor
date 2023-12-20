# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from functools import partial

from django.utils.translation import ugettext as _

from bkmonitor.commons.tools import get_host_view_display_fields
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType
from core.drf_resource import resource
from core.drf_resource.base import Resource
from core.errors.collecting import CollectConfigNotExist
from monitor_web.collecting.constant import CollectStatus, OperationType
from monitor_web.commons.cc.utils import foreach_topo_tree
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.plugin.constant import PluginType


class FrontendCollectConfigDetailResource(Resource):
    """
    获取采集配置详细信息，供前端展示用
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置ID")

    def perform_request(self, params):
        config_detail = resource.collecting.collect_config_detail(id=params["id"])

        # 基本信息
        basic_info = {
            "name": config_detail["name"],
            "target_object_type": config_detail["target_object_type"],  # SERVICE, HOST
            "collect_type": config_detail["collect_type"],
            "plugin_display_name": config_detail["plugin_info"]["plugin_display_name"],
            "plugin_id": config_detail["plugin_info"]["plugin_id"],
            "period": config_detail["params"]["collector"]["period"],
            "bk_biz_id": config_detail["bk_biz_id"],
            "label_info": config_detail["label_info"],
            "create_time": config_detail["create_time"],
            "create_user": config_detail["create_user"],
            "update_time": config_detail["update_time"],
            "update_user": config_detail["update_user"],
        }

        # 运行参数
        runtime_params = []
        config_json = config_detail["plugin_info"]["config_json"]
        if config_detail["collect_type"] == PluginType.SNMP:
            for key, item in enumerate(config_json):
                if item.get("auth_json"):
                    config_json.extend(config_json.pop(key).pop("auth_json"))
                    break
        for item in config_json:
            if item["mode"] != "collector":
                item["mode"] = "plugin"
            runtime_params.append(
                {
                    "name": item["description"] or item["name"],
                    "value": config_detail["params"][item["mode"]].get(item["name"], item["default"]),
                    "type": item["type"],
                }
            )

        # 指标预览
        metric_list = []
        for item in config_detail["plugin_info"]["metric_json"]:
            field_list = []
            for field in item["fields"]:
                field_list.append(
                    {
                        "metric": field["monitor_type"],
                        "englishName": field["name"],
                        "aliaName": field["description"],
                        "type": field["type"],
                        "unit": field["unit"],
                    }
                )
            metric_list.append(
                {
                    "id": item["table_name"],
                    "name": item["table_desc"],
                    "list": field_list,
                    "table_id": item["table_id"],
                }
            )

        # 采集目标
        table_data = []
        if config_detail["target_node_type"] == TargetNodeType.INSTANCE:
            for item in config_detail["target"]:
                table_data.append(
                    {
                        "display_name": item["display_name"],
                        "bk_host_id": item["bk_host_id"],
                        "ip": item["ip"],
                        "agent_status": item["agent_status"],
                        "bk_cloud_name": item["bk_cloud_name"],
                    }
                )
        elif config_detail["target_node_type"] in [TargetNodeType.SET_TEMPLATE, TargetNodeType.SERVICE_TEMPLATE]:
            template_ids = [target["bk_inst_id"] for target in config_detail["target"]]
            nodes = resource.commons.get_nodes_by_template(
                bk_biz_id=config_detail["bk_biz_id"],
                bk_obj_id=config_detail["target_node_type"],
                bk_inst_ids=template_ids,
                bk_inst_type=config_detail["target_object_type"],
            )
            for item in nodes:
                table_data.append(
                    {"bk_inst_name": item["bk_inst_name"], "count": item["count"], "labels": item["labels"]}
                )
        else:
            for item in config_detail["target"]:
                table_data.append(
                    {"bk_inst_name": item["bk_inst_name"], "count": item["count"], "labels": item["labels"]}
                )

        target_info = {"target_node_type": config_detail["target_node_type"], "table_data": table_data}

        result = {
            "basic_info": basic_info,
            "runtime_params": runtime_params,
            "metric_list": metric_list,
            "target_info": target_info,
            "subscription_id": config_detail["subscription_id"],
            "extend_info": config_detail["params"],
        }
        return result


class FrontendTargetStatusTopoResource(Resource):
    """
    获取检查视图页左侧topo树
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        only_instance = serializers.BooleanField(label="是否值显示实例列表", default=False)

    @staticmethod
    def handle_node(bk_biz_id: int, node, node_link=None):
        """
        拓扑节点处理
        """
        field, alias_field = get_host_view_display_fields(bk_biz_id)
        # 子节点处理
        child = node.pop("child", [])
        if child:
            node["children"] = []
        for item in child:
            # 去除不包含实例的节点
            if item.get("children") or item.get("bk_host_id"):
                node["children"].append(item)

        # 补充字段
        if node.get("service_instance_id"):
            node["name"] = node.get("instance_name")
            node["status"] = node.get("status", CollectStatus.FAILED)
            node["id"] = node["service_instance_id"]
        elif node.get("bk_host_id"):
            node["name"] = node.get("instance_name")
            node["alias_name"] = node.get(alias_field, "")
            node["id"] = str(node["bk_host_id"])
            node["status"] = node.get("status", CollectStatus.FAILED)
        elif node.get("bk_inst_name"):
            node["name"] = node["bk_inst_name"]
            node["id"] = f"{node['bk_obj_id']}|{node['bk_inst_id']}"
        else:
            node["name"] = _("无法识别节点")

    def perform_request(self, params):
        topo_tree = resource.collecting.collect_target_status_topo(params)
        config = CollectConfigMeta.objects.select_related("deployment_config").get(id=params["id"])

        handle_node = partial(self.handle_node, params["bk_biz_id"])

        # 实例处理
        if config.deployment_config.target_node_type == TargetNodeType.INSTANCE:
            for node in topo_tree:
                handle_node(node, None)
            return topo_tree

        # 动态拓扑处理
        foreach_topo_tree(topo_tree, handle_node, order="desc")

        # 补充目标字段
        if params["only_instance"]:
            queue = [topo_tree]
            while queue:
                node = queue.pop()
                if "service_instance_id" in node:
                    node["target"] = {"bk_target_service_instance_id": node["service_instance_id"]}
                elif "bk_host_id" in node:
                    node["target"] = {
                        "bk_target_ip": node["ip"],
                        "bk_target_cloud_id": node["bk_cloud_id"],
                        "bk_host_id": node["bk_host_id"],
                    }
                queue.extend(node.get("children", []))

        return [topo for topo in topo_tree if topo.get("children")]


class DeploymentConfigDiffResource(Resource):
    """
    用于列表页重新进入执行中的采集配置
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, validated_request_data):
        try:
            collect_config = CollectConfigMeta.objects.get(id=validated_request_data["id"])
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": validated_request_data["id"]})

        # 获得采集配置的上一份部署配置
        if collect_config.last_operation == OperationType.ROLLBACK:
            last_version = DeploymentConfigVersion.objects.filter(parent_id=collect_config.deployment_config.id).last()
        else:
            last_version = collect_config.deployment_config.last_version

        # 返回两份配置的diff_node差异信息
        if last_version:
            diff_node = last_version.show_diff(collect_config.deployment_config)["nodes"]
        else:
            diff_node = {
                "is_modified": True,
                "added": collect_config.deployment_config.target_nodes,
                "updated": [],
                "removed": [],
                "unchanged": [],
            }
        return diff_node


class GetCollectVariablesResource(Resource):
    def perform_request(self, validated_request_data):
        data = [
            ["{{ target.host.bk_host_innerip }}", _("主机内网IP"), "127.0.0.1"],
            ["{{ target.host.bk_cloud_id }}", _("主机云区域ID"), "0"],
            ["{{ target.host.bk_cloud_name }}", _("主机云区域名称"), "default area"],
            ["{{ target.host.bk_host_id }}", _("主机ID"), "1"],
            ["{{ target.host.operator }}", _("主机负责人"), "user1,user2"],
            ["{{ target.host.bk_bak_operator }}", _("主机备份负责人"), "user1,user2"],
            ["{{ target.host.bk_host_name }}", _("主机名"), "VM_centos"],
            ["{{ target.host.bk_isp_name }}", _("ISP名称"), _("联通")],
            ["{{ target.host.bk_os_name }}", _("操作系统名称"), "linux centos"],
            ["{{ target.host.bk_os_version }}", _("操作系统版本"), "7.4.1700"],
            ["{{ target.service.id }}", _("服务实例ID"), "1"],
            ["{{ target.service.name }}", _("服务实例名称"), "test"],
            ["{{ target.service.bk_module_id }}", _("模块ID"), "1"],
            ["{{ target.service.bk_host_id }}", _("主机ID"), "1"],
            ["{{ target.service.service_category_id }}", _("服务分类ID"), "1"],
            ['{{ target.service.labels["label_name"] }}', _("标签"), "test"],
            ['{{ target.process["process_name"].bk_process_id }}', _("进程ID"), "1"],
            ['{{ target.process["process_name"].bk_process_name }}', _("进程别名"), "1"],
            ['{{ target.process["process_name"].bk_func_name }}', _("进程名称"), "1"],
            ['{{ target.process["process_name"].bind_info[index].port }}', _("进程端口"), "80,81-85"],
            ['{{ target.process["process_name"].bind_info[index].ip }}', _("绑定IP"), "127.0.0.1"],
            ['{{ target.process["process_name"].bk_func_id }}', _("功能ID"), "123"],
            ['{{ target.process["process_name"].user }}', _("启动用户"), "root"],
            ['{{ target.process["process_name"].work_path }}', _("工作路径"), "/data/bkee"],
            ['{{ target.process["process_name"].proc_num }}', _("进程数量"), "4"],
            ['{{ target.process["process_name"].pid_file }}', _("PID文件路径"), "/data/bkee/a.pid"],
            ['{{ target.process["process_name"].auto_start }}', _("自动启动"), "false"],
        ]
        return [{"name": record[0], "description": record[1], "example": record[2]} for record in data]
