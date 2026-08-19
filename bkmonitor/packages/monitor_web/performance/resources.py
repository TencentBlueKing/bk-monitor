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
import time

from api.cmdb.define import Host, TopoNode
from bkm_space.validate import validate_bk_biz_id
from django.conf import settings
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils import time_tools
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.user import get_request_username
from bkmonitor.views import serializers
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.contrib.cache import CacheResource
from core.drf_resource.exceptions import CustomException
from core.errors.share import InvalidParamsError, ParamsPermissionDeniedError
from monitor_web.constants import AGENT_STATUS
from monitor_web.performance.snapshot import (
    SNAPSHOT_DEADLINE,
    SNAPSHOT_SECTIONS,
    HostMetricSnapshotStore,
    SnapshotState,
    SnapshotUnavailable,
    build_host_ids_hash,
    build_snapshot_fingerprint,
    canonicalize_snapshot_time,
)

logger = logging.getLogger(__name__)


class HostPerformanceResource(CacheResource):
    """
    获取主机列表信息
    """

    cache_type = CacheType.HOST

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    @staticmethod
    def get_process_status(
        bk_biz_id: int,
        hosts: list[Host],
        data: dict[int, dict],
        start_time: int = None,
        end_time: int = None,
    ):
        """
        获取进程信息

        注意：CMDB 进程基本信息（名称/端口/命令等）为当前快照，不支持历史查询；
        start_time/end_time 仅作用于进程存活状态判定（system.proc_port 的 proc_exists 指标）。
        选择历史时间后，进程列表仍反映当前 CMDB 数据，但进程启停状态与所选时间窗口一致。
        """
        result = resource.cc.get_process_info(
            bk_biz_id=bk_biz_id,
            hosts=hosts,
            start_time=start_time,
            end_time=end_time,
        )
        for bk_host_id in result:
            if bk_host_id not in data:
                continue
            data[bk_host_id]["component"] = [
                {
                    "display_name": process["name"],
                    "ports": process["ports"],
                    "protocol": process["protocol"],
                    "status": process["status"],
                    "id": process.get("id"),
                    "bindIp": process.get("bindIp"),
                    "port": process.get("port"),
                    "startCommand": process.get("startCommand"),
                    "user": process.get("user"),
                }
                for process in result[bk_host_id]
            ]

    @staticmethod
    def get_alarm_count(bk_biz_id: int, hosts: list[Host], data: dict[int, dict]):
        """
        获取告警信息
        """
        result = resource.cc.get_host_alarm_count(bk_biz_id=bk_biz_id, hosts=hosts)
        for bk_host_id in result:
            if bk_host_id not in data:
                continue
            data[bk_host_id]["alarm_count"] = sorted(
                [{"level": level, "count": count} for level, count in result[bk_host_id].items()],
                key=lambda x: x["level"],
            )

    def perform_request(self, params):
        bk_biz_id = params.get("bk_biz_id")
        hosts: list[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
        topo_links: dict[str, list[TopoNode]] = api.cmdb.get_topo_tree(
            bk_biz_id=params["bk_biz_id"]
        ).convert_to_topo_link()

        host_dict = {
            host.bk_host_id: {
                # 基础信息
                "display_name": host.display_name,
                "bk_cloud_id": host.bk_cloud_id,
                "bk_host_id": host.bk_host_id,
                "bk_host_innerip": host.bk_host_innerip,
                "bk_host_innerip_v6": host.bk_host_innerip_v6,
                "bk_host_name": host.bk_host_name,
                "bk_host_outerip": host.bk_host_outerip,
                "bk_host_outerip_v6": host.bk_host_outerip_v6,
                "bk_os_name": host.bk_os_name,
                "bk_os_type": host.bk_os_type,
                "bk_state": host.bk_state,
                "bk_biz_id": bk_biz_id,
                "bk_cloud_name": host.bk_cloud_name,
                "region": host.bk_province_name,
                "ignore_monitoring": host.ignore_monitoring,
                "is_shielding": host.is_shielding,
                # 拓扑信息
                "module": SearchHostInfoResource.get_module_info(host.bk_module_ids, topo_links),
                # 性能指标信息
                "cpu_usage": None,
                "cpu_load": None,
                "psc_mem_usage": None,
                "mem_usage": None,
                "io_util": None,
                "disk_in_use": None,
                # Agent及数据状态
                "status": AGENT_STATUS.UNKNOWN,
                # 进程信息
                "component": [],
                "alarm_count": [],
            }
            for host in hosts
        }

        pool = ThreadPool()
        pool.apply_async(SearchHostMetricResource.get_agent_status, args=(bk_biz_id, hosts, host_dict))
        pool.apply_async(SearchHostMetricResource.get_performance_data, args=(bk_biz_id, hosts, host_dict))
        pool.apply_async(self.get_process_status, args=(bk_biz_id, hosts, host_dict))
        pool.apply_async(self.get_alarm_count, args=(bk_biz_id, hosts, host_dict))
        pool.close()
        pool.join()

        return {
            "hosts": list(host_dict.values()),
            "update_time": time_tools.now().strftime("%Y-%m-%d %H:%M:%S%z"),
        }


class HostPerformanceDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_host_id = serializers.IntegerField(required=True, label="主机ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bk_host_id = params["bk_host_id"]

        # 获取主机信息
        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=[bk_host_id])
        if not hosts:
            raise CustomException(f"host({bk_host_id}) not found")
        host = hosts[0]

        # 获取主机拓扑信息
        topo_links: dict[str, list[TopoNode]] = api.cmdb.get_topo_tree(
            bk_biz_id=params["bk_biz_id"]
        ).convert_to_topo_link()
        module = SearchHostInfoResource.get_module_info(host.bk_module_ids, topo_links)

        # 获取Agent状态
        statuses = resource.cc.get_agent_status(bk_biz_id=bk_biz_id, hosts=[host])
        status = statuses.get(host.bk_host_id, AGENT_STATUS.UNKNOWN)

        # 获取业务信息
        business = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])[0]

        return_data = {
            "bk_host_id": host.bk_host_id,
            "bk_host_innerip": host.bk_host_innerip,
            "bk_host_outerip": host.bk_host_outerip,
            "bk_host_innerip_v6": host.bk_host_innerip_v6,
            "bk_host_outerip_v6": host.bk_host_outerip_v6,
            "bk_cloud_id": host.bk_cloud_id,
            "bk_cloud_name": host.bk_cloud_name,
            "bk_host_name": host.bk_host_name,
            "bk_os_name": host.bk_os_name,
            "bk_os_type": host.bk_os_type,
            "region": host.bk_province_name,
            "bk_biz_id": bk_biz_id,
            "bk_biz_name": business.bk_biz_name,
            "module": module,
            "status": status,
            "bk_state": host.bk_state,
        }

        return return_data


class HostTopoNodeDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        bk_obj_id = serializers.CharField(required=True, label="节点类型")
        bk_inst_id = serializers.IntegerField(required=True, label="节点实例ID")

    @staticmethod
    def get_alarm_count(bk_biz_id: int, hosts: list[Host]):
        """
        统计主机关联告警数量
        """
        if not hosts:
            return 0

        # 获取关联告警数量
        alarm_counts = resource.cc.get_host_alarm_count(bk_biz_id=bk_biz_id, hosts=hosts)
        if not alarm_counts:
            return 0

        # 统计告警数量
        count = 0
        for no_use, alarm_count in alarm_counts.items():
            for value in alarm_count.values():
                count += value
        return count

    def perform_request(self, params: dict):
        bk_obj_id = params["bk_obj_id"]
        bk_inst_id = params["bk_inst_id"]
        bk_biz_id = params["bk_biz_id"]

        # 查询节点信息
        topo_nodes = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id).get_all_nodes_with_relation()
        node = topo_nodes.get(f"{bk_obj_id}_{bk_inst_id}")

        # 查询节点下的主机
        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id, topo_nodes={bk_obj_id: [bk_inst_id]})

        # 查询关联策略数量
        enabled_strategy_count, disabled_strategy_count = resource.cc.get_topo_strategy_count(
            bk_biz_id=bk_biz_id, bk_obj_id=bk_obj_id, bk_inst_id=bk_inst_id
        )

        # 查询主备负责人
        operator, bk_bak_operator = [], []
        if bk_obj_id == "module":
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=[bk_inst_id])
            if modules:
                m = modules[0]
                operator, bk_bak_operator = m.operator, m.bk_bak_operator

        return {
            "bk_obj_id": bk_obj_id,
            "bk_inst_id": bk_inst_id,
            "bk_obj_name": node.bk_obj_name if node else "",
            "bk_inst_name": node.bk_inst_name if node else "",
            "operator": operator,
            "bk_bak_operator": bk_bak_operator,
            "child_count": len(hosts) if bk_obj_id == "module" else len(node.child),
            "host_count": len(hosts),
            "alarm_count": self.get_alarm_count(bk_biz_id, hosts),
            "alarm_strategy": {"enabled": enabled_strategy_count, "disabled": disabled_strategy_count},
        }


class TopoNodeProcessStatusResource(Resource):
    """
    获取拓扑下的进程
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        bk_obj_id = serializers.CharField(required=True, label="节点类型")
        bk_inst_id = serializers.IntegerField(required=True, label="节点实例ID")

    def perform_request(self, validated_request_data):
        bk_obj_id = validated_request_data["bk_obj_id"]
        bk_inst_id = validated_request_data.get("bk_inst_id")
        bk_biz_id = validated_request_data["bk_biz_id"]

        service_instances = api.cmdb.get_service_instance_by_topo_node(
            bk_biz_id=bk_biz_id, topo_nodes={bk_obj_id: [bk_inst_id]}
        )

        processes = []
        for service_instance in service_instances:
            if service_instance and service_instance.process_instances:
                processes.extend(service_instance.process_instances)
        process_list = [process["process"] for process in processes]

        return_data = list()
        process_name_list = [process_info.get("bk_process_name", "") for process_info in process_list]
        for process_name in set(process_name_list):
            # 这里status直接置灰，ports、protocol留空，只保留display_name
            info = {"status": AGENT_STATUS.UNKNOWN, "ports": [], "display_name": process_name, "protocol": ""}
            return_data.append(info)

        return return_data


class SearchHostInfoResource(ApiAuthResource):
    """
    主机信息查询
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_host_id = serializers.IntegerField(required=False, label="主机ID")
        bk_obj_id = serializers.CharField(required=False, label="拓扑对象ID")
        bk_inst_id = serializers.IntegerField(required=False, label="拓扑实例ID")

        def validate(self, attrs):
            if bool(attrs.get("bk_obj_id")) != (attrs.get("bk_inst_id") is not None):
                raise InvalidParamsError({"key": "bk_obj_id,bk_inst_id"})
            return attrs

        def validate_bk_biz_id(self, value):
            return validate_bk_biz_id(value)

    @staticmethod
    def get_module_info(bk_module_ids: list[int], topo_links: dict[str, list[TopoNode]]) -> list[dict]:
        """
        获取模块详情
        """
        modules = []
        for bk_module_id in bk_module_ids:
            key = f"module|{bk_module_id}"
            if key not in topo_links:
                continue
            topo_link = topo_links[key]

            modules.append(
                {
                    "id": f"module|{topo_link[0].bk_inst_id}",
                    "bk_inst_id": topo_link[0].bk_inst_id,
                    "bk_inst_name": topo_link[0].bk_inst_name,
                    "topo_link": [f"{node.bk_obj_id}|{node.bk_inst_id}" for node in reversed(topo_link)],
                    "topo_link_display": [node.bk_inst_name for node in reversed(topo_link)],
                    "bk_obj_name_map": {node.bk_obj_id: node.bk_obj_name for node in reversed(topo_link)},
                }
            )
        return modules

    def perform_request(self, params):
        def get_hosts() -> list[Host]:
            if params.get("bk_host_id") is not None:
                return api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=[params["bk_host_id"]])
            if params.get("bk_obj_id") and params.get("bk_inst_id") is not None:
                return api.cmdb.get_host_by_topo_node(
                    bk_biz_id=params["bk_biz_id"],
                    topo_nodes={params["bk_obj_id"]: [params["bk_inst_id"]]},
                )
            return api.cmdb.get_host_by_topo_node(bk_biz_id=params["bk_biz_id"])

        pool = ThreadPool(2)
        hosts_future = pool.apply_async(get_hosts)
        topo_future = pool.apply_async(api.cmdb.get_topo_tree, kwds={"bk_biz_id": params["bk_biz_id"]})
        pool.close()
        try:
            hosts = hosts_future.get()
            topo_links: dict[str, list[TopoNode]] = topo_future.get().convert_to_topo_link()
        finally:
            pool.join()

        result = []
        for host in hosts:
            result.append(
                {
                    "display_name": host.display_name,
                    "bk_host_id": host.bk_host_id,
                    "bk_biz_id": host.bk_biz_id,
                    "bk_cloud_id": host.bk_cloud_id,
                    "bk_cloud_name": host.bk_cloud_name,
                    "bk_host_innerip": host.bk_host_innerip,
                    "bk_host_innerip_v6": host.bk_host_innerip_v6,
                    "bk_host_outerip": host.bk_host_outerip,
                    "bk_host_outerip_v6": host.bk_host_outerip_v6,
                    "bk_os_type": host.bk_os_type,
                    "bk_os_name": host.bk_os_name,
                    "region": host.bk_province_name,
                    "bk_host_name": host.bk_host_name,
                    "ignore_monitoring": host.ignore_monitoring,
                    "is_shielding": host.is_shielding,
                    "module": self.get_module_info(host.bk_module_ids, topo_links),
                }
            )

        return result


class SearchHostMetricResource(ApiAuthResource):
    """
    查询指定主机的agent及指标信息
    """

    PAGE_QUERY_MODE = "page"
    PAGE_HOST_LIMIT = 100

    class RequestSerializer(serializers.Serializer):
        bk_host_ids = serializers.ListField(label="主机ID", child=serializers.IntegerField())
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_mode = serializers.ChoiceField(choices=("full", "page"), default="full")
        bk_host_id = serializers.IntegerField(required=False, label="分享主机ID")
        bk_obj_id = serializers.CharField(required=False, label="分享拓扑对象ID")
        bk_inst_id = serializers.IntegerField(required=False, label="分享拓扑实例ID")
        # 时间范围（秒级 Unix 时间戳，可选）。传入时约束 TSDB 性能指标查询区间，
        # 不传则保持默认"最近三分钟"行为（向后兼容）
        start_time = serializers.IntegerField(required=False, label="开始时间(秒级时间戳)")
        end_time = serializers.IntegerField(required=False, label="结束时间(秒级时间戳)")

        # 主机场景，以关联资源身份请求
        def validate_bk_biz_id(self, value):
            return validate_bk_biz_id(value)

        def validate(self, attrs):
            if (
                attrs["query_mode"] == SearchHostMetricResource.PAGE_QUERY_MODE
                and len(attrs["bk_host_ids"]) > SearchHostMetricResource.PAGE_HOST_LIMIT
            ):
                raise serializers.ValidationError(
                    {"bk_host_ids": f"page query supports at most {SearchHostMetricResource.PAGE_HOST_LIMIT} hosts"}
                )
            return attrs

    @staticmethod
    def validate_scope_host_ids(params):
        requested_host_ids = set(params["bk_host_ids"])
        if params.get("bk_host_id") is not None:
            allowed_host_ids = {params["bk_host_id"]}
        elif params.get("bk_obj_id") and params.get("bk_inst_id") is not None:
            allowed_host_ids = {
                host.bk_host_id
                for host in api.cmdb.get_host_by_topo_node(
                    bk_biz_id=params["bk_biz_id"],
                    topo_nodes={params["bk_obj_id"]: [params["bk_inst_id"]]},
                )
            }
        elif params.get("bk_obj_id") or params.get("bk_inst_id") is not None:
            raise InvalidParamsError({"key": "bk_obj_id,bk_inst_id"})
        else:
            return

        if not requested_host_ids.issubset(allowed_host_ids):
            raise ParamsPermissionDeniedError(
                {
                    "key": "bk_host_ids",
                    "error_params": sorted(requested_host_ids),
                    "correct_params": sorted(allowed_host_ids),
                }
            )

    @staticmethod
    def get_agent_status(
        bk_biz_id: int,
        hosts: list[Host],
        data: dict[int, dict],
        start_time: int = None,
        end_time: int = None,
        fail_on_incomplete: bool = False,
        target_filter: dict | None = None,
        incomplete_callback=None,
    ):
        """
        获取Agent状态
        """
        agent_statuses = resource.cc.get_agent_status(
            bk_biz_id=bk_biz_id,
            hosts=hosts,
            start_time=start_time,
            end_time=end_time,
            fail_on_incomplete=fail_on_incomplete,
            target_filter=target_filter,
            incomplete_callback=incomplete_callback,
        )
        for bk_host_id, status in agent_statuses.items():
            if bk_host_id not in data:
                continue
            data[bk_host_id]["status"] = status

    @staticmethod
    def get_performance_data(
        bk_biz_id: int,
        hosts: list[Host],
        data: dict[int, dict],
        start_time: int = None,
        end_time: int = None,
        fail_on_incomplete: bool = False,
        target_filter: dict | None = None,
        incomplete_callback=None,
    ):
        """
        获取指标信息
        """
        result = resource.cc.get_host_performance_data(
            bk_biz_id=bk_biz_id,
            hosts=hosts,
            start_time=start_time,
            end_time=end_time,
            fail_on_incomplete=fail_on_incomplete,
            target_filter=target_filter,
            incomplete_callback=incomplete_callback,
        )
        for bk_host_id, metrics in result.items():
            if bk_host_id not in data:
                continue
            data[bk_host_id].update(metrics)

    @staticmethod
    def get_process_status(
        bk_biz_id: int,
        hosts: list[Host],
        data: dict[int, dict],
        start_time: int = None,
        end_time: int = None,
        fail_on_incomplete: bool = False,
        filter_by_hosts: bool = False,
        target_filter: dict | None = None,
        incomplete_callback=None,
    ):
        """
        获取进程信息

        注意：CMDB 进程基本信息（名称/端口/命令等）为当前快照，不支持历史查询；
        start_time/end_time 仅作用于进程存活状态判定（system.proc_port 的 proc_exists 指标）。
        选择历史时间后，进程列表仍反映当前 CMDB 数据，但进程启停状态与所选时间窗口一致。
        """
        result = resource.cc.get_process_info(
            bk_biz_id=bk_biz_id,
            hosts=hosts,
            start_time=start_time,
            end_time=end_time,
            fail_on_incomplete=fail_on_incomplete,
            filter_by_hosts=filter_by_hosts,
            target_filter=target_filter,
            incomplete_callback=incomplete_callback,
        )
        for bk_host_id in result:
            if bk_host_id not in data:
                continue

            data[bk_host_id]["component"] = [
                {
                    "display_name": process["name"],
                    "status": process["status"],
                    "id": process.get("id"),
                    "bindIp": process.get("bindIp"),
                    "port": process.get("port"),
                    "startCommand": process.get("startCommand"),
                    "user": process.get("user"),
                }
                for process in result[bk_host_id]
            ]

    @staticmethod
    def get_alarm_count(
        bk_biz_id: int,
        hosts: list[Host],
        data: dict[int, dict],
        start_time: int = None,
        end_time: int = None,
        filter_by_host_ip: bool = True,
    ):
        """
        获取告警信息
        """
        result = resource.cc.get_host_alarm_count(
            bk_biz_id=bk_biz_id,
            hosts=hosts,
            start_time=start_time,
            end_time=end_time,
            filter_by_host_ip=filter_by_host_ip,
        )
        for bk_host_id in result:
            if bk_host_id not in data:
                continue
            data[bk_host_id]["alarm_count"] = sorted(
                [{"level": level, "count": count} for level, count in result[bk_host_id].items()],
                key=lambda x: x["level"],
            )

    def perform_request(self, params):
        self.validate_scope_host_ids(params)
        bk_biz_id = params["bk_biz_id"]
        is_page_query = params.get("query_mode") == self.PAGE_QUERY_MODE
        defaults = {
            "status": AGENT_STATUS.UNKNOWN,
            "cpu_load": None,
            "cpu_usage": None,
            "disk_in_use": None,
            "io_util": None,
            "mem_usage": None,
            "psc_mem_usage": None,
            "component": [],
            "alarm_count": [],
        }
        data = {
            bk_host_id: (
                {}
                if is_page_query
                else {
                    "status": AGENT_STATUS.UNKNOWN,
                    "cpu_load": None,
                    "cpu_usage": None,
                    "disk_in_use": None,
                    "io_util": None,
                    "mem_usage": None,
                    "psc_mem_usage": None,
                    "component": [],
                    "alarm_count": [],
                }
            )
            for bk_host_id in params["bk_host_ids"]
        }

        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=params["bk_host_ids"])

        pool = ThreadPool()
        task_args = (bk_biz_id, hosts, data, params.get("start_time"), params.get("end_time"))
        section_states = {section: {"state": "RUNNING"} for section in SNAPSHOT_SECTIONS}

        def mark_partial(section):
            section_states[section] = {"state": "PARTIAL"}

        futures = {
            "agent_status": pool.apply_async(
                self.get_agent_status,
                args=(*task_args, not is_page_query),
                kwds={"incomplete_callback": (lambda: mark_partial("agent_status")) if is_page_query else None},
            ),
            "performance_data": pool.apply_async(
                self.get_performance_data,
                args=(*task_args, not is_page_query),
                kwds={"incomplete_callback": (lambda: mark_partial("performance_data")) if is_page_query else None},
            ),
            "process_status": pool.apply_async(
                self.get_process_status,
                args=(*task_args, not is_page_query, is_page_query),
                kwds={"incomplete_callback": (lambda: mark_partial("process_status")) if is_page_query else None},
            ),
            "alarm_count": pool.apply_async(self.get_alarm_count, args=task_args),
        }
        pool.close()
        failed_sections = []
        for section, future in futures.items():
            try:
                future.get()
            except Exception:
                logger.exception("get host metric section %s failed, bk_biz_id=%s", section, bk_biz_id)
                failed_sections.append(section)
                section_states[section] = {"state": "FAILED"}
                continue
            if section_states[section]["state"] == "RUNNING":
                section_states[section] = {"state": "READY"}
            if is_page_query and section_states[section]["state"] == "READY":
                section_defaults = {
                    "agent_status": {"status": defaults["status"]},
                    "performance_data": {
                        key: defaults[key]
                        for key in defaults
                        if key.endswith("usage") or key in {"cpu_load", "disk_in_use", "io_util"}
                    },
                    "process_status": {"component": []},
                    "alarm_count": {"alarm_count": []},
                }[section]
                for host_data in data.values():
                    for field, value in section_defaults.items():
                        host_data.setdefault(field, value)
        pool.join()
        if failed_sections and not is_page_query:
            raise CustomException("get host metric data failed", data={"failed_sections": failed_sections})
        if is_page_query:
            return {
                "data": data,
                "failed_sections": sorted(failed_sections),
                "partial_sections": sorted(
                    section for section, state in section_states.items() if state["state"] == "PARTIAL"
                ),
                "sections": section_states,
            }
        return data


class HostMetricSnapshotRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    start_time = serializers.IntegerField(label="开始时间(秒级时间戳)")
    end_time = serializers.IntegerField(label="结束时间(秒级时间戳)")
    bk_host_id = serializers.IntegerField(required=False, label="分享主机ID")
    bk_obj_id = serializers.CharField(required=False, label="分享拓扑对象ID")
    bk_inst_id = serializers.IntegerField(required=False, label="分享拓扑实例ID")

    def to_internal_value(self, data):
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError({field: ["unexpected field"] for field in sorted(unknown_fields)})
        return super().to_internal_value(data)

    def validate_bk_biz_id(self, value):
        return validate_bk_biz_id(value)

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": ["must be greater than start_time"]})
        has_host = attrs.get("bk_host_id") is not None
        has_topo = attrs.get("bk_obj_id") is not None or attrs.get("bk_inst_id") is not None
        if has_host and has_topo:
            raise serializers.ValidationError({"bk_host_id": ["host and topology scopes are mutually exclusive"]})
        if bool(attrs.get("bk_obj_id")) != (attrs.get("bk_inst_id") is not None):
            raise serializers.ValidationError({"bk_obj_id": ["bk_obj_id and bk_inst_id must be provided together"]})
        return attrs


def build_host_metric_snapshot_scope(params: dict) -> dict:
    if params.get("bk_host_id") is not None:
        return {"bk_host_id": params["bk_host_id"], "type": "host"}
    if params.get("bk_obj_id") and params.get("bk_inst_id") is not None:
        return {
            "bk_inst_id": params["bk_inst_id"],
            "bk_obj_id": params["bk_obj_id"],
            "type": "topology",
        }
    return {"type": "business"}


def resolve_host_metric_snapshot_scope(params: dict) -> tuple[dict, list[Host]]:
    bk_biz_id = params["bk_biz_id"]
    scope = build_host_metric_snapshot_scope(params)
    if scope["type"] == "host":
        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=[params["bk_host_id"]])
    elif scope["type"] == "topology":
        hosts = api.cmdb.get_host_by_topo_node(
            bk_biz_id=bk_biz_id,
            topo_nodes={params["bk_obj_id"]: [params["bk_inst_id"]]},
        )
    else:
        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
    return scope, hosts


def _unavailable_snapshot_response():
    return {
        "data": {},
        "expired": False,
        "failed_sections": [],
        "retry_after": 5,
        "revision": 0,
        "sections": {},
        "snapshot_id": "",
        "state": SnapshotState.UNAVAILABLE,
    }


def _expired_snapshot_response(snapshot_id: str):
    return {
        "data": {},
        "expired": True,
        "failed_sections": [],
        "retry_after": 5,
        "revision": 0,
        "sections": {},
        "snapshot_id": snapshot_id,
        "state": SnapshotState.EXPIRED,
    }


class CreateHostMetricSnapshotResource(ApiAuthResource):
    RequestSerializer = HostMetricSnapshotRequestSerializer

    def perform_request(self, params):
        if not settings.ENABLE_HOST_METRIC_PROGRESSIVE:
            return _unavailable_snapshot_response()
        scope = build_host_metric_snapshot_scope(params)
        request = get_request(peaceful=True)
        canonical_time = canonicalize_snapshot_time(
            params["start_time"],
            params["end_time"],
            is_share=bool(request and getattr(request, "token", None)),
        )
        bk_tenant_id = get_request_tenant_id()
        fingerprint = build_snapshot_fingerprint(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=params["bk_biz_id"],
            scope=scope,
            time_key=canonical_time.time_key,
        )
        now = int(time.time())
        payload = {
            "bk_biz_id": params["bk_biz_id"],
            "bk_tenant_id": bk_tenant_id,
            "canonical_end_time": canonical_time.end_time,
            "canonical_start_time": canonical_time.start_time,
            "deadline_at": now + SNAPSHOT_DEADLINE,
            "host_count": 0,
            "host_ids_hash": "",
            "scope": scope,
            "sections": {section: {"state": "PENDING"} for section in SNAPSHOT_SECTIONS},
            "username": get_request_username(),
        }
        try:
            store = HostMetricSnapshotStore()
            manifest, created = store.create_or_get(fingerprint, payload)
            if created:
                from monitor_web.performance.tasks import build_host_metric_snapshot

                try:
                    build_host_metric_snapshot.delay(manifest["snapshot_id"])
                except Exception:
                    logger.exception("enqueue host metric snapshot failed, bk_biz_id=%s", params["bk_biz_id"])
                    store.fail(manifest["snapshot_id"], "enqueue_failed")
                else:
                    latest = store.get_manifest(manifest["snapshot_id"])
                    if latest and latest["state"] == SnapshotState.RUNNING and not store.renew_capacity(latest):
                        store.expire(manifest["snapshot_id"], allow_ready=False)
            response = store.build_response(manifest["snapshot_id"], now=now, include_data=False)
            response["revision"] = 0
            return response
        except SnapshotUnavailable:
            logger.warning("host metric snapshot unavailable, bk_biz_id=%s", params["bk_biz_id"])
            return _unavailable_snapshot_response()


class GetHostMetricSnapshotResource(ApiAuthResource):
    class RequestSerializer(HostMetricSnapshotRequestSerializer):
        snapshot_id = serializers.CharField(label="快照ID")
        since_revision = serializers.IntegerField(required=False, min_value=0, label="已加载版本")

    def perform_request(self, params):
        if not settings.ENABLE_HOST_METRIC_PROGRESSIVE:
            return _unavailable_snapshot_response()
        snapshot_id = params["snapshot_id"]
        try:
            store = HostMetricSnapshotStore()
            manifest = store.get_manifest(snapshot_id)
            if not manifest:
                return _expired_snapshot_response(snapshot_id)

            scope = build_host_metric_snapshot_scope(params)
            is_bound = (
                manifest.get("bk_tenant_id") == get_request_tenant_id()
                and manifest.get("bk_biz_id") == params["bk_biz_id"]
                and manifest.get("scope") == scope
                and manifest.get("canonical_start_time") == params["start_time"]
                and manifest.get("canonical_end_time") == params["end_time"]
            )
            current = store.get_current(manifest["fingerprint"])
            if not is_bound or not current or current["snapshot_id"] != snapshot_id:
                return _expired_snapshot_response(snapshot_id)

            response = store.build_response(
                snapshot_id,
                since_revision=params.get("since_revision", 0),
            )
            if response.get("data") or response.get("state") == SnapshotState.READY:
                try:
                    _, hosts = resolve_host_metric_snapshot_scope(params)
                    current_host_hash = build_host_ids_hash(host.bk_host_id for host in hosts)
                except Exception:
                    logger.exception(
                        "resolve host metric snapshot poll scope failed, bk_biz_id=%s", params["bk_biz_id"]
                    )
                    store.expire(snapshot_id)
                    return _expired_snapshot_response(snapshot_id)
                current = store.get_current(manifest["fingerprint"])
                if (
                    response.get("host_ids_hash") != current_host_hash
                    or not current
                    or current["snapshot_id"] != snapshot_id
                ):
                    store.expire(snapshot_id)
                    return _expired_snapshot_response(snapshot_id)
            return response
        except SnapshotUnavailable:
            logger.warning("host metric snapshot poll unavailable, bk_biz_id=%s", params["bk_biz_id"])
            return _unavailable_snapshot_response()
