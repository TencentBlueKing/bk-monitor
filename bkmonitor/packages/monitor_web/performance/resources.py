"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from api.cmdb.define import Host, TopoNode
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils import time_tools
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.views import serializers
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.contrib.cache import CacheResource
from core.drf_resource.exceptions import CustomException
from monitor_web.constants import AGENT_STATUS


class HostPerformanceResource(CacheResource):
    """
    获取主机列表信息
    """

    cache_type = CacheType.HOST

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    @staticmethod
    def get_process_status(bk_biz_id: int, hosts: list[Host], data: dict[int, dict]):
        """
        获取进程信息
        """
        result = resource.cc.get_process_info(bk_biz_id=bk_biz_id, hosts=hosts)
        for bk_host_id in result:
            if bk_host_id not in data:
                continue
            data[bk_host_id]["component"] = [
                {
                    "display_name": process["name"],
                    "ports": process["ports"],
                    "protocol": process["protocol"],
                    "status": process["status"],
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


class SearchHostInfoResource(Resource):
    """
    主机信息查询
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

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
        hosts: list[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=params["bk_biz_id"])
        topo_links: dict[str, list[TopoNode]] = api.cmdb.get_topo_tree(
            bk_biz_id=params["bk_biz_id"]
        ).convert_to_topo_link()

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
                    "bk_host_outerip": host.bk_host_outerip,
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


class SearchHostMetricResource(Resource):
    """
    查询指定主机的agent及指标信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_host_ids = serializers.ListField(label="主机ID", child=serializers.IntegerField())
        bk_biz_id = serializers.IntegerField(label="业务ID")

        # 主机场景，以关联资源身份请求
        def validate_bk_biz_id(self, value):
            return validate_bk_biz_id(value)

    @staticmethod
    def get_agent_status(bk_biz_id: int, hosts: list[Host], data: dict[int, dict]):
        """
        获取Agent状态
        """
        agent_statuses = resource.cc.get_agent_status(bk_biz_id=bk_biz_id, hosts=hosts)
        for bk_host_id, status in agent_statuses.items():
            if bk_host_id not in data:
                continue
            data[bk_host_id]["status"] = status

    @staticmethod
    def get_performance_data(bk_biz_id: int, hosts: list[Host], data: dict[int, dict]):
        """
        获取指标信息
        """
        result = resource.cc.get_host_performance_data(bk_biz_id=bk_biz_id, hosts=hosts)
        for bk_host_id, metrics in result.items():
            if bk_host_id not in data:
                continue
            data[bk_host_id].update(metrics)

    @staticmethod
    def get_process_status(bk_biz_id: int, hosts: list[Host], data: dict[int, dict]):
        """
        获取进程信息
        """
        result = resource.cc.get_process_info(bk_biz_id=bk_biz_id, hosts=hosts)
        for bk_host_id in result:
            if bk_host_id not in data:
                continue

            data[bk_host_id]["component"] = [
                {"display_name": process["name"], "status": process["status"]} for process in result[bk_host_id]
            ]

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        data = {
            bk_host_id: {
                "status": AGENT_STATUS.UNKNOWN,
                "cpu_load": None,
                "cpu_usage": None,
                "disk_in_use": None,
                "io_util": None,
                "mem_usage": None,
                "psc_mem_usage": None,
                "component": [],
            }
            for bk_host_id in params["bk_host_ids"]
        }

        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=params["bk_host_ids"])

        pool = ThreadPool()
        pool.apply_async(self.get_agent_status, args=(bk_biz_id, hosts, data))
        pool.apply_async(self.get_performance_data, args=(bk_biz_id, hosts, data))
        pool.apply_async(self.get_process_status, args=(bk_biz_id, hosts, data))
        pool.close()
        pool.join()
        return data
