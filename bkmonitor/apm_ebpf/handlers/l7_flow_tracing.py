# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import math
from collections import defaultdict

import pandas as pd
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from pandas import DataFrame

from apm_ebpf.constants import (
    FIELDS_MAP,
    L7_FLOW_TYPE_REQUEST,
    L7_FLOW_TYPE_RESPONSE,
    L7_FLOW_TYPE_SESSION,
    MERGE_KEY_REQUEST,
    MERGE_KEY_RESPONSE,
    MERGE_KEYS,
    RETURN_FIELDS,
    TAP_SIDE_CLIENT_GATEWAY,
    TAP_SIDE_CLIENT_GATEWAY_HAPERVISOR,
    TAP_SIDE_CLIENT_PROCESS,
    TAP_SIDE_LOCAL,
    TAP_SIDE_RANKS,
    TAP_SIDE_REST,
    TAP_SIDE_SERVER_GATEWAY,
    TAP_SIDE_SERVER_GATEWAY_HAPERVISOR,
    TAP_SIDE_SERVER_PROCESS,
    L7_TRACINg_LIMIT,
)

logger = logging.getLogger("apm-ebpf")


class L7FlowTracing(object):
    def __init__(self, param: dict):
        self.param = param
        self.bk_biz_id = self.param.get("bk_biz_id")
        self.start_time = self.param.get("start_time", 0)
        self.end_time = self.param.get("end_time", 0)
        self.id = self.param.get("id")
        self.max_iteration = self.param.get("max_iteration", 3)

    def query(self) -> list:
        time_filter = f'time>={self.start_time} AND time<={self.end_time}'
        base_filter = f'_id={self.id}'
        return self.trace_l7_flow(time_filter=time_filter, base_filter=base_filter)

    def trace_l7_flow(self, time_filter: str, base_filter: str) -> list:
        """L7 FlowLog 追踪入口

        参数说明：
        time_filter: 查询的时间范围过滤条件，SQL表达式
            当使用四元组进行追踪时，time_filter置为希望搜索的一段时间范围，
            当使用五元组进行追踪时，time_filter置为五元组对应流日志的start_time前后一小段时间，以提升精度
        base_filter: 查询的基础过滤条件，用于限定一个四元组或五元组
        max_iteration: 使用Flowmeta信息搜索的次数，每次搜索可认为大约能够扩充一级调用关系
        """
        l7_flow_ids = set()
        # 根据 _id 及时间范围查询当前ebpf数据
        dataframe_flow_metas = self.query_flow_metas(time_filter, base_filter)
        dataframe_flow_metas.rename(columns={"_id_str": "_id"}, inplace=True)

        # 根据 _id 查询出来的数据, 对 time_filter 进行修正, start_time_us 上下5分钟, 目的：加快搜索速度
        for i in range(self.max_iteration):
            filters = []
            # build filters
            req_tcp_seqs = set()
            resp_tcp_seqs = set()
            syscall_trace_id_requests = set()
            syscall_trace_id_responses = set()
            x_request_id_0s = set()
            x_request_id_1s = set()
            for index in dataframe_flow_metas.index:
                req_tcp_seq = dataframe_flow_metas["req_tcp_seq"][index]
                resp_tcp_seq = dataframe_flow_metas["resp_tcp_seq"][index]
                tap_side = dataframe_flow_metas["tap_side"][index]

                syscall_trace_id_request = dataframe_flow_metas["syscall_trace_id_request"][index]
                syscall_trace_id_response = dataframe_flow_metas["syscall_trace_id_response"][index]

                x_request_id_0 = dataframe_flow_metas["x_request_id_0"][index]
                x_request_id_1 = dataframe_flow_metas["x_request_id_1"][index]

                if x_request_id_0:
                    x_request_id_0s.add(f'"{x_request_id_0}"')
                if x_request_id_1:
                    x_request_id_1s.add(f'"{x_request_id_1}"')

                if syscall_trace_id_request > 0:
                    syscall_trace_id_requests.add(str(syscall_trace_id_request))
                if syscall_trace_id_response > 0:
                    syscall_trace_id_responses.add(str(syscall_trace_id_response))

                if req_tcp_seq == 0 and resp_tcp_seq == 0:
                    continue
                if tap_side not in TAP_SIDE_RANKS:
                    continue
                if req_tcp_seq:
                    req_tcp_seqs.add(str(req_tcp_seq))
                if resp_tcp_seq:
                    resp_tcp_seqs.add(str(resp_tcp_seq))

            # Network span relational query
            network_filters = []
            if req_tcp_seqs:
                network_filters.append(f'req_tcp_seq IN ({",".join(req_tcp_seqs)})')
            if resp_tcp_seqs:
                network_filters.append(f'resp_tcp_seq IN ({",".join(resp_tcp_seqs)})')
            if network_filters:
                filters.append(f'({" OR ".join(network_filters)})')

            # System span relational query
            syscall_filters = []
            if syscall_trace_id_requests or syscall_trace_id_responses:
                syscall_trace_id_requests_and_responses = list(syscall_trace_id_requests | syscall_trace_id_responses)
                syscall_filters.append(
                    f'syscall_trace_id_request IN ({",".join(syscall_trace_id_requests_and_responses)})'
                )
                syscall_filters.append(
                    f'syscall_trace_id_response IN ({",".join(syscall_trace_id_requests_and_responses)})'
                )
            if syscall_filters:
                filters.append(f'({" OR ".join(syscall_filters)})')

            # x_request_id related query
            x_request_filters = []
            if x_request_id_0s:
                x_request_filters.append(f'x_request_id_1 IN ({",".join(x_request_id_0s)})')
            if x_request_id_1s:
                x_request_filters.append(f'x_request_id_0 IN ({",".join(x_request_id_1s)})')
            if x_request_filters:
                filters.append(f'({" OR ".join(x_request_filters)})')

            new_flows = pd.DataFrame()
            if filters:
                # Non-trace_id relational queries
                new_flows = self.query_flow_metas(time_filter, " OR ".join(filters))
                new_flows.rename(columns={"_id_str": "_id"}, inplace=True)

            # Merge all flows and check if any new flows are generated
            old_flows_length = len(dataframe_flow_metas)
            dataframe_flow_metas = (
                pd.concat([dataframe_flow_metas, new_flows], join="outer", ignore_index=True)
                .drop_duplicates(["_id"])
                .reset_index(drop=True)
            )
            # L7 Flow ID信息
            l7_flow_ids |= set(dataframe_flow_metas["_id"])
            new_flows_length = len(dataframe_flow_metas)
            if old_flows_length == new_flows_length:
                break

        if not l7_flow_ids:
            return []

        # 获取追踪到的所有应用流日志
        flow_fields = list(RETURN_FIELDS)
        # 时间需要特殊处理
        l7_flows = self.query_all_flows(time_filter, list(l7_flow_ids), flow_fields)
        if l7_flows.empty:
            return []
        l7_flows.rename(columns={"_id_str": "_id"}, inplace=True)
        l7_flows = l7_flows.where(l7_flows.notnull(), None)

        # 对所有应用流日志合并
        l7_flows_merged = merge_all_flows(l7_flows, flow_fields)
        # 对所有应用流日志排序
        sort_l7_flows = sort_all_flows(l7_flows_merged)
        return data_format(sort_l7_flows)

    def query_ck(self, sql: str) -> DataFrame:
        from apm_ebpf.resource import TraceQueryResource

        ebpf_param = {"bk_biz_id": self.bk_biz_id, "sql": sql, "db": "flow_log"}
        res = TraceQueryResource().request(ebpf_param)
        if res:
            return pd.DataFrame(res)
        logger.info("apm-ebpf, query_ck, ebpf_param: {}".format(ebpf_param))
        return pd.DataFrame()

    def query_flow_metas(self, time_filter: str, base_filter: str):
        """找到base_filter对应的L7 Flowmeta

        网络流量追踪信息：
            type, req_tcp_seq, resp_tcp_seq, start_time_us, end_time_us
            通过tcp_seq及流日志的时间追踪

        系统调用追踪信息：
            vtap_id, syscall_trace_id_request, syscall_trace_id_response
            通过eBPF获取到的coroutine_trace_id追踪

        主动注入的追踪信息：
            trace_id：通过Tracing SDK主动注入的trace_id追踪
            x_request_id_0：通过Nginx/HAProxy/BFE等L7网关注入的request_id追踪
            x_request_id_1：通过Nginx/HAProxy/BFE等L7网关注入的request_id追踪
        """
        sql = """
        SELECT 
        type, req_tcp_seq, resp_tcp_seq, toUnixTimestamp64Micro(start_time) AS start_time_us, 
        toUnixTimestamp64Micro(end_time) AS end_time_us, auto_instance_0, auto_instance_1, 
        vtap_id, syscall_trace_id_request, syscall_trace_id_response, span_id, parent_span_id, l7_protocol, 
        trace_id, x_request_id_0, x_request_id_1, toString(_id) AS `_id_str`, tap_side
        FROM `l7_flow_log` 
        WHERE (({time_filter}) AND ({base_filter})) limit {l7_tracing_limit}
        """.format(
            time_filter=time_filter, base_filter=base_filter, l7_tracing_limit=L7_TRACINg_LIMIT
        )
        return self.query_ck(sql)

    def query_all_flows(self, time_filter: str, l7_flow_ids: list, return_fields: list):
        """
        根据l7_flow_ids查询所有追踪到的应用流日志
        if(is_ipv4, IPv4NumToString(ip4_0), IPv6NumToString(ip6_0)) AS ip_0,
        if(is_ipv4, IPv4NumToString(ip4_1), IPv6NumToString(ip6_1)) AS ip_1,
        toUnixTimestamp64Micro(start_time) AS start_time_us,
        toUnixTimestamp64Micro(end_time) AS end_time_us,
        """
        ids = []
        for flow_id in l7_flow_ids:
            ids.append(f'_id={flow_id}')
        fields = []
        for field in return_fields:
            if field in FIELDS_MAP:
                fields.append(FIELDS_MAP[field])
            else:
                fields.append(field)
        sql = """
        SELECT {fields} FROM `l7_flow_log` WHERE (({time_filter}) AND ({l7_flow_ids})) ORDER BY start_time_us asc
        """.format(
            time_filter=time_filter, l7_flow_ids=" OR ".join(ids), fields=",".join(fields)
        )
        return self.query_ck(sql)


def merge_flow(flows: list, flow: dict) -> bool:
    """
    只有一个请求和一个响应能合并，不能合并多个请求或多个响应；
    按如下策略合并：
    按start_time递增的顺序从前向后扫描，每发现一个请求，都找一个它后面离他最近的响应。
    例如：请求1、请求2、响应1、响应2
    则请求1和响应1配队，请求2和响应2配队
    """
    if flow["type"] == L7_FLOW_TYPE_SESSION and flow["tap_side"] not in [
        TAP_SIDE_SERVER_PROCESS,
        TAP_SIDE_CLIENT_PROCESS,
    ]:
        return False
    # vtap_id, l7_protocol, flow_id, request_id
    for i in range(len(flows)):
        if flow["_id"] == flows[i]["_id"]:
            continue
        if flow["flow_id"] != flows[i]["flow_id"]:
            continue
        if flows[i]["tap_side"] not in [TAP_SIDE_SERVER_PROCESS, TAP_SIDE_CLIENT_PROCESS]:
            if flows[i]["type"] == L7_FLOW_TYPE_SESSION:
                continue
            # 每条flow的_id最多只有一来一回两条
            if len(flows[i]["_id"]) > 1 or flow["type"] == flows[i]["type"]:
                continue
        equal = True
        request_flow = None
        response_flow = None
        if flows[i]["type"] == L7_FLOW_TYPE_REQUEST or flow["type"] == L7_FLOW_TYPE_RESPONSE:
            request_flow = flows[i]
            response_flow = flow
        elif flows[i]["type"] == L7_FLOW_TYPE_RESPONSE or flow["type"] == L7_FLOW_TYPE_REQUEST:
            request_flow = flow
            response_flow = flows[i]
        if not request_flow or not response_flow:
            continue
        for key in ["vtap_id", "tap_port", "tap_port_type", "l7_protocol", "request_id", "tap_side"]:
            if _get_df_key(request_flow, key) != _get_df_key(response_flow, key):
                equal = False
                break
        # 请求的时间必须比响应的时间小
        if request_flow["start_time_us"] > response_flow["end_time_us"]:
            equal = False
        if request_flow["tap_side"] in [TAP_SIDE_SERVER_PROCESS, TAP_SIDE_CLIENT_PROCESS]:
            # 应用span syscall_cap_seq判断合并
            if request_flow["syscall_cap_seq_0"] + 1 != response_flow["syscall_cap_seq_1"]:
                equal = False
        if equal:  # 合并字段
            # FIXME 确认要合并哪些字段

            flows[i]["_id"].extend(flow["_id"])
            flows[i]["auto_instance_0"] = flow["auto_instance_0"]
            flows[i]["auto_instance_1"] = flow["auto_instance_1"]
            flows[i]["auto_service_0"] = flow["auto_service_0"]
            flows[i]["auto_service_1"] = flow["auto_service_1"]
            for key in MERGE_KEYS:
                if key in MERGE_KEY_REQUEST:
                    if flow["type"] in [L7_FLOW_TYPE_REQUEST, L7_FLOW_TYPE_SESSION]:
                        flows[i][key] = flow[key]
                elif key in MERGE_KEY_RESPONSE:
                    if flow["type"] in [L7_FLOW_TYPE_RESPONSE, L7_FLOW_TYPE_SESSION]:
                        flows[i][key] = flow[key]
                else:
                    if not flows[i][key]:
                        flows[i][key] = flow[key]
            if flow["type"] == L7_FLOW_TYPE_REQUEST:
                if flow["start_time_us"] < flows[i]["start_time_us"]:
                    flows[i]["start_time_us"] = flow["start_time_us"]
                else:
                    if flows[i]["req_tcp_seq"] in [0, ""]:
                        flows[i]["req_tcp_seq"] = flow["req_tcp_seq"]
                flows[i]["syscall_cap_seq_0"] = flow["syscall_cap_seq_0"]
            else:
                if flow["end_time_us"] > flows[i]["end_time_us"]:
                    flows[i]["end_time_us"] = flow["end_time_us"]
                    if flows[i]["resp_tcp_seq"] in [0, ""]:
                        flows[i]["resp_tcp_seq"] = flow["resp_tcp_seq"]
                flows[i]["syscall_cap_seq_1"] = flow["syscall_cap_seq_1"]
            if flow["type"] == L7_FLOW_TYPE_SESSION:
                flows[i]["req_tcp_seq"] = flow["req_tcp_seq"]
                flows[i]["resp_tcp_seq"] = flow["resp_tcp_seq"]
            # request response合并后type改为session
            if flow["type"] + flows[i]["type"] == 1:
                flows[i]["type"] = 2
            flows[i]["type"] = max(flows[i]["type"], flow["type"])
            return True

    return False


def merge_all_flows(dataframe_flows: DataFrame, return_fields: list) -> list:
    """
    对应用流日志进行合并。

    1. 根据系统调用追踪信息追踪：
          1 -> +-----+
               |     | -> 2
               |     | <- 2
               | svc |
               |     | -> 3
               |     ! <- 3
          1 <- +-----+
       上图中的服务进程svc在接受请求1以后，向下游继续请求了2、3，他们之间的关系是：
          syscall_trace_id_request_1  = syscall_trace_id_request_2
          syscall_trace_id_response_2 = syscall_trace_id_request_3
          syscall_trace_id_response_3 = syscall_trace_id_response_1
       上述规律可用于追踪系统调用追踪信息发现的流日志。

    2. 根据主动注入的追踪信息追踪：
       主要的原理是通过x_request_id、span_id匹配追踪，这些信息穿越L7网关时保持不变。

    3. 根据网络流量追踪信息追踪：
       主要的原理是通过TCP SEQ匹配追踪，这些信息穿越L2-L4网元时保持不变。

    4. 融合1-3的结果，并将2和3中的结果合并到1中
    """
    flows = []
    # 按start_time升序，用于merge_flow
    dict_flows = dataframe_flows.sort_values(by=["start_time_us"], ascending=True).to_dict("list")
    for index in dataframe_flows.index:
        flow = {"duration": dataframe_flows["end_time_us"][index] - dataframe_flows["start_time_us"][index]}
        for key in return_fields:
            key = key.strip("")
            if key == "_id":  # 流合并后会对应多条记录
                flow[key] = [dict_flows[key][index]]
            else:
                flow[key] = dict_flows[key][index]
        if merge_flow(flows, flow):  # 合并单向Flow为会话
            continue
        flows.append(flow)
    flow_count = len(flows)
    for i, flow in enumerate(reversed(flows)):
        # 单向的c-p和s-p进行第二轮merge
        if len(flow["_id"]) > 1 or flow["tap_side"] not in [TAP_SIDE_SERVER_PROCESS, TAP_SIDE_CLIENT_PROCESS]:
            continue
        if merge_flow(flows, flow):
            del flows[flow_count - i - 1]

    return flows


def sort_all_flows(flows: list) -> list:
    """
    对应用流日志排序，用于绘制火焰图。
    """
    sort_flows = sorted(flows, key=lambda item: item["start_time_us"])
    # 网络span及系统span按照tcp_seq进行分组
    network_map = defaultdict()
    for flow in sort_flows:
        network_map.setdefault((flow["req_tcp_seq"], flow["resp_tcp_seq"]), list()).append(flow)

    # 排序
    ebpf_data = []
    for i, network in network_map.items():
        sorted_traces = network_flow_sort(network)
        ebpf_data.extend(sorted_traces)

    return ebpf_data


def data_format(l7_flow_data: list) -> list:
    # 补充trace_id, span_id
    trace_id = hex(RandomIdGenerator().generate_trace_id())
    for trace in l7_flow_data:
        if not trace.get("span_id"):
            trace["span_id"] = generate_span_id()
        trace["trace_id"] = trace_id
        trace["_id"] = trace["_id"][0]
        trace["flow_id"] = str(trace["flow_id"])
    return l7_flow_data


def _get_df_key(df: DataFrame, key: str):
    if type(df[key]) == float:
        if math.isnan(df[key]):
            return None
    return df[key]


def generate_span_id():
    return hex(RandomIdGenerator().generate_span_id())


def network_flow_sort(traces):
    """
    对网络span进行排序，排序规则：
    1. 按照TAP_SIDE_RANKS进行排序
    2. 对Local和rest就近（比较采集器）排到其他位置附近（按时间排）
    3. 网络 Span 中如 tap_side = local 或 rest 或 xx_gw 或者 tap!= 虚拟网络，则取消 tap_side 排序逻辑，改为响应时延长度倒排，
    TAP_SIDE_RANKS正排
    """
    local_rest_traces = []
    sorted_traces = []
    sys_traces = []
    response_duration_sort = False
    for trace in traces:
        if (
            trace["tap_side"]
            in [
                TAP_SIDE_LOCAL,
                TAP_SIDE_REST,
                TAP_SIDE_CLIENT_GATEWAY,
                TAP_SIDE_SERVER_GATEWAY,
                TAP_SIDE_CLIENT_GATEWAY_HAPERVISOR,
                TAP_SIDE_SERVER_GATEWAY_HAPERVISOR,
            ]
            or trace["tap"] != "虚拟网络"
        ):
            response_duration_sort = True
        if trace["tap_side"] in [TAP_SIDE_LOCAL, TAP_SIDE_REST]:
            local_rest_traces.append(trace)
        elif trace["tap_side"] in [TAP_SIDE_CLIENT_PROCESS, TAP_SIDE_SERVER_PROCESS]:
            sys_traces.append(trace)
        else:
            sorted_traces.append(trace)
    if response_duration_sort:
        sorted_traces = sorted(
            sorted_traces + local_rest_traces,
            key=lambda x: (-x["response_duration"], TAP_SIDE_RANKS.get(x["tap_side"]), x["tap_side"]),
        )
        for sys_trace in sys_traces:
            if sys_trace["tap_side"] == TAP_SIDE_CLIENT_PROCESS:
                sorted_traces.insert(0, sys_trace)
            else:
                sorted_traces.append(sys_trace)
        return sorted_traces
    sorted_traces = sorted(sorted_traces + sys_traces, key=lambda x: (TAP_SIDE_RANKS.get(x["tap_side"]), x["tap_side"]))
    if not sorted_traces:
        sorted_traces += local_rest_traces
    else:
        for trace in local_rest_traces:
            vtap_index = -1
            for i, sorted_trace in enumerate(sorted_traces):
                if vtap_index > 0 and sorted_trace["vtap_id"] != trace["vtap_id"]:
                    break
                if sorted_trace["vtap_id"] == trace["vtap_id"]:
                    if sorted_trace["start_time_us"] < trace["start_time_us"]:
                        vtap_index = i + 1
                    elif vtap_index == -1:
                        vtap_index = i
            if vtap_index >= 0:
                sorted_traces.insert(vtap_index, trace)
            else:
                for i, sorted_trace in enumerate(sorted_traces):
                    if trace["start_time_us"] < sorted_trace["start_time_us"]:
                        sorted_traces.insert(i, trace)
                        break
    return sorted_traces
