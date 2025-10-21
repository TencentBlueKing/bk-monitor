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
from django.db.models import Prefetch
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
from monitor_api.filtersets import get_filterset
from monitor_web.models.uptime_check import (
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckTask,
    UptimeCheckTaskCollectorLog,
)
from monitor_web.uptime_check.constants import BEAT_STATUS
from monitor_web.uptime_check.serializers import (
    UptimeCheckGroupSerializer,
    UptimeCheckNodeSerializer,
    UptimeCheckTaskSerializer,
)
from utils.business import get_business_id_list

logger = logging.getLogger(__name__)


class CountModelMixin:
    """
    Count a queryset.
    """

    @action(methods=["GET"], detail=False)
    def count(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        content = {"count": queryset.count()}
        return Response(content)


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


class UptimeCheckNodeViewSet(PermissionMixin, viewsets.ModelViewSet, CountModelMixin):
    _, filterset_class = get_filterset(UptimeCheckNode)
    serializer_class = UptimeCheckNodeSerializer

    def get_queryset(self):
        return UptimeCheckNode.objects.filter(bk_tenant_id=get_request_tenant_id())

    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs).data
        node_instance = self.get_object()
        bk_host_id = node_instance.set_host_id()
        data["bk_host_id"] = bk_host_id
        return Response(data)

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

        def get_by_node(node, data_map, default=None):
            if isinstance(node, UptimeCheckNode):
                node = node.__dict__
            key = node["bk_host_id"]
            if not key:
                key = host_key(ip=node["ip"], bk_cloud_id=node["plat_id"])
            if key not in data_map:
                return default
            return data_map[key]

        # 如用户传入业务，同时还应该加上通用节点
        id_list = get_business_id_list()
        # 使用business_id_list过滤掉业务已经不存在的公共节点
        common_nodes = self.get_queryset().filter(is_common=True, bk_biz_id__in=id_list)
        biz_nodes = self.get_queryset().filter(is_common=False).values("biz_scope", "id")

        # 指定业务范围可见节点过滤
        bk_biz_id = request.GET.get("bk_biz_id")
        biz_node_ids = []
        for biz_node in biz_nodes:
            if bk_biz_id in biz_node["biz_scope"]:
                biz_node_ids.append(biz_node["id"])
        queryset = (
            (self.get_queryset().filter(id__in=biz_node_ids) | common_nodes | self.filter_queryset(self.get_queryset()))
            .distinct()
            .prefetch_related(Prefetch("tasks", queryset=UptimeCheckTask.objects.only("id")))
        )
        serializer: UptimeCheckNodeSerializer = self.get_serializer(queryset, many=True)
        # 将节点解析成cmdb主机，存放在以host_id 和 ip+cloud_id 为key 的 字典里
        node_to_host = resource.uptime_check.get_node_host_dict(bk_tenant_id=get_request_tenant_id(), nodes=queryset)

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

        node_task_counts = {node.id: node.tasks.count() for node in queryset}

        for node in serializer.data:
            task_num = node_task_counts.get(node["id"], 0)
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
    def is_exist(self, request, *args, **kwargs):
        """
        用于给前端判断输入的IP是否属于已建节点
        """
        ip = request.GET.get("ip")
        bk_biz_id = request.GET.get("bk_biz_id")
        return Response(
            {"is_exist": True if self.get_queryset().filter(ip=ip, bk_biz_id=bk_biz_id).exists() else False}
        )

    @action(methods=["GET"], detail=False)
    def fix_name_conflict(self, request, *args, **kwargs):
        """
        节点重名时自动补全一个名称，如广东移动补全为广东移动2
        """
        # filter() 时, 在mysql里，‘name=’ 会忽略结尾空格，而'name__startswith'不会。故在进行校验时，将结尾空格去掉。
        name = request.GET.get("name", "").rstrip()
        bk_biz_id = request.GET.get("bk_biz_id")
        id = request.GET.get("id")

        queryset = self.get_queryset().filter(name=name, bk_biz_id=bk_biz_id)
        if id:
            queryset = queryset.exclude(id=id)
        is_exists = queryset.exists()

        if is_exists:
            all_names = self.get_queryset().filter(name__startswith=name, bk_biz_id=bk_biz_id).values("name")
            num_suffix_list = []
            for item in all_names:
                num_suffix_list.append(safe_int(item["name"].strip(name)))
            max_num = max(num_suffix_list)
            if max_num:
                name += str(max_num + 1)
            else:
                name += "2"
        return Response({"name": name})


class UptimeCheckTaskViewSet(PermissionMixin, viewsets.ModelViewSet, CountModelMixin):
    _, filterset_class = get_filterset(UptimeCheckTask)
    serializer_class = UptimeCheckTaskSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        旧版动态下发配置转换
        """
        data = super().retrieve(request, *args, **kwargs).data
        config = data["config"]
        protocol = data["protocol"]
        if config.get("urls") and protocol == UptimeCheckTask.Protocol.HTTP:
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

    def get_queryset(self):
        """
        可用于按任务组筛选拨测任务
        """
        queryset = UptimeCheckTask.objects.all().prefetch_related("nodes", "groups")
        group_id = self.request.query_params.get("group_id")
        if group_id:
            uptime_check_group = UptimeCheckGroup.objects.get(id=group_id)
            queryset = uptime_check_group.tasks.all()
            # NOTE: ManyToMany 时 Proxy 关系将失效，此处的 queryset.model 将会是原始的 Model 类
            # 当前版本的 django-filter 将会校验 Model 类的所属而并未考虑到 Proxy，所以我们手动修改一下指向
            # 可以参考：https://stackoverflow.com/questions/3891880/django-proxy-model-and-foreignkey
            queryset.model = UptimeCheckTask
        return queryset

    def list(self, request, *args, **kwargs):
        """
        重写list，传入get_groups时整合拨测任务组卡片页数据，避免数据库重复查询
        """
        queryset = self.filter_queryset(self.get_queryset())

        # 如果传入plain参数，则返回简单数据
        if request.query_params.get("plain", False):
            task_id = request.query_params.get("id")
            if task_id:
                tasks = queryset.filter(id=task_id)
                response = Response(
                    [
                        {
                            "id": task.id,
                            "name": task.name,
                            "bk_biz_id": task.bk_biz_id,
                            "status": task.status,
                            "config": task.config,
                            "protocol": task.protocol,
                            "check_interval": task.check_interval,
                            "location": task.location,
                        }
                        for task in tasks
                    ]
                )
            else:
                response = Response(
                    [
                        {
                            "id": task.id,
                            "name": task.name,
                            "bk_biz_id": task.bk_biz_id,
                        }
                        for task in queryset.only("id", "name", "bk_biz_id")
                    ]
                )
            return response

        bk_biz_id = int(request.query_params.get("bk_biz_id", 0))
        if bk_biz_id:
            queryset = queryset.filter(bk_biz_id=bk_biz_id)
        get_groups = request.query_params.get("get_groups", False)
        get_available = request.query_params.get("get_available") == "true"
        get_task_duration = request.query_params.get("get_task_duration") == "true"
        task_data = resource.uptime_check.uptime_check_task_list(
            task_data=queryset, bk_biz_id=bk_biz_id, get_available=get_available, get_task_duration=get_task_duration
        )

        # 如果节点对应的业务id已经不存在了，则该任务状态强制显示为START_FAILED，用于给用户提示
        biz_id_list = get_business_id_list()
        for data in task_data:
            for node in data["nodes"]:
                if node["bk_biz_id"] not in biz_id_list:
                    data["status"] = UptimeCheckTask.Status.START_FAILED

        if get_groups:
            result = resource.uptime_check.uptime_check_card(bk_biz_id=bk_biz_id, task_data=task_data)
        else:
            result = task_data
        return Response(result)

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
    def deploy(self, request, *args, **kwargs):
        """
        正式创建任务
        下发正式配置，采集器托管任务，将采集结果上报至计算平台
        """
        task = self.get_object()
        return Response(task.deploy())

    @action(methods=["POST"], detail=True)
    def clone(self, request, *args, **kwargs):
        """
        克隆任务
        """
        task = self.get_object()
        nodes = task.nodes.all()
        task.pk = None

        # 判断重名
        new_name = name = task.name + "_copy"
        i = 1
        while task.__class__.objects.filter(name=new_name):
            new_name = f"{name}({i})"
            i += 1
        task.name = new_name

        # 克隆出的拨测任务为 ”未保存“ 状态，使用者可进行编辑后提交
        task.create_user = request.user.username
        task.update_user = request.user.username
        task.status = task.__class__.Status.STOPED
        task.subscription_id = 0
        task.save()
        return Response(task.nodes.add(*nodes))

    @action(methods=["POST"], detail=True)
    def change_status(self, request, *args, **kwargs):
        """
        更改任务状态
        """
        task = self.get_object()
        status = request.data.get("status", "")
        task.change_status(status)
        return Response(data={"id": task.pk, "status": task.status})

    @action(methods=["GET"], detail=True)
    def running_status(self, request, *args, **kwargs):
        """
        创建拨测任务时，查询部署任务是否成功，失败则返回节点管理中部署失败错误日志
        :return:
        """
        task = self.get_object()
        if task.status == task.Status.START_FAILED:
            error_log = [
                item["error_log"]
                for item in UptimeCheckTaskCollectorLog.objects.filter(task_id=task.id, is_deleted=False).values()
            ]
            return Response(data={"status": task.Status.START_FAILED, "error_log": error_log})
        else:
            return Response(data={"status": task.status})


class UptimeCheckGroupViewSet(PermissionMixin, viewsets.ModelViewSet):
    queryset = UptimeCheckGroup.objects.all()
    _, filterset_class = get_filterset(UptimeCheckGroup)
    serializer_class = UptimeCheckGroupSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        简化返回数据
        """
        data = super().retrieve(request, *args, **kwargs).data
        result = {
            "id": data["id"],
            "name": data["name"],
            "bk_biz_id": data["bk_biz_id"],
            "logo": data["logo"],
            "task_list": [{"id": item["id"], "name": item["name"]} for item in data["tasks"]],
        }
        return Response(result)

    @action(methods=["POST"], detail=True)
    def add_task(self, request, *args, **kwargs):
        """
        拨测任务拖拽进入任务组
        """
        task_id = request.data.get("task_id")
        task = UptimeCheckTask.objects.get(pk=task_id)
        group = self.get_object()
        if task in group.tasks.all():
            return Response({"msg": _("拨测分组({})已存在任务({})".format(group.name, task.name))})
        group.tasks.add(task_id)
        return Response({"msg": _("拨测分组({})添加任务({})成功".format(group.name, task.name))})

    @action(methods=["post"], detail=True)
    def remove_task(self, request, *args, **kwargs):
        """拨测任务组移除拨测任务"""
        task_id = request.data.get("task_id")
        task = UptimeCheckTask.objects.get(pk=task_id)
        group = self.get_object()
        if task not in group.tasks.all():
            return Response({"msg": _("拨测分组({})不存在任务({})".format(group.name, task.name))})
        group.tasks.remove(task_id)
        return Response({"msg": _("拨测分组({})移除任务({})成功".format(group.name, task.name))})


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
