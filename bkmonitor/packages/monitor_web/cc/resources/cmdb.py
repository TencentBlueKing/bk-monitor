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
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

from api.cmdb.define import Host, ServiceInstance, TopoTree
from bkm_ipchooser import constants
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.documents import AlertDocument
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.utils.thread_backend import ThreadPool
from constants.alert import EventStatus
from constants.cmdb import TargetNodeType
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import HOST_SCENARIO, TargetFieldType
from core.drf_resource import api
from monitor.constants import AGENT_STATUS

logger = logging.getLogger(__name__)


def topo_tree(bk_biz_id):
    # api.cmdb.get_topo_tree 已开启 API 缓存并由 alarm_backends.core.api_cache.library.cmdb_api_list 每分钟刷新
    # 此处无需再设置「用户」级别的缓存 - using_cache(CacheType.CC)，两级缓存容易落后
    result = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
    return to_dict(result)


# 主机相关的信息及数据需要支持IPv6及DHCP
# 如果相关信息的获取需要保证兼容性，那么使用Host对象作为参数，否则直接使用特定字段作为参数
# 如果相关信息的获取需要保证兼容性，那么使用bk_host_id作为返回值，否则直接使用特定字段作为返回值
def get_agent_status(bk_biz_id: int, hosts: List[Host]) -> Dict[int, int]:
    """
    :summary 获取主机Agent状态及数据状态
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表（如果在外部已经获取了数据，可以只传入没有数据的主机）
    :return {bk_host_id: AGENT_STATUS}
    """
    status: Dict[int, int] = {}

    # 获取主机数据状态，查询最近三分钟
    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=bk_biz_id,
        interval=60,
        metrics=[{"field": "usage", "method": "AVG", "alias": "A"}],
        table="system.cpu_summary",
        group_by=["bk_host_id"] if is_ipv6_biz(bk_biz_id) else ["bk_target_ip", "bk_target_cloud_id"],
    )
    query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
    now = int(time.time()) * 1000
    records = query.query_data(start_time=now - 180000, end_time=now)

    # 统计已经存在数据的主机并设置状态为正常
    ip_to_host_id: Dict[Tuple, int] = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}
    for record in records:
        if record["_result_"] is None:
            continue

        bk_host_id = None
        if is_ipv6_biz(bk_biz_id) and record.get("bk_host_id"):
            bk_host_id = int(record["bk_host_id"])
        elif not is_ipv6_biz(bk_biz_id) and record.get("bk_target_ip") and record.get("bk_target_cloud_id") is not None:
            bk_host_id = ip_to_host_id.get((record["bk_target_ip"], int(record["bk_target_cloud_id"])))

        if bk_host_id:
            status[bk_host_id] = AGENT_STATUS.ON

    # 后续只查询没数据的主机
    meta = {"scope_type": constants.ScopeType.BIZ.value, "scope_id": str(bk_biz_id), "bk_biz_id": bk_biz_id}
    host_list = [{"host_id": host["bk_host_id"], "meta": meta} for host in hosts if host.bk_host_id not in status]
    scope_list = [{"scope_type": constants.ScopeType.BIZ.value, "scope_id": str(bk_biz_id)}]
    pool = ThreadPool()
    futures = []
    for index in range(0, len(host_list), 1000):
        futures.append(
            pool.apply_async(
                api.node_man.ipchooser_host_detail,
                kwds={
                    "host_list": host_list[index : index + 1000],
                    "scope_list": scope_list,
                    "agent_realtime_state": True,
                },
            )
        )
    pool.close()
    pool.join()
    result = []
    for future in futures:
        result.extend(future.get())

    for info in result:
        host_id = info["host_id"]
        if info["alive"] == 1:
            status[host_id] = AGENT_STATUS.NO_DATA

    for host in hosts:
        if host.bk_host_id not in status:
            status[host.bk_host_id] = AGENT_STATUS.NOT_EXIST

    return status


def _parse_cc_ports(ports):
    """
    解析从 CC 返回的进程端口信息
    """
    arr_ports = []
    if not ports:
        return []
    for port in ports.split(","):
        try:
            if "-" in port:
                start_port, end_port = port.split("-")
                arr_ports.extend(list(range(int(start_port), int(end_port) + 1)))
            else:
                arr_ports.append(int(port))
        except ValueError:
            pass
    return arr_ports


def get_process_info(bk_biz_id: int, hosts: List[Host], limit_port_num: int = None) -> Dict[int, List[Dict]]:
    """
    :summary 通过主机ID列表获取主机进程信息
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param limit_port_num: 限制端口数量
    """
    pp_info = defaultdict(list)

    # 如果只有一台机器，可以直接使用bk_host_id参数进行检索
    bk_host_id = None
    if len(hosts) == 1:
        bk_host_id = hosts[0].bk_host_id

    # 查询进程信息
    result = api.cmdb.get_process(bk_biz_id=bk_biz_id, bk_host_id=bk_host_id)

    # 查询进程状态数据
    statuses: Dict[int, Dict[str, int]] = get_process_status(bk_biz_id, hosts)

    bk_host_ids = {host.bk_host_id for host in hosts}
    for pp in result:
        # 按传入主机ID列表进行过滤
        if pp.bk_host_id not in bk_host_ids:
            continue

        # 端口解析&端口数量限制
        ports = _parse_cc_ports(pp.port)
        if limit_port_num:
            ports = ports[:limit_port_num]

        # 获取进程状态
        if pp.bk_host_id in statuses and pp.bk_process_name in statuses[pp.bk_host_id]:
            status = statuses[pp.bk_host_id][pp.bk_process_name]
        else:
            status = AGENT_STATUS.UNKNOWN

        pp_instance = {
            "bk_host_id": pp.bk_host_id,
            "name": pp.bk_process_name,
            "protocol": pp.protocol,
            "ports": ports,
            "status": status,
        }
        pp_info[pp.bk_host_id].append(pp_instance)

    return pp_info


def get_process_status(bk_biz_id: int, hosts: List[Host]) -> Dict[int, Dict[str, int]]:
    """
    查询进程状态
    """
    ip_to_host_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}
    bk_host_ids = {host.bk_host_id for host in hosts}

    # 查询进程端口数据
    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=bk_biz_id,
        interval=60,
        metrics=[{"field": "proc_exists", "method": "AVG", "alias": "A"}],
        table="system.proc_port",
        group_by=(["bk_host_id"] if is_ipv6_biz(bk_biz_id) else ["bk_target_ip", "bk_target_cloud_id"])
        + ["display_name"],
    )
    query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
    now = int(time.time()) * 1000
    records = query.query_data(start_time=now - 180000, end_time=now)

    # 根据返回值记录进程状态
    result = defaultdict(dict)
    for record in records:
        if record["_result_"] is None:
            continue

        if record.get("bk_host_id"):
            bk_host_id = int(record["bk_host_id"])
        else:
            bk_host_id = ip_to_host_id.get((record["bk_target_ip"], int(record["bk_target_cloud_id"])))

        if bk_host_id in bk_host_ids and record.get("display_name"):
            result[bk_host_id][record["display_name"]] = AGENT_STATUS.ON if record["_result_"] else AGENT_STATUS.OFF
    return result


def get_host_performance_data(bk_biz_id: int, hosts: List[Host] = None) -> Union[Dict[int, Dict], Dict[Tuple, Dict]]:
    """
    :summary 按主机查询主机性能信息(五分钟负载/CPU使用率/磁盘空间使用率/磁盘IO使用率/应用内存使用率)
             需要兼容基于bk_host_id或bk_target_ip的数据查询
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表 {"ip": "127.0.0.1", "bk_cloud_id": 0}
    """
    ip_to_host_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}
    bk_host_ids = {host.bk_host_id for host in hosts}

    data = {
        host.bk_host_id: {
            "cpu_load": None,
            "cpu_usage": None,
            "disk_in_use": None,
            "io_util": None,
            "mem_usage": None,
            "psc_mem_usage": None,
        }
        for host in hosts
    }

    def get_metric_data(metric, _data):
        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            interval=60,
            metrics=[{"field": metric["metric_field"], "method": "MAX", "alias": "A"}],
            table=metric["result_table_id"],
            group_by=["bk_host_id"] if is_ipv6_biz(bk_biz_id) else ["bk_target_ip", "bk_target_cloud_id"],
        )
        query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
        now = int(time.time()) * 1000
        records = query.query_data(start_time=now - 180000, end_time=now)
        for record in records:
            if not record["_result_"]:
                continue

            if record.get("bk_host_id"):
                bk_host_id = int(record["bk_host_id"])
            else:
                bk_host_id = ip_to_host_id.get((record["bk_target_ip"], int(record["bk_target_cloud_id"])))

            if bk_host_id in bk_host_ids:
                _data[bk_host_id][metric["field"]] = round(record["_result_"] * metric.get("ratio", 1), 2)

    metrics = [
        {"field": "cpu_load", "result_table_id": "system.load", "metric_field": "load5"},
        {"field": "cpu_usage", "result_table_id": "system.cpu_summary", "metric_field": "usage"},
        {"field": "disk_in_use", "result_table_id": "system.disk", "metric_field": "in_use"},
        {"field": "io_util", "result_table_id": "system.io", "metric_field": "util", "ratio": 100},
        {"field": "mem_usage", "result_table_id": "system.mem", "metric_field": "pct_used"},
        {"field": "psc_mem_usage", "result_table_id": "system.mem", "metric_field": "psc_pct_used"},
    ]

    # 根据请求总数并发请求
    pool = ThreadPool()
    for m in metrics:
        pool.apply_async(get_metric_data, args=(m, data))
    pool.close()
    pool.join()

    return data


def _get_host_strategy_target(bk_biz_id: int, scenario_list: List[str]) -> Dict[int, Dict]:
    """
    查询策略目标配置
    @param bk_biz_id: 业务ID
    @param scenario_list: 策略场景
    """
    from bkmonitor.models import ItemModel, StrategyModel

    # 查询所有主机场景的策略配置
    strategy_configs = {}
    strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, scenario__in=scenario_list).values(
        "id", "is_enabled"
    )
    for strategy in strategies:
        strategy_configs[strategy["id"]] = {"is_enabled": strategy["is_enabled"], "target": None}

    items = ItemModel.objects.filter(strategy_id__in=list(strategy_configs.keys())).values("strategy_id", "target")
    for item in items:
        strategy_configs[item["strategy_id"]]["target"] = item["target"]

    return strategy_configs


def get_topo_strategy_count(bk_biz_id: int, bk_obj_id: str, bk_inst_id: int) -> Tuple[int, int]:
    """
    查询拓扑节点关联策略数量
    """
    topo_node_id = f"{bk_obj_id}|{bk_inst_id}"
    strategy_configs = _get_host_strategy_target(bk_biz_id, HOST_SCENARIO)

    # 查询拓扑关联模板
    template_id = 0
    if bk_obj_id == "set":
        sets = api.cmdb.get_set(bk_set_ids=[bk_inst_id], bk_biz_id=bk_biz_id)
        if sets:
            template_id = getattr(sets[0], "set_template_id", 0)
    elif bk_obj_id == "module":
        modules = api.cmdb.get_module(bk_module_ids=[bk_inst_id], bk_biz_id=bk_biz_id)
        if modules:
            template_id = getattr(modules[0], "service_template_id", 0)

    enable_count, disabled_count = 0, 0
    for config in strategy_configs.values():
        target = config["target"]
        if target and target[0]:
            is_matched = False
            target_field = target[0][0]["field"]
            if target_field in [TargetFieldType.host_topo, TargetFieldType.service_topo]:
                # 主机/服务拓扑
                target_topos = {f'{obj["bk_obj_id"]}|{obj["bk_inst_id"]}' for obj in target[0][0]["value"]}
                if topo_node_id in target_topos:
                    is_matched = True
            elif (
                target_field in [TargetFieldType.host_service_template, TargetFieldType.service_service_template]
                and bk_obj_id == "module"
            ) or (
                target_field in [TargetFieldType.host_set_template, TargetFieldType.service_set_template]
                and bk_obj_id == "set"
            ):
                # 主机/服务模板
                template_ids = [template["bk_inst_id"] for template in target[0][0]["value"]]
                if template_id in template_ids:
                    is_matched = True
        else:
            is_matched = True

        if not is_matched:
            continue

        # 按照策略是否启用进行统计
        if config["is_enabled"]:
            enable_count += 1
        else:
            disabled_count += 1

    return enable_count, disabled_count


def get_host_strategy_count(bk_biz_id: int, host: Host = None) -> Tuple[int, int]:
    """
    :summary 获取主机关联策略
    :param bk_biz_id: 业务ID
    :param host: 主机
    :return 关联启用策略数 关联未启用策略数
    """
    strategy_configs = _get_host_strategy_target(bk_biz_id, HOST_SCENARIO)

    # 获得该主机所有关联拓扑
    topo_set = set()
    if host:
        host_modules = [f"module|{module}" for module in host.bk_module_ids]
        topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
        topo_link = topo_tree.convert_to_topo_link()

        for module in host_modules:
            topo_set.update({link.id for link in topo_link[module]})

    # 统计策略数量
    enabled, disabled = 0, 0
    for config in strategy_configs.values():
        target = config["target"]

        # 按主机过滤
        if host and target and target[0]:
            is_matched = False
            if target[0][0]["field"] == TargetFieldType.host_topo:
                # 动态拓扑匹配
                target_topos = {f'{obj["bk_obj_id"]}|{obj["bk_inst_id"]}' for obj in target[0][0]["value"]}
                if target_topos.intersection(topo_set):
                    is_matched = True
            elif "template" in target[0][0]["field"]:
                # 服务/集群模板匹配
                template_type = (
                    TargetNodeType.SERVICE_TEMPLATE
                    if "service" in target[0][0]["field"]
                    else TargetNodeType.SET_TEMPLATE
                )
                # TODO: 此处存多次api调用，需要优化
                template_hosts = api.cmdb.get_host_by_template(
                    dict(
                        bk_biz_id=bk_biz_id,
                        bk_obj_id=template_type,
                        template_ids=[template["bk_inst_id"] for template in target[0][0]["value"]],
                    )
                )
                if host in template_hosts:
                    is_matched = True
            else:
                # 静态IP匹配
                # TODO: 单纯通过target配置无法确定策略的实际匹配逻辑，需要优化才能保证匹配策略数的准确性
                target_values = target[0][0]["value"]
                for value in target_values:
                    # 按bk_host_id进行主机匹配
                    if "bk_host_id" in value and value["bk_host_id"] == host.bk_host_id:
                        is_matched = True
                        break

                    # 按主机进行主机匹配
                    if "bk_target_ip" in value and (value["bk_target_ip"], str(value.get("bk_target_cloud_id", 0))) == (
                        host.ip,
                        str(host.bk_cloud_id),
                    ):
                        is_matched = True
                        break
        else:
            is_matched = True

        if not is_matched:
            continue

        # 按启用/停用统计数量
        if config["is_enabled"]:
            enabled += 1
        else:
            disabled += 1

    return enabled, disabled


# 获取主机告警事件
def get_host_alarm_count(bk_biz_id: int, hosts: List[Host], days: int = 7) -> Dict[int, Dict[int, int]]:
    """
    获取主机关联告警数量，当不传主机时，统计所有主机数据
    todo: 在ipv6改造后，alert需要添加bk_host_id，该函数需要额外适配
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param days: 查询范围
    :return: Dict[ip, Dict[level, count]]
    """
    search_object = (
        AlertDocument.search(days=days)
        .filter("term", status=EventStatus.ABNORMAL)
        .filter("term", **{"event.bk_biz_id": bk_biz_id})
        .source(["event.ip", "event.bk_cloud_id", "severity"])
    )
    ip_to_host_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}

    alarm_count_info = {host.bk_host_id: {1: 0, 2: 0, 3: 0} for host in hosts}
    for alert in search_object.scan():
        try:
            ip = alert.event.ip
            bk_cloud_id = int(alert.event.bk_cloud_id)
        except (ValueError, TypeError, AttributeError):
            continue

        # 判断是否是所需主机告警
        if (ip, bk_cloud_id) not in ip_to_host_id:
            continue
        alarm_count_info[ip_to_host_id[(ip, bk_cloud_id)]][int(alert.severity)] += 1
    return alarm_count_info


def parse_topo_target(bk_biz_id: int, dimensions: List[str], target: List[Dict]) -> Optional[List[Dict]]:
    """
    根据维度解析监控目标
    :param bk_biz_id: 业务ID
    :param dimensions: 维度
    :param target: 监控目标
    """
    # 兼容策略目标格式
    if target and isinstance(target[0], list):
        if not target[0]:
            return []
        target = target[0][0]["value"]

    # 如果没有聚合任何目标字段，则不过滤目标
    is_service_instance, is_host_id, is_ip = False, False, False
    if "bk_target_service_instance_id" in dimensions or "service_instance_id" in dimensions:
        is_service_instance = True
    elif "bk_host_id" in dimensions:
        is_host_id = True
    elif "bk_target_ip" in dimensions or "ip" in dimensions:
        is_ip = True
    else:
        return []

    result = {"bk_host_id": set(), "service_instance_id": set(), "ip": defaultdict(set)}

    topo_nodes = defaultdict(list)
    service_template_id = []
    set_template_id = []
    bk_host_ids = []

    for node in target:
        if "bk_inst_id" in node and "bk_obj_id" in node:
            if node["bk_obj_id"].upper() == TargetNodeType.SERVICE_TEMPLATE:
                service_template_id.append(node["bk_inst_id"])
            elif node["bk_obj_id"].upper() == TargetNodeType.SET_TEMPLATE:
                set_template_id.append(node["bk_inst_id"])
            elif node["bk_obj_id"].upper() == "BIZ":
                return []
            else:
                topo_nodes[node["bk_obj_id"]].append(node["bk_inst_id"])
        elif ("bk_target_service_instance_id" in node or "service_instance_id" in node) and is_service_instance:
            service_instance_id = str(node.get("service_instance_id") or node["bk_target_service_instance_id"])
            result["service_instance_id"].add(service_instance_id)
        elif "bk_host_id" in node:
            if is_host_id:
                result["bk_host_id"].add(str(node["bk_host_id"]))
            else:
                bk_host_ids.append(node["bk_host_id"])
        elif ("bk_target_ip" in node or "ip" in node) and is_ip:
            ip = node.get("bk_target_ip") or node["ip"]
            bk_cloud_id = str(node.get("bk_cloud_id") or node.get("bk_target_cloud_id", 0))
            result["ip"][str(bk_cloud_id)].add(ip)

    # 处理主机ID
    if bk_host_ids:
        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=bk_host_ids)
        for host in hosts:
            result["ip"][str(host.bk_cloud_id)].add(host.bk_host_innerip)

    # 根据实例类型设置查询方法
    if is_service_instance:
        node_query_func = api.cmdb.get_service_instance_by_topo_node
        template_query_func = api.cmdb.get_service_instance_by_template
    else:
        node_query_func = api.cmdb.get_host_by_topo_node
        template_query_func = api.cmdb.get_host_by_template

    instance_nodes: List[Union[ServiceInstance, Host]] = []
    # 根据拓扑节点查询实例
    if topo_nodes:
        instance_nodes.extend(node_query_func(bk_biz_id=bk_biz_id, topo_nodes=topo_nodes))

    # 根据集群模版查询实例
    if set_template_id:
        instance_nodes.extend(
            template_query_func(
                bk_biz_id=bk_biz_id, bk_obj_id=TargetNodeType.SET_TEMPLATE, template_ids=set_template_id
            )
        )

    # 根据服务模版查询实例
    if service_template_id:
        instance_nodes.extend(
            template_query_func(
                bk_biz_id=bk_biz_id, bk_obj_id=TargetNodeType.SERVICE_TEMPLATE, template_ids=service_template_id
            )
        )

    for node in instance_nodes:
        if is_service_instance:
            result["service_instance_id"].add(str(node.service_instance_id))
        elif is_host_id:
            result["bk_host_id"].add(str(node.bk_host_id))
        elif is_ip:
            result["ip"][str(node.bk_cloud_id)].add(node.bk_host_innerip)

    # 处理返回值
    instances = []
    if is_host_id:
        instances = [{"bk_host_id": list(result["bk_host_id"])}]
    elif is_service_instance:
        if "bk_target_service_instance_id" in dimensions:
            instances = [{"bk_target_service_instance_id": list(result["service_instance_id"])}]
        else:
            instances = [{"service_instance_id": list(result["service_instance_id"])}]
    elif is_ip:
        for bk_cloud_id, ips in result["ip"].items():
            if "bk_target_ip" in dimensions:
                instance = {"bk_target_ip": list(ips)}
            else:
                instance = {"ip": list(ips)}

            if "bk_target_cloud_id" in dimensions:
                instance["bk_target_cloud_id"] = bk_cloud_id
            elif "bk_cloud_id" in dimensions:
                instance["bk_cloud_id"] = bk_cloud_id
            instances.append(instance)
    else:
        instances = []

    # 如果target有值但是没有返回，外部应返回空值，避免因过滤条件为空导致过滤失效
    if target and not instances:
        return None

    return instances
