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
from typing import Any, Literal, cast

import arrow
from bk_monitor_base.uptime_check import (
    BEAT_STATUS,
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
    control_task,
    delete_group,
    delete_node,
    delete_task,
    get_group,
    get_node,
    get_node_with_host_id,
    get_task,
    list_collector_logs,
    list_groups,
    list_nodes,
    list_tasks,
    save_group,
    save_node,
    save_task,
)
from django.conf import settings
from django.utils.translation import gettext as _
from pydantic import ValidationError as PydanticValidationError
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.utils.common_utils import host_key, safe_int
from bkmonitor.utils.request import get_request_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.uptime_check import UptimeCheckProcessError
from monitor_web.uptime_check.serializers import UptimeCheckTaskSerializer
from monitor_web.uptime_check.utils import get_uptime_check_task_available, get_uptime_check_task_duration
from utils.business import get_business_id_list

logger = logging.getLogger(__name__)


class PermissionMixin:
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:  # type: ignore
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


class UptimeCheckNodeViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测节点 ViewSet"""

    @staticmethod
    def _validate_node_payload(payload: dict[str, Any]) -> UptimeCheckNode:
        """将请求参数校验并转换为节点定义对象。"""
        try:
            return UptimeCheckNode(**payload)
        except PydanticValidationError as exc:
            raise DRFValidationError(exc.errors()) from exc

    @staticmethod
    def _node_beat_check(
        *,
        bk_biz_id: int,
        bk_host_id: int | None,
        ip: str | None,
        plat_id: int | None,
    ) -> None:
        """检查当前节点心跳。

        Args:
            bk_biz_id: 业务 ID。
            bk_host_id: 主机 ID。
            ip: 主机 IP。
            plat_id: 云区域 ID。
        """
        # TODO: 多租户环境下暂时跳过心跳检查
        if settings.ENABLE_MULTI_TENANT_MODE:
            return

        if not is_ipv6_biz(bk_biz_id):
            checked_ip = ip or ""
            bk_cloud_id = plat_id or 0
            if bk_host_id:
                host = api.cmdb.get_host_by_id(
                    bk_biz_id=bk_biz_id,
                    bk_host_ids=[bk_host_id],
                )
                if host:
                    checked_ip = host[0].bk_host_innerip
                    bk_cloud_id = host[0].bk_cloud_id
            promql_statement = (
                f"bkmonitor:beat_monitor:heartbeat_total:uptime{{ip='{checked_ip}',bk_cloud_id='{bk_cloud_id}'}}[3m]"
            )
        else:
            promql_statement = f"bkmonitor:beat_monitor:heartbeat_total:uptime{{bk_host_id='{bk_host_id}'}}[3m]"

        data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
        query_config = {
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "promql": promql_statement,
            "interval": 60,
            "alias": "a",
        }
        data_source = data_source_class(int(bk_biz_id), **query_config)
        query = UnifyQuery(bk_biz_id=int(bk_biz_id), data_sources=[data_source], expression="")
        end_time = arrow.utcnow().timestamp
        records = query.query_data(start_time=(end_time - 180) * 1000, end_time=end_time * 1000, limit=5)

        if len(records) == 0:
            raise UptimeCheckProcessError()

    @staticmethod
    def _get_filtered_nodes(bk_tenant_id: str, bk_biz_id: int):
        """
        获取过滤后的节点列表（公共节点 + 业务节点）
        """
        # 公共节点
        nodes = list_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, query={"include_common": True})

        filtered_nodes: list[UptimeCheckNode] = []
        for node in nodes:
            # 业务节点，直接添加
            if not node.is_common:
                filtered_nodes.append(node)

            # 公共节点，需要判断业务范围可见性
            if node.is_common:
                if not node.biz_scope:
                    filtered_nodes.append(node)
                elif bk_biz_id in node.biz_scope:
                    filtered_nodes.append(node)

        return filtered_nodes

    def retrieve(self, request: Request, pk: int | str):
        """获取节点详情"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        # 获取节点并自动回填 bk_host_id
        node_define = get_node_with_host_id(bk_tenant_id=bk_tenant_id, node_id=int(pk))
        return Response(node_define.model_dump())

    def create(self, request: Request, *args, **kwargs):
        """创建节点"""
        request_data = cast(dict[str, Any], request.data)
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator: str = request.user.username

        # 1) 组装并校验请求参数（统一使用 UptimeCheckNode 进行约束）
        node_payload = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": request_data.get("bk_biz_id"),
            "name": request_data.get("name"),
            "is_common": request_data.get("is_common", False),
            "biz_scope": request_data.get("biz_scope", []),
            "ip_type": request_data.get("ip_type"),
            "bk_host_id": request_data.get("bk_host_id"),
            "ip": request_data.get("ip"),
            "plat_id": request_data.get("plat_id"),
            "location": request_data.get("location", {}),
            "carrieroperator": request_data.get("carrieroperator", ""),
        }
        node_define = self._validate_node_payload(node_payload)

        # 2) 公共节点创建前做权限校验
        if node_define.is_common:
            Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

        # 3) 心跳校验通过后才允许持久化
        self._node_beat_check(
            bk_biz_id=node_define.bk_biz_id,
            bk_host_id=node_define.bk_host_id,
            ip=node_define.ip,
            plat_id=node_define.plat_id,
        )

        # 4) 保存并返回最新节点数据
        node_id = save_node(node=node_define, operator=operator)
        node_define = get_node(bk_tenant_id=bk_tenant_id, bk_biz_id=node_define.bk_biz_id, node_id=node_id)
        return Response(node_define.model_dump())

    def update(self, request: Request, pk: int | str, *args, **kwargs):
        """更新节点"""
        request_data = cast(dict[str, Any], request.data)
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator: str = request.user.username

        # 1) 读取当前节点定义，用于合并更新参数
        node_define = get_node_with_host_id(bk_tenant_id=bk_tenant_id, node_id=int(pk))
        if node_define.is_common and not request_data.get("is_common", True):
            # 校验公共节点管理权限
            Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

            # 检查是否有其他业务的任务在使用此公共节点
            tasks = list_tasks(query={"node_ids": [node_define.id]})
            other_biz_task = [
                _("{}(业务id:{})").format(task.name, task.bk_biz_id)
                for task in tasks
                if task.bk_biz_id != node_define.bk_biz_id
            ]
            if other_biz_task:
                raise CustomException(
                    _("不能取消公共节点勾选，若要取消，请先删除以下任务的当前节点：%s") % "，".join(other_biz_task)
                )

        # 2) 合并旧值和新值，再通过 UptimeCheckNode 做完整校验
        node_payload = {
            "bk_tenant_id": bk_tenant_id,
            "id": node_define.id,
            "bk_biz_id": request_data.get("bk_biz_id", node_define.bk_biz_id),
            "name": request_data.get("name", node_define.name),
            "is_common": request_data.get("is_common", node_define.is_common),
            "biz_scope": request_data.get("biz_scope", node_define.biz_scope),
            "ip_type": request_data.get("ip_type", node_define.ip_type),
            "bk_host_id": request_data.get("bk_host_id", node_define.bk_host_id),
            "ip": request_data.get("ip", node_define.ip),
            "plat_id": request_data.get("plat_id", node_define.plat_id),
            "location": request_data.get("location", node_define.location),
            "carrieroperator": request_data.get("carrieroperator", node_define.carrieroperator),
        }
        updated_node_define = self._validate_node_payload(node_payload)

        # 3) 校验心跳，确保节点可连通
        self._node_beat_check(
            bk_biz_id=updated_node_define.bk_biz_id,
            bk_host_id=updated_node_define.bk_host_id,
            ip=updated_node_define.ip,
            plat_id=updated_node_define.plat_id,
        )

        # 4) 保存并返回更新后的节点定义
        updated_node_id = save_node(node=updated_node_define, operator=operator)
        updated_node_define = get_node(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=updated_node_define.bk_biz_id,
            node_id=updated_node_id,
        )
        return Response(updated_node_define.model_dump())

    def destroy(self, request: Request, pk: int | str):
        """删除节点。bk_biz_id 支持从 query 或 body 获取，以兼容前端 DELETE 请求体传参。"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        node_id = int(pk)
        body = cast(dict, request.data) if request.data is not None else {}
        bk_biz_id_raw = request.query_params.get("bk_biz_id") or body.get("bk_biz_id")
        if bk_biz_id_raw is None:
            raise DRFValidationError({"bk_biz_id": _("参数缺失")})
        bk_biz_id = int(cast(int | str, bk_biz_id_raw))
        operator: str = request.user.username
        delete_node(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, node_id=node_id, operator=operator)
        return Response({"id": node_id, "result": _("删除成功")})

    @staticmethod
    def _get_beat_version(bk_host_ids):
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
        def get_by_node(node: dict, data_map: dict, default=None):
            key = node.get("bk_host_id")
            if not key:
                key = host_key(ip=node["ip"], bk_cloud_id=node["plat_id"])
            if key not in data_map:
                return default
            return data_map[key]

        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = int(request.GET["bk_biz_id"])

        # 获取过滤后的节点列表（公共节点 + 业务节点）
        nodes = self._get_filtered_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        # 将节点解析成cmdb主机，存放在以host_id 和 ip+cloud_id 为key 的 字典里
        node_to_host = resource.uptime_check.get_node_host_dict(bk_tenant_id=bk_tenant_id, nodes=nodes)

        result = []
        bk_host_ids = {host.bk_host_id for host in node_to_host.values()}
        hosts = [node_to_host[host_id] for host_id in bk_host_ids]
        all_beat_version = {}
        if bk_host_ids:
            # 去节点管理拿拨测采集器的版本信息
            all_beat_version = self._get_beat_version(bk_host_ids)

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
            # 统计任务数（通过任务列表获取）
            task_num = len(list_tasks(bk_tenant_id=bk_tenant_id, query={"node_ids": [node.id]}, fields=["id"]))
            host_instance = get_by_node(node.model_dump(), node_to_host)
            beat_version = ""
            if not host_instance:
                # host_id/ip失效，无法找到对应主机实例，拨测节点标记状态为失效
                node_status = {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["INVALID"]}
                display_name = node.ip
            else:
                display_name = host_instance.display_name
                # 未上报数据，默认给不可用状态
                node_status = get_by_node(
                    node.model_dump(),
                    all_node_status,
                    {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["DOWN"]},
                )
                node_status = cast(dict[str, Any], node_status)
                beat_version = get_by_node(node.model_dump(), all_beat_version, beat_version)

            # 添加权限信息
            result.append(
                {
                    "id": node.id,
                    "bk_biz_id": node.bk_biz_id,
                    "name": node.name,
                    "ip": display_name,
                    "bk_host_id": node.bk_host_id,
                    "plat_id": node.plat_id,
                    "ip_type": node.ip_type.value,
                    "country": node.location.get("country"),
                    "province": node.location.get("city"),
                    "carrieroperator": node.carrieroperator,
                    "task_num": task_num,
                    "is_common": node.is_common,
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
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = int(request.GET["bk_biz_id"])

        # 获取过滤后的节点列表（公共节点 + 业务节点）
        nodes = self._get_filtered_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        return Response({"count": len(nodes)})

    @action(methods=["GET"], detail=False)
    def is_exist(self, request, *args, **kwargs):
        """
        用于给前端判断输入的IP是否属于已建节点
        """
        ip = request.GET["ip"]
        if not ip:
            return Response({"is_exist": False})

        bk_biz_id = int(request.GET["bk_biz_id"])
        bk_tenant_id = cast(str, get_request_tenant_id())
        # 先获取，再判断是否存在
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"ip": ip},
        )
        # 从 Define 对象提取 id
        node_ids = [node.id for node in nodes]
        is_exist = bool(node_ids)
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
        bk_tenant_id = cast(str, get_request_tenant_id())

        exclude_id = int(node_id) if node_id else None
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": name},
        )
        # 从 Define 对象提取 id
        node_ids = [node.id for node in nodes]

        # 先获取，再遍历排除指定ID
        is_exists = bool([nid for nid in node_ids if nid != exclude_id])

        if is_exists:
            # 先查询所有同名节点，在外部过滤
            all_nodes = list_nodes(bk_tenant_id=bk_tenant_id, bk_biz_id=int(bk_biz_id))
            # 过滤出名称以指定name开头的节点
            matching_names = [node.name for node in all_nodes if node.name.startswith(name)]
            num_suffix_list = []
            for item_name in matching_names:
                num_suffix_list.append(safe_int(item_name.strip(name)))
            max_num = max(num_suffix_list) if num_suffix_list else 0
            if max_num:
                name += str(max_num + 1)
            else:
                name += "2"
        return Response({"name": name})


class UptimeCheckTaskViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测任务 ViewSet"""

    serializer_class = UptimeCheckTaskSerializer

    def get_permissions(self):
        """拨测任务权限控制"""

        if self.action == "list":
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS, ActionEnum.VIEW_SYNTHETIC])]
        return super().get_permissions()

    @staticmethod
    def _build_task_serializer_payload(
        request_data: dict[str, Any], instance: UptimeCheckTask | None = None
    ) -> dict[str, Any]:
        """构建用于 TaskSerializer 的兼容入参"""
        if instance is None:
            payload: dict[str, Any] = {
                key: request_data[key]
                for key in ("bk_biz_id", "name", "protocol", "config", "labels", "location", "indepentent_dataid")
                if key in request_data
            }
            # 兼容旧字段 independent_dataid
            if "independent_dataid" in request_data and "indepentent_dataid" not in payload:
                payload["indepentent_dataid"] = request_data["independent_dataid"]
            return payload

        protocol = (
            instance.protocol.value if isinstance(instance.protocol, UptimeCheckTaskProtocol) else instance.protocol
        )
        payload = {
            "bk_biz_id": request_data.get("bk_biz_id", instance.bk_biz_id),
            "name": request_data.get("name", instance.name),
            "protocol": request_data.get("protocol", protocol),
            "config": request_data.get("config", instance.config),
            "labels": request_data.get("labels", instance.labels or {}),
            "location": request_data.get("location", instance.location or {}),
        }
        if "indepentent_dataid" in request_data:
            payload["indepentent_dataid"] = request_data["indepentent_dataid"]
        elif "independent_dataid" in request_data:
            payload["indepentent_dataid"] = request_data["independent_dataid"]
        return payload

    @staticmethod
    def _parse_relation_id_list(raw_values: Any, id_keys: tuple[str, ...], field_name: str) -> list[int]:
        """解析节点/分组ID列表，兼容 list[int] 与 list[dict]"""
        if not isinstance(raw_values, list):
            raise DRFValidationError({field_name: _("字段格式错误，必须为数组")})

        result: list[int] = []
        for item in raw_values:
            parsed_value: Any = item
            if isinstance(item, dict):
                found_key = next((key for key in id_keys if item.get(key) is not None), None)
                if found_key is None:
                    continue
                parsed_value = item[found_key]
            try:
                result.append(int(parsed_value))
            except (TypeError, ValueError):
                raise DRFValidationError({field_name: _("字段格式错误，ID 必须为整数")})
        return result

    @classmethod
    def _extract_relation_ids(
        cls,
        request_data: dict[str, Any],
        default_node_ids: list[int] | None = None,
        default_group_ids: list[int] | None = None,
    ) -> tuple[list[int], list[int]]:
        """从新旧字段中提取节点/分组ID"""
        node_ids: list[int]
        group_ids: list[int]

        if "node_id_list" in request_data:
            node_ids = cls._parse_relation_id_list(request_data["node_id_list"], ("id", "node_id"), "node_id_list")
        elif "node_ids" in request_data:
            node_ids = cls._parse_relation_id_list(request_data["node_ids"], ("id", "node_id"), "node_ids")
        elif "nodes" in request_data:
            node_ids = cls._parse_relation_id_list(request_data["nodes"], ("id", "node_id"), "nodes")
        else:
            node_ids = list(default_node_ids or [])

        if "group_id_list" in request_data:
            group_ids = cls._parse_relation_id_list(request_data["group_id_list"], ("id", "group_id"), "group_id_list")
        elif "group_ids" in request_data:
            group_ids = cls._parse_relation_id_list(request_data["group_ids"], ("id", "group_id"), "group_ids")
        elif "groups" in request_data:
            group_ids = cls._parse_relation_id_list(request_data["groups"], ("id", "group_id"), "groups")
        else:
            group_ids = list(default_group_ids or [])

        return node_ids, group_ids

    @staticmethod
    def _check_public_node_permission(bk_tenant_id: str, bk_biz_id: int, node_ids: list[int]) -> None:
        """检查公共节点使用权限"""
        if not node_ids:
            return

        node_objects = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"node_ids": node_ids, "include_common": True},
        )
        if any(node.is_common for node in node_objects) and settings.ENABLE_PUBLIC_SYNTHETIC_LOCATION_AUTH:
            Permission().is_allowed(ActionEnum.USE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

    @staticmethod
    def _check_task_name_conflict(
        bk_tenant_id: str,
        bk_biz_id: int,
        task_name: str,
        exclude_task_id: int | None = None,
    ) -> None:
        """检查任务名称冲突"""
        existing_tasks = list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": task_name},
        )
        if any(task.name == task_name and task.id != exclude_task_id for task in existing_tasks):
            raise CustomException(_("已存在相同名称的拨测任务"))

    def retrieve(self, request: Request, pk: int | str) -> Response:
        """查询任务详情"""
        params: dict[str, Any] = request.query_params

        task_id = int(pk)
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = int(params["bk_biz_id"])

        # 查询任务
        task_define = get_task(bk_tenant_id=bk_tenant_id, task_id=task_id)
        data: dict[str, Any] = task_define.model_dump(exclude={"bk_tenant_id"})
        data["status"] = task_define.status.value

        # 兼容旧字段名
        data["indepentent_dataid"] = data.pop("independent_dataid", False)

        # 补充nodes字段信息
        if task_define.node_ids:
            data["nodes"] = [
                node.model_dump()
                for node in list_nodes(bk_tenant_id=bk_tenant_id, query={"node_ids": data.pop("node_ids", [])})
            ]
            # 兼容旧字段名
            for node in data["nodes"]:
                node["is_deleted"] = False
        else:
            data["nodes"] = []

        # 补充groups字段信息
        if task_define.group_ids:
            data["groups"] = [
                group.model_dump()
                for group in list_groups(
                    bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, query={"group_ids": data.pop("group_ids", [])}
                )
            ]
        else:
            data["groups"] = []

        # 获取可用率和响应时长
        if params.get("get_available"):
            data["available"] = get_uptime_check_task_available(task_id)
        else:
            data["available"] = None
        if params.get("get_task_duration"):
            data["task_duration"] = get_uptime_check_task_duration(task_id)
        else:
            data["task_duration"] = None

        serializer = UptimeCheckTaskSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)

        # 配置处理
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
                host_instances = api.cmdb.get_host_without_biz(bk_tenant_id=bk_tenant_id, ips=ips)["hosts"]
                config["node_list"] = [{"bk_host_id": h.bk_host_id} for h in host_instances]
                host_instance_ips = [h.ip for h in host_instances]
                config["ip_list"] = [host["ip"] for host in hosts if host["ip"] not in host_instance_ips]

        return Response(data)

    def create(self, request: Request, *args, **kwargs):
        """创建任务"""
        request_data = cast(dict[str, Any], request.data)
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator: str = request.user.username

        # 1) 使用 TaskSerializer 进行基础校验与旧字段兼容（如 independent_dataid）
        serializer_payload = self._build_task_serializer_payload(request_data=request_data)
        serializer = self.serializer_class(data=serializer_payload)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        # 2) 从新旧字段中提取节点/分组ID，确保兼容历史请求格式
        node_ids, group_ids = self._extract_relation_ids(request_data=request_data)
        bk_biz_id = int(validated_data["bk_biz_id"])

        # 3) 权限与业务约束校验
        self._check_public_node_permission(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, node_ids=node_ids)
        self._check_task_name_conflict(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            task_name=cast(str, validated_data["name"]),
        )

        # 4) 独立数据源字段兼容：多租户强制开启，否则沿用请求值（默认 False）
        if settings.ENABLE_MULTI_TENANT_MODE:
            independent_dataid = True
        else:
            independent_dataid = bool(validated_data.get("indepentent_dataid", False))

        # 5) 构建定义对象并持久化
        task_define = UptimeCheckTask(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            protocol=UptimeCheckTaskProtocol(validated_data["protocol"]),
            config=validated_data["config"],
            labels=validated_data.get("labels", {}),
            check_interval=validated_data["config"].get("period", 5),
            location=validated_data.get("location", {}),
            node_ids=node_ids,
            group_ids=group_ids,
            independent_dataid=independent_dataid,
        )
        task_id = save_task(task=task_define, operator=operator)
        return Response(get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id).model_dump())

    def update(self, request: Request, pk: int | str, *args, **kwargs):
        """更新任务"""
        request_data = cast(dict[str, Any], request.data)
        bk_tenant_id = cast(str, get_request_tenant_id())
        task_id = int(pk)
        operator: str = request.user.username

        # 1) 读取现有任务，用于补齐局部更新缺失字段
        existing_task = get_task(bk_tenant_id=bk_tenant_id, task_id=task_id)
        serializer_payload = self._build_task_serializer_payload(request_data=request_data, instance=existing_task)
        serializer = self.serializer_class(data=serializer_payload)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        # 2) 解析节点/分组ID（优先请求值；缺省时回退原值）
        node_ids, group_ids = self._extract_relation_ids(
            request_data=request_data,
            default_node_ids=existing_task.node_ids,
            default_group_ids=existing_task.group_ids,
        )
        bk_biz_id = int(validated_data["bk_biz_id"])

        # 3) 权限与名称冲突校验
        self._check_public_node_permission(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, node_ids=node_ids)
        self._check_task_name_conflict(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            task_name=cast(str, validated_data["name"]),
            exclude_task_id=task_id,
        )

        # 4) 更新任务定义并持久化（独立数据源沿用现有配置）
        task_define = UptimeCheckTask(
            bk_tenant_id=bk_tenant_id,
            id=task_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            protocol=UptimeCheckTaskProtocol(validated_data["protocol"]),
            config=validated_data["config"],
            labels=validated_data.get("labels", existing_task.labels or {}),
            check_interval=validated_data["config"].get("period", existing_task.check_interval),
            location=validated_data.get("location", existing_task.location or {}),
            node_ids=node_ids,
            group_ids=group_ids,
            status=UptimeCheckTaskStatus(existing_task.status),
            independent_dataid=existing_task.independent_dataid,
        )
        updated_task_id = save_task(task=task_define, operator=operator)
        return Response(get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=updated_task_id).model_dump())

    def destroy(self, request: Request, pk: int | str):
        """删除任务（需要先停止任务）。bk_biz_id 支持从 query 或 body 获取，以兼容前端 DELETE 请求体传参。"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        task_id = int(pk)
        body = cast(dict, request.data) if request.data is not None else {}
        bk_biz_id_raw = request.query_params.get("bk_biz_id") or body.get("bk_biz_id")
        if bk_biz_id_raw is None:
            raise DRFValidationError({"bk_biz_id": _("参数缺失")})
        bk_biz_id = int(cast(int | str, bk_biz_id_raw))
        operator: str = request.user.username

        task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id)
        # 运行中/启动中/停止中/停止失败的任务，要求先执行停用，避免删除过程中配置状态不一致
        if task.status in (
            UptimeCheckTaskStatus.RUNNING,
            UptimeCheckTaskStatus.STARTING,
            UptimeCheckTaskStatus.STOPING,
            UptimeCheckTaskStatus.STOP_FAILED,
        ):
            raise CustomException(_("任务正在运行，请先停止任务后再删除"))

        delete_task(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            task_id=task_id,
            operator=operator,
        )
        return Response({"id": task_id, "result": _("删除成功")})

    def list(self, request, *args, **kwargs):
        """
        重写list，传入get_groups时整合拨测任务组卡片页数据，避免数据库重复查询
        """
        params = request.query_params

        group_id = params.get("group_id")
        bk_biz_id = int(params["bk_biz_id"])
        bk_tenant_id = cast(str, get_request_tenant_id())
        # 获取分组
        get_groups = params.get("get_groups", False)
        # 获取可用率和响应时长
        get_available = params.get("get_available") == "true"
        get_task_duration = params.get("get_task_duration") == "true"

        # 如果传入plain参数，则返回简单数据
        if params.get("plain", False):
            task_id = params.get("id")
            tasks = list_tasks(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                query={
                    "group_ids": [int(group_id)] if group_id else None,
                    "task_ids": [int(task_id)] if task_id else None,
                }
                if group_id or task_id
                else None,
                order_by=params.get("ordering"),
            )
            if task_id:
                return Response(
                    [
                        {
                            "id": t.id,
                            "name": t.name,
                            "bk_biz_id": t.bk_biz_id,
                            "protocol": t.protocol.value,
                            "config": t.config,
                            "node_ids": t.node_ids,
                            "group_ids": t.group_ids,
                            "status": t.status.value,
                        }
                        for t in tasks
                    ]
                )
            else:
                return Response([{"id": t.id, "name": t.name, "bk_biz_id": t.bk_biz_id} for t in tasks])

        tasks = list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"group_ids": [int(group_id)]} if group_id else None,
            order_by=params.get("ordering"),
        )

        task_data = resource.uptime_check.uptime_check_task_list(
            task_data=[task.model_dump(exclude={"bk_tenant_id"}) for task in tasks],
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
        bk_biz_id = int(request.query_params["bk_biz_id"])
        bk_tenant_id = get_request_tenant_id()

        # 获取数量
        tasks = list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"group_ids": [int(group_id)]} if group_id else None,
            fields=["id"],
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
        result = resource.uptime_check.test_task(
            {"bk_biz_id": bk_biz_id, "config": config, "protocol": protocol, "node_id_list": node_id_list}
        )
        return Response(result)

    @action(methods=["POST"], detail=True)
    def deploy(self, request: Request, pk: int | str):
        """
        正式创建任务
        下发正式配置，采集器托管任务，将采集结果上报至计算平台
        """
        task_id = int(pk)
        bk_tenant_id = cast(str, get_request_tenant_id())
        request_data = cast(dict[str, Any], request.data)
        bk_biz_id = int(request_data["bk_biz_id"])
        result = control_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id, action="deploy")
        return Response(result)

    @action(methods=["POST"], detail=True)
    def clone(self, request, pk: int | str):
        """
        克隆任务
        """
        task_id = int(pk)
        request_data = cast(dict[str, Any], request.data)
        bk_biz_id = int(request_data["bk_biz_id"])
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = request.user.username

        # 获取源任务（带节点和分组）
        source_task = get_task(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            task_id=task_id,
        )

        # 生成新名称
        base_name = source_task.name + "_copy"
        new_name = base_name
        i = 1
        while True:
            existing_tasks = list_tasks(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                query={"name": new_name},
            )
            if not existing_tasks:
                break
            new_name = f"{base_name}({i})"
            i += 1

        # 创建新任务（定义define）
        new_task = UptimeCheckTask(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=new_name,
            protocol=source_task.protocol,
            config=source_task.config,
            node_ids=source_task.node_ids,
            group_ids=source_task.group_ids,
        )

        # 保存新任务
        new_task_id = save_task(new_task, operator)
        return Response({"id": new_task_id})

    @action(methods=["POST"], detail=True)
    def change_status(self, request: Request, pk: int | str):
        """
        更改任务状态
        """
        task_id = int(pk)
        request_data = cast(dict[str, Any], request.data)
        bk_biz_id = int(request_data["bk_biz_id"])
        task_status = request_data.get("status", "")
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = request.user.username

        # status: "running" -> start, "stoped" -> stop
        action_str = cast(
            Literal["start", "stop"], "start" if task_status == UptimeCheckTaskStatus.RUNNING.value else "stop"
        )
        control_task(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id, action=action_str, operator=operator
        )

        # 重新获取更新后的状态
        updated_task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id)
        return Response(data={"id": task_id, "status": updated_task.status.value})

    @action(methods=["GET"], detail=True)
    def running_status(self, request, pk: int | str):
        """
        创建拨测任务时，查询部署任务是否成功，失败则返回节点管理中部署失败错误日志
        :return:
        """
        task_id = int(pk)
        bk_biz_id = int(request.query_params["bk_biz_id"])
        task = get_task(bk_tenant_id=get_request_tenant_id(), bk_biz_id=bk_biz_id, task_id=task_id)
        task_status = task.status.value
        if task_status == UptimeCheckTaskStatus.START_FAILED.value:
            error_log = list_collector_logs(task_id)
            return Response(data={"status": UptimeCheckTaskStatus.START_FAILED.value, "error_log": error_log})
        else:
            return Response(data={"status": task_status})


class UptimeCheckGroupViewSet(PermissionMixin, viewsets.ViewSet):
    """拨测分组 ViewSet"""

    def create(self, request: Request):
        """创建分组"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        request_data = cast(dict[str, Any], request.data)
        bk_biz_id = int(request_data["bk_biz_id"])
        logo: str = request_data.get("logo", "")
        name: str = request_data["name"]
        task_id_list: list[int] = request_data.get("task_id_list", [])
        operator: str = request.user.username

        group = UptimeCheckGroup(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, name=name, logo=logo, task_ids=task_id_list
        )
        group_id = save_group(group, operator)
        return Response(get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id).model_dump())

    def update(self, request: Request, pk: int | str):
        """更新分组"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        group_id = int(pk)
        request_data = cast(dict[str, Any], request.data)
        bk_biz_id = int(request_data["bk_biz_id"])
        logo: str = request_data.get("logo", "")
        name: str = request_data["name"]
        task_id_list: list[int] = request_data.get("task_id_list", [])
        operator: str = request.user.username

        group = get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)
        group.name = name
        group.logo = logo
        group.task_ids = task_id_list
        save_group(group, operator)
        return Response(get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id).model_dump())

    def retrieve(self, request: Request, pk: int | str):
        """
        简化返回数据
        """
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = int(request.query_params["bk_biz_id"])
        group_id = int(pk)
        # 直接获取分组
        group = get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)
        tasks = list_tasks(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, query={"group_ids": [group_id]}, fields=["id", "name"]
        )
        result = {
            "id": group.id,
            "name": group.name,
            "bk_biz_id": group.bk_biz_id,
            "logo": group.logo,
            "task_list": [{"id": task.id, "name": task.name} for task in tasks],
        }
        return Response(result)

    def list(self, request, *args, **kwargs):
        """获取分组列表"""
        bk_biz_id = int(request.query_params["bk_biz_id"])
        bk_tenant_id = get_request_tenant_id()
        get_available = request.query_params.get("get_available", False)
        get_task_duration = request.query_params.get("get_task_duration", False)

        groups = list_groups(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        result = [group.model_dump() for group in groups]

        tasks = list_tasks(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        task_data = resource.uptime_check.uptime_check_task_list(
            task_data=[task.model_dump(exclude={"bk_tenant_id"}) for task in tasks],
            bk_biz_id=bk_biz_id,
            get_available=get_available,
            get_task_duration=get_task_duration,
        )

        # 如果不需要获取可用率和响应时长，则设置为None
        for task in task_data:
            if not get_available:
                task["available"] = None
            if not get_task_duration:
                task["task_duration"] = None

        task_map = {task["id"]: task for task in task_data}
        for group in result:
            task_ids = group.pop("task_ids", [])
            group["tasks"] = [task_map[task_id] for task_id in task_ids if task_id in task_map]

        return Response(result)

    @action(methods=["POST"], detail=True)
    def add_task(self, request, pk: int | str):
        """
        拨测任务拖拽进入任务组
        """
        group_id = int(pk)
        task_id = int(request.data["task_id"])
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = int(request.data["bk_biz_id"])
        operator: str = request.user.username

        # 获取分组信息
        group = get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)
        bk_biz_id = group.bk_biz_id

        # 检查任务是否已在分组中
        group_task_ids = group.task_ids
        if task_id in group_task_ids:
            # 从任务中获取名称
            task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id)
            task_name = task.name
            group_name = group.name
            return Response({"msg": _("拨测分组({})已存在任务({})".format(group_name, task_name))})

        # 添加任务到分组
        new_group_task_ids = group_task_ids + [task_id]
        updated_group = UptimeCheckGroup(
            id=group_id,
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=group.name,
            task_ids=new_group_task_ids,
        )
        save_group(updated_group, operator)

        # 返回成功信息
        task = get_task(bk_tenant_id=bk_tenant_id, task_id=task_id)
        task_name = task.name
        group_name = group.name
        return Response({"msg": _("拨测分组({})添加任务({})成功".format(group_name, task_name))})

    @action(methods=["post"], detail=True)
    def remove_task(self, request, pk: int | str):
        """拨测任务组移除拨测任务"""
        group_id = int(pk)
        task_id = int(request.data["task_id"])
        bk_biz_id = int(request.data["bk_biz_id"])
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = request.user.username

        # 获取分组信息
        group = get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)
        bk_biz_id = group.bk_biz_id

        # 检查任务是否在分组中
        group_task_ids = group.task_ids
        if task_id not in group_task_ids:
            # 从任务中获取名称
            task = get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id)
            task_name = task.name
            group_name = group.name
            return Response({"msg": _("拨测分组({})不存在任务({})".format(group_name, task_name))})

        # 从分组中移除任务
        new_group_task_ids = [tid for tid in group_task_ids if tid != task_id]
        updated_group = UptimeCheckGroup(
            id=group_id,
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=group.name,
            task_ids=new_group_task_ids,
        )
        save_group(updated_group, operator)

        # 返回成功信息
        task = get_task(bk_tenant_id=bk_tenant_id, task_id=task_id)
        task_name = task.name
        group_name = group.name
        return Response({"msg": _("拨测分组({})移除任务({})成功".format(group_name, task_name))})

    def destroy(self, request: Request, pk: int | str):
        """删除分组。bk_biz_id 支持从 query 或 body 获取，以兼容前端 DELETE 请求体传参。"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        group_id = int(pk)
        body = cast(dict, request.data) if request.data is not None else {}
        bk_biz_id_raw = request.query_params.get("bk_biz_id") or body.get("bk_biz_id")
        if bk_biz_id_raw is None:
            raise DRFValidationError({"bk_biz_id": _("参数缺失")})
        bk_biz_id = int(bk_biz_id_raw)
        operator: str = request.user.username
        delete_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id, operator=operator)
        return Response({"msg": _("拨测分组({})删除成功".format(group_id))})


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
