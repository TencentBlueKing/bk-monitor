"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.utils.common_utils import host_key, safe_int
from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource import api, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from bk_monitor_base.domains.uptime_check import operation as uptime_check_operation
from bk_monitor_base.domains.uptime_check.constants import BEAT_STATUS
from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskProtocol, UptimeCheckTaskStatus
from monitor_web.uptime_check.serializers import (
    UptimeCheckGroupSerializer,
    UptimeCheckNodeSerializer,
    UptimeCheckTaskSerializer,
)
from utils.business import get_business_id_list

logger = logging.getLogger(__name__)


class TaskAdapter:
    """将字典数据适配成资源层需要的对象格式"""

    def __init__(self, task_dict: dict):
        self._task_dict = task_dict
        self.id = task_dict.get("id")
        self.protocol = task_dict.get("protocol")
        self.config = task_dict.get("config", {})
        for key, value in task_dict.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def get_period(self) -> int:
        """获取任务周期（秒）"""
        return self.config.get("period", 60)

    @property
    def __dict__(self):
        """返回字典表示"""
        return self._task_dict


class PermissionMixin:
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_SYNTHETIC])]
        return [BusinessActionPermission([ActionEnum.MANAGE_SYNTHETIC])]


class FrontPageDataViewSet(ResourceViewSet):
    """
    监控首页 服务拨测曲线数据获取
    """

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]

    resource_routes = [ResourceRoute("POST", resource.uptime_check.front_page_data)]


class GetHttpHeadersViewSet(PermissionMixin, ResourceViewSet):
    """
    获取HTTP任务允许设置的Header
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.get_http_headers)]


class GetStrategyStatusViewSet(PermissionMixin, ResourceViewSet):
    """
    获取启用/停用策略数
    """

    resource_routes = [ResourceRoute("POST", resource.uptime_check.get_strategy_status)]


class TaskDetailViewSet(PermissionMixin, ResourceViewSet):
    """
    根据任务id 获取可用率曲线或响应时长曲线
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.task_detail)]


class TaskGraphAndMapViewSet(PermissionMixin, ResourceViewSet):
    """
    根据任务id 获取可用率曲线和响应时长曲线与地区信息
    """

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_SYNTHETIC])]

    resource_routes = [ResourceRoute("POST", resource.uptime_check.task_graph_and_map)]


def get_capacity(targets_count):
    if targets_count / settings.UPTIMECHECK_NODE_TARGET_LIMITS > 0.6:
        return "enough"
    elif targets_count / settings.UPTIMECHECK_NODE_TARGET_LIMITS < 0.3:
        return "unavailable"
    else:
        return "normal"


class UptimeCheckNodeViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测节点 ViewSet"""

    serializer_class = UptimeCheckNodeSerializer

    def retrieve(self, request, pk: int | None = None):
        """获取节点详情"""
        node_data = uptime_check_operation.get_node_detail(int(pk))
        bk_host_id = uptime_check_operation.set_node_host_id(int(pk))
        node_data["bk_host_id"] = bk_host_id
        serializer = UptimeCheckNodeSerializer(data=node_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    @staticmethod
    def get_beat_version(bk_host_ids):
        all_beat_version = {}
        all_plugin = api.node_man.plugin_search(
            {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
        )["list"]
        for plugin in all_plugin:
            beat_plugin = list(filter(lambda x: x["name"] == "bkmonitorbeat", plugin["plugin_status"]))
            # 过滤后，只剩下bkmonitorbeat插件
            if beat_plugin:
                bkmonitorbeat = beat_plugin[0]
                # 兼容ipv4无bk_host_id的旧节点配置
                if plugin["inner_ip"]:
                    all_beat_version[host_key(ip=plugin["inner_ip"], bk_cloud_id=plugin["bk_cloud_id"])] = (
                        bkmonitorbeat.get("version", "")
                    )
                all_beat_version[plugin["bk_host_id"]] = bkmonitorbeat.get("version", "")
            else:
                logger.warning(
                    "bkmonitorbeat plugin(host_id:{}, ip:{}, ipv6:{}, cloud_id:{}) doesn't exist. "
                    "all plugin status info:{}".format(
                        plugin["bk_host_id"],
                        plugin["inner_ip"],
                        plugin["inner_ipv6"],
                        plugin["bk_cloud_id"],
                        plugin["plugin_status"],
                    )
                )
        return all_beat_version

    def list(self, request, *args, **kwargs):
        """
        重写list,简化节点部分数据并添加关联任务数等数据
        """

        def get_by_node(node: dict, data_map: dict, default=None):
            key = node.get("bk_host_id")
            if not key:
                key = host_key(ip=node["ip"], bk_cloud_id=node["plat_id"])
            if key not in data_map:
                return default
            return data_map[key]

        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = request.GET.get("bk_biz_id")

        # 使用business_id_list过滤掉业务已经不存在的公共节点
        id_list = get_business_id_list()

        # 获取用于展示的节点列表
        nodes = uptime_check_operation.list_nodes_for_display(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=int(bk_biz_id) if bk_biz_id else None,
            valid_bk_biz_id_list=id_list,
        )

        # 将节点解析成cmdb主机，存放在以host_id 和 ip+cloud_id 为key 的 字典里
        node_to_host = resource.uptime_check.get_node_host_dict(bk_tenant_id=bk_tenant_id, nodes=nodes)

        result = []
        bk_host_ids = {host.bk_host_id for host in node_to_host.values()}
        hosts = [node_to_host[host_id] for host_id in bk_host_ids]
        all_beat_version = {}
        if bk_host_ids:
            # 去节点管理拿拨测采集器的版本信息
            all_beat_version = self.get_beat_version(bk_host_ids)

        # 获取采集器相关信息
        all_node_status = {}
        try:
            all_node_status = (
                resource.uptime_check.uptime_check_beat.return_with_dict(bk_biz_id=bk_biz_id, hosts=hosts)
                if bk_biz_id
                else resource.uptime_check.uptime_check_beat.return_with_dict(hosts=hosts)
            )
        except Exception as e:
            logger.exception(f"Failed to get uptime check node status: {e}")

        for node in nodes:
            task_num = node.get("task_count", 0)
            host_instance = get_by_node(node, node_to_host)
            beat_version = ""
            if not host_instance:
                # host_id/ip失效，无法找到对应主机实例，拨测节点标记状态为失效
                node_status = {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["INVALID"]}
                display_name = node["ip"]
            else:
                display_name = host_instance.display_name
                # 未上报数据，默认给不可用状态
                node_status = get_by_node(
                    node, all_node_status, {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["DOWN"]}
                )
                beat_version = get_by_node(node, all_beat_version, beat_version)

            # 添加权限信息
            result.append(
                {
                    "id": node["id"],
                    "bk_biz_id": node["bk_biz_id"],
                    "name": node["name"],
                    "ip": display_name,
                    "bk_host_id": node["bk_host_id"],
                    "plat_id": node["plat_id"],
                    "ip_type": node["ip_type"],
                    "country": node["location"].get("country"),
                    "province": node["location"].get("city"),
                    "carrieroperator": node["carrieroperator"],
                    "task_num": task_num,
                    "is_common": node["is_common"],
                    "gse_status": node_status.get("gse_status", BEAT_STATUS["RUNNING"]),
                    # TODO: 多租户环境下暂时跳过心跳检查
                    "status": node_status.get("status", "0")
                    if not settings.ENABLE_MULTI_TENANT_MODE
                    else BEAT_STATUS["RUNNING"],
                    "version": node_status.get("version", "") if node_status.get("version", "") else beat_version,
                }
            )
        return Response(result)

    @action(methods=["GET"], detail=False)
    def count(self, request, *args, **kwargs):
        """获取节点数量"""
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = request.GET.get("bk_biz_id")
        id_list = get_business_id_list()

        nodes = uptime_check_operation.list_nodes_for_display(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=int(bk_biz_id) if bk_biz_id else None,
            valid_bk_biz_id_list=id_list,
        )
        return Response({"count": len(nodes)})

    @action(methods=["GET"], detail=False)
    def is_exist(self, request, *args, **kwargs):
        """
        用于给前端判断输入的IP是否属于已建节点
        """
        ip = request.GET.get("ip")
        bk_biz_id = request.GET.get("bk_biz_id")
        bk_tenant_id = get_request_tenant_id()
        is_exist = uptime_check_operation.check_node_exists(bk_tenant_id, int(bk_biz_id), ip=ip)
        return Response({"is_exist": is_exist})

    @action(methods=["GET"], detail=False)
    def fix_name_conflict(self, request, *args, **kwargs):
        """
        节点重名时自动补全一个名称，如广东移动补全为广东移动2
        """
        # filter() 时, 在mysql里，'name=' 会忽略结尾空格，而'name__startswith'不会。故在进行校验时，将结尾空格去掉。
        name = request.GET.get("name", "").rstrip()
        bk_biz_id = request.GET.get("bk_biz_id")
        node_id = request.GET.get("id")
        bk_tenant_id = get_request_tenant_id()

        exclude_id = int(node_id) if node_id else None
        is_exists = uptime_check_operation.check_node_exists(
            bk_tenant_id, int(bk_biz_id), name=name, exclude_id=exclude_id
        )

        if is_exists:
            all_names = uptime_check_operation.list_node_names_starting_with(bk_tenant_id, name, int(bk_biz_id))
            num_suffix_list = []
            for item_name in all_names:
                num_suffix_list.append(safe_int(item_name.strip(name)))
            max_num = max(num_suffix_list) if num_suffix_list else 0
            if max_num:
                name += str(max_num + 1)
            else:
                name += "2"
        return Response({"name": name})


class UptimeCheckTaskViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测任务 ViewSet

    改造后完全通过 operation 层操作，不直接暴露 Model。
    """

    serializer_class = UptimeCheckTaskSerializer

    def retrieve(self, request, pk=None):
        """
        旧版动态下发配置转换
        """
        data = uptime_check_operation.get_task_detail(int(pk))
        config = data["config"]
        protocol = data["protocol"]
        if config.get("urls") and protocol == UptimeCheckTaskProtocol.HTTP.value:
            url = config.pop("urls", None)
            config["url_list"] = [url]
        if config.get("hosts"):
            config["url_list"] = []
            hosts = config.pop("hosts", [])
            if hosts[0].get("bk_inst_id"):
                config["node_list"] = hosts
                config["ip_list"] = []
            if hosts[0].get("ip"):
                ips = [host["ip"] for host in hosts if host.get("ip")]
                host_instances = api.cmdb.get_host_without_biz(bk_tenant_id=get_request_tenant_id(), ips=ips)["hosts"]
                config["node_list"] = [{"bk_host_id": h.bk_host_id} for h in host_instances]
                host_instance_ips = [h.ip for h in host_instances]
                config["ip_list"] = [host["ip"] for host in hosts if host["ip"] not in host_instance_ips]
        return Response(data)

    def get_permissions(self):
        if self.action == "list":
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS, ActionEnum.VIEW_SYNTHETIC])]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        """
        重写list，传入get_groups时整合拨测任务组卡片页数据，避免数据库重复查询
        """
        group_id = request.query_params.get("group_id")
        bk_biz_id = int(request.query_params.get("bk_biz_id", 0))

        # 如果传入plain参数，则返回简单数据
        if request.query_params.get("plain", False):
            task_id = request.query_params.get("id")
            tasks = uptime_check_operation.list_tasks_simple(
                bk_biz_id=bk_biz_id if bk_biz_id else None,
                group_id=int(group_id) if group_id else None,
                task_id=int(task_id) if task_id else None,
                plain=True if task_id else False,
            )
            if task_id:
                return Response(tasks)
            else:
                return Response([{"id": t["id"], "name": t["name"], "bk_biz_id": t["bk_biz_id"]} for t in tasks])

        # 使用 operation 层直接获取任务列表，避免 QuerySet 依赖
        tasks = uptime_check_operation.list_tasks_simple(
            bk_biz_id=bk_biz_id if bk_biz_id else None,
            group_id=int(group_id) if group_id else None,
            plain=False,
        )

        # 适配成对象格式(兼容resource调用)
        task_adapters = [TaskAdapter(task) for task in tasks]

        get_groups = request.query_params.get("get_groups", False)
        get_available = request.query_params.get("get_available") == "true"
        get_task_duration = request.query_params.get("get_task_duration") == "true"
        task_data = resource.uptime_check.uptime_check_task_list(
            task_data=task_adapters,
            bk_biz_id=bk_biz_id,
            get_available=get_available,
            get_task_duration=get_task_duration,
        )

        # 如果节点对应的业务id已经不存在了，则该任务状态强制显示为START_FAILED，用于给用户提示
        biz_id_list = get_business_id_list()
        for data in task_data:
            for node in data["nodes"]:
                if node["bk_biz_id"] not in biz_id_list:
                    data["status"] = UptimeCheckTaskStatus.START_FAILED.value

        if get_groups:
            result = resource.uptime_check.uptime_check_card(bk_biz_id=bk_biz_id, task_data=task_data)
        else:
            result = task_data
        return Response(result)

    @action(methods=["GET"], detail=False)
    def count(self, request, *args, **kwargs):
        """获取任务数量"""
        group_id = request.query_params.get("group_id")
        bk_biz_id = int(request.query_params.get("bk_biz_id", 0))

        # 使用 operation 层获取数量
        tasks = uptime_check_operation.list_tasks_simple(
            bk_biz_id=bk_biz_id if bk_biz_id else None,
            group_id=int(group_id) if group_id else None,
            plain=False,
        )
        return Response({"count": len(tasks)})

    @action(methods=["POST"], detail=False)
    def test(self, request, *args, **kwargs):
        """
        测试任务
        下发测试配置，采集器只执行一次数据采集，直接返回采集结果，不经过计算平台
        """
        bk_biz_id = request.data.get("bk_biz_id")
        config = request.data.get("config")
        protocol = request.data.get("protocol")
        node_id_list = request.data.get("node_id_list")
        if not settings.ENABLE_UPTIMECHECK_TEST:
            return Response(_("未开启拨测联通性测试，保存任务中..."))
        return Response(
            resource.uptime_check.test_task(
                {"bk_biz_id": bk_biz_id, "config": config, "protocol": protocol, "node_id_list": node_id_list}
            )
        )

    @action(methods=["POST"], detail=True)
    def deploy(self, request, pk=None):
        """
        正式创建任务
        下发正式配置，采集器托管任务，将采集结果上报至计算平台
        """
        task_id = int(pk)
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = uptime_check_operation.get_task_bk_biz_id(task_id)
        result = uptime_check_operation.deploy_uptime_check_task(bk_tenant_id, bk_biz_id, task_id)
        return Response(result)

    @action(methods=["POST"], detail=True)
    def clone(self, request, pk=None):
        """
        克隆任务
        """
        task_id = int(pk)
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = uptime_check_operation.get_task_bk_biz_id(task_id)
        operator = request.user.username
        new_task_id = uptime_check_operation.clone_uptime_check_task(bk_tenant_id, bk_biz_id, task_id, operator)
        return Response({"id": new_task_id})

    @action(methods=["POST"], detail=True)
    def change_status(self, request, pk=None):
        """
        更改任务状态
        """
        task_id = int(pk)
        task_status = request.data.get("status", "")
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = uptime_check_operation.get_task_bk_biz_id(task_id)
        operator = request.user.username

        # status: "running" -> start, "stoped" -> stop
        action = "start" if task_status == UptimeCheckTaskStatus.RUNNING.value else "stop"
        uptime_check_operation.switch_uptime_check_task(bk_tenant_id, bk_biz_id, task_id, action, operator)

        # 重新获取更新后的状态
        updated_status = uptime_check_operation.get_task_status(task_id)
        return Response(data={"id": task_id, "status": updated_status})

    @action(methods=["GET"], detail=True)
    def running_status(self, request, pk=None):
        """
        创建拨测任务时，查询部署任务是否成功，失败则返回节点管理中部署失败错误日志
        :return:
        """
        task_id = int(pk)
        task_status = uptime_check_operation.get_task_status(task_id)
        if task_status == UptimeCheckTaskStatus.START_FAILED.value:
            error_log = uptime_check_operation.list_task_collector_error_logs(task_id)
            return Response(data={"status": UptimeCheckTaskStatus.START_FAILED.value, "error_log": error_log})
        else:
            return Response(data={"status": task_status})


class UptimeCheckGroupViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测分组 ViewSet

    改造后完全通过 operation 层操作，不直接暴露 Model。
    """

    serializer_class = UptimeCheckGroupSerializer

    def retrieve(self, request, pk=None):
        """
        简化返回数据
        """
        data = uptime_check_operation.get_group_detail(int(pk))
        result = {
            "id": data["id"],
            "name": data["name"],
            "bk_biz_id": data["bk_biz_id"],
            "logo": data["logo"],
            "task_list": data["tasks"],
        }
        return Response(result)

    def list(self, request, *args, **kwargs):
        """获取分组列表"""
        bk_biz_id = int(request.query_params.get("bk_biz_id", 0))
        bk_tenant_id = get_request_tenant_id()

        if bk_biz_id:
            result = uptime_check_operation.list_uptime_check_groups_paged(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
            )
        else:
            # 没有指定业务时，使用基础查询
            result = uptime_check_operation.list_uptime_check_groups_paged(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=0,
                include_global=True,
            )
        return Response(result["data"])

    @action(methods=["POST"], detail=True)
    def add_task(self, request, pk=None):
        """
        拨测任务拖拽进入任务组
        """
        group_id = int(pk)
        task_id = request.data.get("task_id")

        if uptime_check_operation.check_task_in_group(group_id, task_id):
            group_name = uptime_check_operation.get_group_name(group_id)
            task_name = uptime_check_operation.get_task_name(task_id)
            return Response({"msg": _("拨测分组({})已存在任务({})".format(group_name, task_name))})

        uptime_check_operation.add_task_to_group(group_id, task_id)
        group_name = uptime_check_operation.get_group_name(group_id)
        task_name = uptime_check_operation.get_task_name(task_id)
        return Response({"msg": _("拨测分组({})添加任务({})成功".format(group_name, task_name))})

    @action(methods=["post"], detail=True)
    def remove_task(self, request, pk=None):
        """拨测任务组移除拨测任务"""
        group_id = int(pk)
        task_id = request.data.get("task_id")

        if not uptime_check_operation.check_task_in_group(group_id, task_id):
            group_name = uptime_check_operation.get_group_name(group_id)
            task_name = uptime_check_operation.get_task_name(task_id)
            return Response({"msg": _("拨测分组({})不存在任务({})".format(group_name, task_name))})

        uptime_check_operation.remove_task_from_group(group_id, task_id)
        group_name = uptime_check_operation.get_group_name(group_id)
        task_name = uptime_check_operation.get_task_name(task_id)
        return Response({"msg": _("拨测分组({})移除任务({})成功".format(group_name, task_name))})


class ExportUptimeCheckConfViewSet(PermissionMixin, ResourceViewSet):
    """
    导出拨测任务配置接口
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.export_uptime_check_conf)]


class ExportUptimeCheckNodeConfViewSet(PermissionMixin, ResourceViewSet):
    """
    导出拨测节点配置接口
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.export_uptime_check_node_conf)]


class ImportUptimeCheckViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.uptime_check.file_parse, endpoint="parse"),
        ResourceRoute("POST", resource.uptime_check.file_import_uptime_check),
    ]


class SelectUptimeCheckNodeViewSet(PermissionMixin, ResourceViewSet):
    """
    节点选择器
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.select_uptime_check_node)]


class SelectCarrierOperatorViewSet(PermissionMixin, ResourceViewSet):
    """
    节点选择器
    """

    resource_routes = [ResourceRoute("GET", resource.uptime_check.select_carrier_operator)]


class UptimeCheckTargetDetailViewSet(PermissionMixin, ResourceViewSet):
    """
    获取目标详情
    """

    resource_routes = [ResourceRoute("POST", resource.uptime_check.uptime_check_target_detail)]
