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
from collections import defaultdict

from api.cmdb.define import Host, ServiceInstance, TopoTree
from bkm_ipchooser import constants
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
def get_agent_status(bk_biz_id: int, hosts: list[Host]) -> dict[int, int]:
    """
    :summary 获取主机Agent状态及数据状态
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表（如果在外部已经获取了数据，可以只传入没有数据的主机）
    :return {bk_host_id: AGENT_STATUS}
    """
    status: dict[int, int] = {}

    # 获取主机数据状态，查询最近三分钟
    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=bk_biz_id,
        interval=180,
        # usage: CPU 使用率（%），仅用于判定主机最近三分钟是否有数据上报（有上报即视为 Agent 正常）
        metrics=[{"field": "usage", "method": "AVG", "alias": "A"}],
        table="system.cpu_summary",
        group_by=["bk_host_id", "bk_target_ip", "bk_target_cloud_id"],
    )
    query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
    now = int(time.time()) * 1000
    # 仅判定最近三分钟内是否有数据上报，使用 instant 查询取窗口聚合的单点，避免拉回区间序列
    records = query.query_data(start_time=now - 180000, end_time=now, instant=True)

    # 统计已经存在数据的主机并设置状态为正常
    ip_to_host_id: dict[tuple, int] = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}
    for record in records:
        if record["_result_"] is None:
            continue

        bk_host_id = None
        if record.get("bk_host_id"):
            try:
                bk_host_id = int(record["bk_host_id"])
            except ValueError:
                pass
        if not bk_host_id:
            if record.get("bk_target_ip") and record.get("bk_target_cloud_id") is not None:
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
        try:
            result.extend(future.get())
        except Exception as e:
            logger.error("get_agent_status error: %s", e)

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


def get_process_info(bk_biz_id: int, hosts: list[Host], limit_port_num: int = None) -> dict[int, list[dict]]:
    """
    :summary 通过主机ID列表获取主机进程信息
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param limit_port_num: 限制端口数量
    :return: 以 bk_host_id 为 key 的进程信息字典，value 为该主机下的进程实例列表
        e.g.:
            {
                11: [
                    {
                        "id": 43,                       # 占位值，host.py 中按 "进程名@主机IP" 覆盖
                        "bk_host_id": 11,
                        "name": "p1",
                        "protocol": "1",
                        "ports": [80, 8080],
                        "status": 0,                     # AGENT_STATUS
                        "bindIp": "127.0.0.1",
                        "port": 80,
                        "startCommand": "/usr/bin/p1 -c /etc/p1.conf",
                        "user": "root",
                    }
                ]
            }

    """
    pp_info = defaultdict(list)

    # 如果只有一台机器，可以直接使用bk_host_id参数进行检索
    bk_host_id = None
    if len(hosts) == 1:
        bk_host_id = hosts[0].bk_host_id

    # 查询进程信息
    result = api.cmdb.get_process(bk_biz_id=bk_biz_id, bk_host_id=bk_host_id)

    # 查询进程状态数据
    statuses: dict[int, dict[str, int]] = get_process_status(bk_biz_id, hosts)

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

        # id 由 host.py 的 get_host_process_list 按 "进程名@主机IP" 格式组装（前端 ProcessItem.id 契约）。
        # 此处保留原始 bk_process_id 占位，维持 pp_instance["id"] 赋值结构，供 host.py 覆盖。
        pp_instance = {
            "id": pp.bk_process_id,
            "bk_host_id": pp.bk_host_id,
            "name": pp.bk_process_name,
            "protocol": str(pp.protocol),
            "ports": ports,
            "status": status,
            "bindIp": pp.bind_ip,
            "port": int(ports[0]) if ports else "",
            "startCommand": pp.start_cmd,
            "user": pp.user,
        }
        pp_info[pp.bk_host_id].append(pp_instance)

    return pp_info


def get_process_status(bk_biz_id: int, hosts: list[Host]) -> dict[int, dict[str, int]]:
    """
    查询进程状态，1为存活
    """
    ip_to_host_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}
    bk_host_ids = {host.bk_host_id for host in hosts}

    # 查询进程端口数据
    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=bk_biz_id,
        interval=180,
        metrics=[{"field": "proc_exists", "method": "AVG", "alias": "A"}],
        table="system.proc_port",
        group_by=(["bk_host_id", "bk_target_ip", "bk_target_cloud_id", "display_name"]),
    )
    query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
    now = int(time.time()) * 1000
    # 仅判定最近三分钟内进程是否存在，使用 instant 查询取窗口聚合的单点，避免拉回区间序列
    records = query.query_data(start_time=now - 180000, end_time=now, instant=True)

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


def _query_proc_metrics(
    bk_biz_id: int,
    hosts: list[Host],
    table: str,
    field: str,
    method: str,
    start_time: int = None,
    end_time: int = None,
):
    """
    查询 system.proc / system.proc_port 指标的公共生成器。

    封装 ip_to_host_id 构造、bk_cloud_id 归一化、时间范围计算、
    UnifyQuery 查询、record 解析等公共逻辑。

    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param table: TSDB 表名（system.proc / system.proc_port）
    :param field: 指标字段名
    :param method: 聚合方式（SUM / MAX / COUNT / MIN 等）
    :param start_time: 查询起始时间（秒级 Unix 时间戳，可选）
    :param end_time: 查询结束时间（秒级 Unix 时间戳，可选）
    :return: 生成 (bk_host_id, display_name, value) 元组，仅包含成功匹配的记录
    """
    ip_to_host_id = {(host.bk_host_innerip, int(host.bk_cloud_id or -1)): host.bk_host_id for host in hosts}
    bk_host_ids = {host.bk_host_id for host in hosts}

    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=bk_biz_id,
        interval=180,
        metrics=[{"field": field, "method": method, "alias": "A"}],
        table=table,
        group_by=["bk_host_id", "bk_target_ip", "bk_target_cloud_id", "display_name"],
    )
    query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
    if start_time is not None and end_time is not None:
        query_start = int(start_time) * 1000
        query_end = int(end_time) * 1000
    else:
        now = int(time.time()) * 1000
        query_start = now - 180000
        query_end = now
    records = query.query_data(start_time=query_start, end_time=query_end, instant=True)
    for record in records:
        if record.get("_result_") is None:
            continue
        if record.get("bk_host_id"):
            bk_host_id = int(record["bk_host_id"])
        else:
            bk_host_id = ip_to_host_id.get((record.get("bk_target_ip"), int(record.get("bk_target_cloud_id") or -1)))
        if bk_host_id in bk_host_ids and record.get("display_name"):
            yield bk_host_id, record["display_name"], record.get("_result_")


def get_process_runtime_metrics(
    bk_biz_id: int, hosts: list[Host], start_time: int = None, end_time: int = None
) -> dict[str, dict]:
    """
    查询进程运行时指标 (system.proc)

    返回各进程指标字段的运行时数据：
    - 指标字段（SUM 聚合）：cpu_usage_pct, mem_res, mem_usage_pct, fd_num
    - uptime 因语义不可加（多实例时长求和无意义），已拆分至 get_process_uptime 单独查询（MIN 聚合）

    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param start_time: 查询起始时间（秒级 Unix 时间戳，可选）。与 end_time 同时传入时约束查询区间。
    :param end_time: 查询结束时间（秒级 Unix 时间戳，可选）。不传或仅传一个时退化为默认"最近三分钟"。
    :return: 以 bk_host_id 为一级 key、进程 display_name（进程名）为二级 key 的运行时指标字典，
        三级 key 为指标字段（cpu_usage_pct/mem_res/mem_usage_pct/fd_num）
        e.g.:
            {
                11: {
                    "nginx": {"cpu_usage_pct": 2.5, "mem_res": 102400, "mem_usage_pct": 10.0, "fd_num": 64},
                    "redis": {"cpu_usage_pct": 5.0, "mem_res": 204800, "mem_usage_pct": 20.0, "fd_num": 128}
                }
            }
    """
    try:
        # system.proc 指标字段（SUM 聚合）
        # - cpu_usage_pct: 进程 CPU 使用率（%）
        # - mem_res:       进程使用的物理内存（字节）
        # - mem_usage_pct: 进程内存使用率（%）
        # - fd_num:        进程文件句柄数
        # 注意：uptime 已拆分至 get_process_uptime（MAX 聚合），不在此处 SUM
        METRIC_FIELDS = ["cpu_usage_pct", "mem_res", "mem_usage_pct", "fd_num"]

        result = defaultdict(lambda: defaultdict(dict))

        def get_metric_data(field):
            # 每个线程写入独立的临时 dict，避免多线程并发写同一 defaultdict 的竞态
            _local = defaultdict(lambda: defaultdict(dict))
            for bk_host_id, display_name, value in _query_proc_metrics(
                bk_biz_id, hosts, "system.proc", field, "SUM", start_time, end_time
            ):
                _local[bk_host_id][display_name][field] = value
            return _local

        # 根据指标字段数量并发请求，单字段失败仅丢弃该字段（设计文档 §1 稳健性要求）。
        # apply_async 的异常仅在 AsyncResult.get() 时抛出，故逐字段 try/except 捕获。
        # 合并在主线程顺序执行，规避多线程写共享 result 的竞态。
        pool = ThreadPool()
        futures = [pool.apply_async(get_metric_data, args=(field,)) for field in METRIC_FIELDS]
        pool.close()
        for field, future in zip(METRIC_FIELDS, futures):
            try:
                field_data = future.get()
            except Exception as e:
                logger.warning("get_process_runtime_metrics field %s failed, skip: %s", field, e)
                continue
            for host_id, proc_map in field_data.items():
                for proc_name, metrics in proc_map.items():
                    result[host_id][proc_name].update(metrics)
        pool.join()

        return result
    except Exception as e:
        # 设计文档 §1：TSDB 查询异常兜底，runtime_data={}，CMDB 基础字段照常返回
        logger.warning("get_process_runtime_metrics failed, degrade to empty: %s", e)
        return {}


def get_process_uptime(
    bk_biz_id: int, hosts: list[Host], start_time: int = None, end_time: int = None
) -> dict[int, dict[str, float]]:
    """
    查询进程运行时长（system.proc uptime，MIN 聚合）

    uptime 为时长不可加（多实例求和无意义），使用 MAX 取窗口内最长运行实例的运行时长。
    instant=True 即时计算，直接返回最新时刻的聚合值。

    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param start_time: 查询起始时间（秒级 Unix 时间戳，可选）。与 end_time 同时传入时约束查询区间。
    :param end_time: 查询结束时间（秒级 Unix 时间戳，可选）。不传或仅传一个时退化为默认"最近三分钟"。
    :return: {bk_host_id: {display_name: uptime(秒)}}
        无对应数据时该 bk_host_id 不下发（返回空 dict 兜底）。
    """
    try:
        result = defaultdict(dict)
        for bk_host_id, display_name, value in _query_proc_metrics(
            bk_biz_id, hosts, "system.proc", "uptime", "MAX", start_time, end_time
        ):
            result[bk_host_id][display_name] = value
        return result
    except Exception as e:
        # TSDB 查询异常兜底，uptime 缺失不影响其他运行时指标
        logger.warning("get_process_uptime failed, degrade to empty: %s", e)
        return {}


def get_process_instance_count(
    bk_biz_id: int, hosts: list[Host], start_time: int = None, end_time: int = None
) -> dict[int, dict[str, int]]:
    """
    查询进程真实运行实例数（按 pid 维度 COUNT 聚合）

    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param start_time: 查询起始时间（秒级 Unix 时间戳，可选）。与 end_time 同时传入时约束查询区间。
    :param end_time: 查询结束时间（秒级 Unix 时间戳，可选）。
    :return: {bk_host_id: {进程 display_name: 实例数}}
        其中实例数为该主机上该进程按 pid 维度 COUNT 聚合的运行实例数；
        无对应数据时该 bk_host_id 不下发（返回空 dict 兜底）。
        示例::

            {
                101: {"nginx": 3, "mysql": 1},
                102: {"redis": 2},
            }
    """
    try:
        result = defaultdict(dict)
        for bk_host_id, display_name, value in _query_proc_metrics(
            bk_biz_id, hosts, "system.proc", "cpu_usage_pct", "COUNT", start_time, end_time
        ):
            # 一条有数据的 pid series 即代表一个运行实例
            result[bk_host_id][display_name] = value
        return result
    except Exception as e:
        # 设计文档 §1：TSDB 查询异常兜底，实例数缺失不影响其他运行时指标
        logger.warning("get_process_instance_count failed, degrade to empty: %s", e)
        return {}


def get_process_port_health(
    bk_biz_id: int, hosts: list[Host], start_time: int = None, end_time: int = None
) -> dict[int, dict[str, int]]:
    """
    查询进程端口健康状态 (port_health)

    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param start_time: 查询起始时间（秒级 Unix 时间戳，可选）。与 end_time 同时传入时约束查询区间。
    :param end_time: 查询结束时间（秒级 Unix 时间戳，可选）。不传或仅传一个时退化为默认"最近三分钟"。
    :return: {bk_host_id: {display_name: 0/1}}
        其中 0=Normal(健康), 1=Abnormal(异常)；
        无对应数据(TSDB 无上报或未解析)的进程不会出现在结果中(即缺失=未知)。
    """
    try:
        result = defaultdict(dict)
        for bk_host_id, display_name, value in _query_proc_metrics(
            bk_biz_id, hosts, "system.proc_port", "port_health", "MIN", start_time, end_time
        ):
            # TSDB port_health: 1=健康, 0=异常；前端 PROCESS_PORT_STATUS_MAP: 0=Normal(绿), 1=Abnormal(红)
            # 在此做枚举映射并二值化为 int，避免透传浮点导致前端 MAP 落灰
            result[bk_host_id][display_name] = 0 if value else 1
        return result
    except Exception as e:
        # 设计文档 §1：TSDB 查询异常兜底，port_health={}，CMDB 基础字段照常返回
        logger.warning("get_process_port_health failed, degrade to empty: %s", e)
        return {}


def get_host_performance_data(bk_biz_id: int, hosts: list[Host] = None) -> dict[int, dict] | dict[tuple, dict]:
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

    def get_metric_data(metric):
        # 每个线程写入独立的临时 dict，避免多线程并发写同一 data 的竞态
        local = {}
        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            interval=180,
            metrics=[{"field": metric["metric_field"], "method": "MAX", "alias": "A"}],
            table=metric["result_table_id"],
            group_by=["bk_host_id", "bk_target_ip", "bk_target_cloud_id"],
        )
        query = UnifyQuery(data_sources=[data_source], bk_biz_id=bk_biz_id, expression="a")
        now = int(time.time()) * 1000
        records = query.query_data(start_time=now - 180000, end_time=now, instant=True)
        for record in records:
            if not record["_result_"]:
                continue

            if record.get("bk_host_id"):
                bk_host_id = int(record["bk_host_id"])
            else:
                bk_host_id = ip_to_host_id.get((record["bk_target_ip"], int(record["bk_target_cloud_id"])))

            if bk_host_id in bk_host_ids:
                local[bk_host_id] = round(record["_result_"] * metric.get("ratio", 1), 2)
        return local

    metrics = [
        {"field": "cpu_load", "result_table_id": "system.load", "metric_field": "load5"},
        {"field": "cpu_usage", "result_table_id": "system.cpu_summary", "metric_field": "usage"},
        {"field": "disk_in_use", "result_table_id": "system.disk", "metric_field": "in_use"},
        {"field": "io_util", "result_table_id": "system.io", "metric_field": "util", "ratio": 100},
        {"field": "mem_usage", "result_table_id": "system.mem", "metric_field": "pct_used"},
        {"field": "psc_mem_usage", "result_table_id": "system.mem", "metric_field": "psc_pct_used"},
    ]

    # 根据请求总数并发请求，单指标失败仅丢弃该指标（不影响其余指标）。
    # apply_async 的异常仅在 AsyncResult.get() 时抛出，故逐指标 try/except 捕获，
    # 避免旧实现只 pool.join() 静默吞掉线程异常、返回不完整性能数据的问题。
    # 合并在主线程顺序执行，规避多线程写共享 data 的竞态。
    pool = ThreadPool()
    futures = [pool.apply_async(get_metric_data, args=(m,)) for m in metrics]
    pool.close()
    for metric, future in zip(metrics, futures):
        try:
            metric_data = future.get()
        except Exception as e:
            logger.warning("get_host_performance_data metric %s failed, skip: %s", metric["field"], e)
            continue
        for host_id, value in metric_data.items():
            data[host_id][metric["field"]] = value
    pool.join()

    return data


def _get_host_strategy_target(bk_biz_id: int, scenario_list: list[str]) -> dict[int, dict]:
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


def get_topo_strategy_count(bk_biz_id: int, bk_obj_id: str, bk_inst_id: int) -> tuple[int, int]:
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
                target_topos = {f"{obj['bk_obj_id']}|{obj['bk_inst_id']}" for obj in target[0][0]["value"]}
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


def get_host_strategy_count(bk_biz_id: int, host: Host = None) -> tuple[int, int]:
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
                target_topos = {f"{obj['bk_obj_id']}|{obj['bk_inst_id']}" for obj in target[0][0]["value"]}
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
def get_host_alarm_count(bk_biz_id: int, hosts: list[Host], days: int = 7) -> dict[int, dict[int, int]]:
    """
    获取主机关联告警数量，当不传主机时，统计所有主机数据
    todo: 在ipv6改造后，alert需要添加bk_host_id，该函数需要额外适配
    支持两种匹配方式（按优先级）：
    1. event.ip + event.bk_cloud_id 匹配（传统主机告警）
    2. dimensions 中提取 ip + bk_cloud_id 匹配（K8s告警）
    :param bk_biz_id: 业务ID
    :param hosts: 主机列表
    :param days: 查询范围
    :return: Dict[bk_host_id, Dict[severity, count]]
    """
    search_object = (
        AlertDocument.search(days=days)
        .filter("term", status=EventStatus.ABNORMAL)
        .filter("term", **{"event.bk_biz_id": bk_biz_id})
        .source(["event.ip", "event.bk_cloud_id", "severity", "dimensions"])
    )
    ip_to_host_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_id for host in hosts}

    alarm_count_info = {host.bk_host_id: {1: 0, 2: 0, 3: 0} for host in hosts}
    for alert in search_object.scan():
        host_id = _resolve_host_id_from_alert(alert, ip_to_host_id)
        if host_id is None:
            continue
        alarm_count_info[host_id][int(alert.severity)] += 1
    return alarm_count_info


def _resolve_host_id_from_alert(alert, ip_to_host_id: dict[tuple, int]) -> int | None:
    """
    从告警中解析出 bk_host_id，支持多种匹配方式。
    :return: bk_host_id 或 None（无法匹配）
    """
    # 优先级1：event.ip + event.bk_cloud_id 匹配（传统主机告警）
    try:
        ip = alert.event.ip
        bk_cloud_id = int(alert.event.bk_cloud_id)
        if ip and (ip, bk_cloud_id) in ip_to_host_id:
            return ip_to_host_id[(ip, bk_cloud_id)]
    except (ValueError, TypeError, AttributeError):
        pass

    # 优先级2：从 dimensions 中提取（K8s 告警通过 KubernetesCMDBEnricher 写入）
    try:
        dimensions = alert.dimensions or []
        dim_map = {}
        for dim in dimensions:
            key = getattr(dim, "key", None)
            value = getattr(dim, "value", None)
            if key and value is not None:
                dim_map[key] = value

        # dimensions 中的 ip + bk_cloud_id 匹配
        if "ip" in dim_map and "bk_cloud_id" in dim_map:
            ip = dim_map["ip"]
            bk_cloud_id = int(dim_map["bk_cloud_id"])
            if (ip, bk_cloud_id) in ip_to_host_id:
                return ip_to_host_id[(ip, bk_cloud_id)]
    except (ValueError, TypeError, AttributeError):
        pass

    return None


def parse_topo_target(bk_biz_id: int, dimensions: list[str], target: list[dict]) -> list[dict] | None:
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
    dynamic_group_ids = []

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
        elif "dynamic_group_id" in node:
            dynamic_group_ids.append(node["dynamic_group_id"])

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

    instance_nodes: list[ServiceInstance | Host] = []
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

    # 根据动态分组查询主机
    if dynamic_group_ids and (is_ip or is_host_id):
        dynamic_group_hosts = api.cmdb.batch_execute_dynamic_group(
            bk_biz_id=bk_biz_id, ids=dynamic_group_ids, bk_obj_id="host"
        )
        for dynamic_group_host in dynamic_group_hosts.values():
            instance_nodes.extend(dynamic_group_host)

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
