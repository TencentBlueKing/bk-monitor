"""采集配置 frontend Resource —— 适配 bk-monitor-base 的新实现。

前端展示专用接口，大部分是对 collect_config_detail 返回值的二次加工。
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from django.utils.translation import gettext as _

from bk_monitor_base.domains.metric_plugin.operation import (
    get_metric_plugin_deployment,
)
from bkmonitor.commons.tools import get_host_view_display_fields
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType
from core.drf_resource import resource
from core.drf_resource.base import Resource
from core.errors.collecting import CollectConfigNotExist
from monitor_web.collecting.constant import CollectStatus, OperationType
from monitor_web.commons.cc.utils import foreach_topo_tree
from monitor_web.plugin.constant import PluginType

logger = logging.getLogger(__name__)


# ===========================================================================
# FrontendCollectConfigDetailResource
# ===========================================================================


class FrontendCollectConfigDetailResource(Resource):
    """获取采集配置详细信息，供前端展示用。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        with_target_info = serializers.BooleanField(label="是否返回采集目标配置", default=True)

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        config_detail = resource.collecting.collect_config_detail(id=params["id"], bk_biz_id=params["bk_biz_id"])

        basic_info = {
            "name": config_detail["name"],
            "target_object_type": config_detail["target_object_type"],
            "collect_type": config_detail["collect_type"],
            "plugin_display_name": config_detail["plugin_info"]["plugin_display_name"],
            "plugin_id": config_detail["plugin_info"]["plugin_id"],
            "period": config_detail["params"].get("collector", {}).get("period", 0),
            "bk_biz_id": config_detail["bk_biz_id"],
            "label_info": config_detail["label_info"],
            "create_time": config_detail["create_time"],
            "create_user": config_detail["create_user"],
            "update_time": config_detail["update_time"],
            "update_user": config_detail["update_user"],
        }

        # 运行参数
        runtime_params: list[dict[str, Any]] = []
        config_json = config_detail["plugin_info"].get("config_json", [])
        if config_detail["collect_type"] == PluginType.SNMP:
            for key, item in enumerate(config_json):
                if item.get("auth_json"):
                    config_json.extend(config_json.pop(key).pop("auth_json"))
                    break
        for item in config_json:
            if item.get("mode") != "collector":
                item["mode"] = "plugin"
            runtime_params.append(
                {
                    "name": item.get("description") or item.get("name", ""),
                    "value": config_detail["params"]
                    .get(item.get("mode", ""), {})
                    .get(item.get("name", ""), item.get("default")),
                    "type": item.get("type", "text"),
                }
            )

        # 指标预览
        metric_list: list[dict[str, Any]] = []
        for item in config_detail["plugin_info"].get("metric_json", []):
            field_list = []
            for field in item.get("fields", []):
                field_list.append(
                    {
                        "metric": field.get("monitor_type", ""),
                        "englishName": field.get("name", ""),
                        "aliaName": field.get("description", ""),
                        "type": field.get("type", ""),
                        "unit": field.get("unit", ""),
                    }
                )
            metric_list.append(
                {
                    "id": item.get("table_name", ""),
                    "name": item.get("table_desc", ""),
                    "list": field_list,
                    "table_id": item.get("table_id", ""),
                }
            )

        result: dict[str, Any] = {
            "basic_info": basic_info,
            "runtime_params": runtime_params,
            "metric_list": metric_list,
            "subscription_id": config_detail.get("subscription_id", 0),
            "extend_info": config_detail["params"],
        }

        if params["with_target_info"]:
            result["target_info"] = resource.collecting.frontend_collect_config_target_info(
                id=params["id"],
                bk_biz_id=params["bk_biz_id"],
            )

        return result


# ===========================================================================
# FrontendCollectConfigTargetInfoResource
# ===========================================================================


class FrontendCollectConfigTargetInfoResource(Resource):
    """获取采集配置的采集目标。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        table_data: list[dict[str, Any]] = []
        config_detail = resource.collecting.collect_config_detail(id=params["id"], bk_biz_id=params["bk_biz_id"])

        if config_detail["target_node_type"] == TargetNodeType.INSTANCE:
            for item in config_detail.get("target", []):
                table_data.append(
                    {
                        "display_name": item.get("display_name", ""),
                        "bk_host_id": item.get("bk_host_id"),
                        "ip": item.get("ip", ""),
                        "agent_status": item.get("agent_status", ""),
                        "bk_cloud_name": item.get("bk_cloud_name", ""),
                    }
                )
        elif config_detail["target_node_type"] in [
            TargetNodeType.SET_TEMPLATE,
            TargetNodeType.SERVICE_TEMPLATE,
        ]:
            template_ids = [target["bk_inst_id"] for target in config_detail.get("target", [])]
            nodes = resource.commons.get_nodes_by_template(
                bk_biz_id=config_detail["bk_biz_id"],
                bk_obj_id=config_detail["target_node_type"],
                bk_inst_ids=template_ids,
                bk_inst_type=config_detail["target_object_type"],
            )
            for item in nodes:
                table_data.append(
                    {
                        "bk_inst_name": item.get("bk_inst_name", ""),
                        "count": item.get("count", 0),
                        "labels": item.get("labels", []),
                    }
                )
        elif config_detail["target_node_type"] == TargetNodeType.DYNAMIC_GROUP:
            for item in config_detail.get("target", []):
                table_data.append(
                    {
                        "bk_inst_name": f"动态分组: {item.get('name', '')}",
                        "count": item.get("count", 0),
                    }
                )
        else:
            for item in config_detail.get("target", []):
                table_data.append(
                    {
                        "bk_inst_name": item.get("bk_inst_name", ""),
                        "count": item.get("count", 0),
                        "labels": item.get("labels", []),
                    }
                )

        return {
            "target_node_type": config_detail["target_node_type"],
            "table_data": table_data,
        }


# ===========================================================================
# FrontendTargetStatusTopoResource
# ===========================================================================


class FrontendTargetStatusTopoResource(Resource):
    """获取检查视图页左侧 topo 树。

    依赖 status 模块的 CollectTargetStatusTopoResource，
    status 模块已完成 base 适配。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        only_instance = serializers.BooleanField(label="是否值显示实例列表", default=False)

    @staticmethod
    def handle_node(bk_biz_id: int, node: dict, node_link=None) -> None:
        """拓扑节点处理。"""
        field, alias_field = get_host_view_display_fields(bk_biz_id)
        child = node.pop("child", [])
        if child:
            node["children"] = []
        for item in child:
            if item.get("children") or item.get("bk_host_id"):
                node["children"].append(item)

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
        elif node.get("dynamic_group_name"):
            node["name"] = node.pop("dynamic_group_name")
            node["id"] = node.pop("dynamic_group_id")
        else:
            node["name"] = _("无法识别节点")

    def perform_request(self, params: dict[str, Any]) -> list:
        topo_tree = resource.collecting.collect_target_status_topo(params)

        bk_tenant_id = get_request_tenant_id()
        try:
            deployment, version = get_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                deployment_id=params["id"],
                bk_biz_id=params["bk_biz_id"],
            )
            target_node_type = version.target_scope.node_type if version else ""
        except Exception:
            target_node_type = ""

        handle_node = partial(self.handle_node, params["bk_biz_id"])

        if target_node_type in [TargetNodeType.INSTANCE, TargetNodeType.DYNAMIC_GROUP]:
            for node in topo_tree:
                handle_node(node, None)
            return topo_tree

        foreach_topo_tree(topo_tree, handle_node, order="desc")

        if params["only_instance"]:
            queue = [topo_tree]
            while queue:
                node = queue.pop()
                if "service_instance_id" in node:
                    node["target"] = {"bk_target_service_instance_id": node["service_instance_id"]}
                elif "bk_host_id" in node:
                    node["target"] = {
                        "bk_target_ip": node.get("ip", ""),
                        "bk_target_cloud_id": node.get("bk_cloud_id", 0),
                        "bk_host_id": node["bk_host_id"],
                    }
                queue.extend(node.get("children", []))

        return [topo for topo in topo_tree if topo.get("children")]


# ===========================================================================
# DeploymentConfigDiffResource
# ===========================================================================


class DeploymentConfigDiffResource(Resource):
    """获取采集配置的部署配置差异。

    [ISSUE] base 不提供版本差异比对（show_diff）能力。
    当前实现需要：
    1. base 提供历史版本列表查询 API
    2. 或者在 SaaS 层实现 diff 计算
    暂时回退到旧 ORM 实现。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict:
        # [ISSUE] base 不提供 show_diff / 版本差异比对能力
        # 需要 base 补齐 list_metric_plugin_deployment_versions() + diff 能力
        # 暂时回退到旧 ORM
        from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion

        try:
            collect_config = CollectConfigMeta.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"],
                id=validated_request_data["id"],
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": validated_request_data["id"]})

        if collect_config.last_operation == OperationType.ROLLBACK:
            last_version = DeploymentConfigVersion.objects.filter(parent_id=collect_config.deployment_config.id).last()
        else:
            last_version = collect_config.deployment_config.last_version

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


# ===========================================================================
# GetCollectVariablesResource
# ===========================================================================


class GetCollectVariablesResource(Resource):
    """获取采集配置可用的模板变量列表（纯静态数据）。"""

    def perform_request(self, validated_request_data: dict) -> list[dict[str, str]]:
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
