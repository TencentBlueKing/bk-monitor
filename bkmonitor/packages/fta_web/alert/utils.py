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
import copy
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

from elasticsearch_dsl import Q


def get_previous_month_range_unix(today=None):
    # 获取当前日期
    if today is None:
        today = datetime.now()
    
    # 获取上个月的最后一天（即当前月的第一天减去一天）
    last_day_of_previous_month = today.replace(day=1) - relativedelta(days=1)
    
    # 获取上个月的第一天（即上个月最后一天的月份的第一天）
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)
    
    # 格式化日期为 YYYYMMDD
    first_day_str = first_day_of_previous_month.strftime('%Y%m%d')
    last_day_str = last_day_of_previous_month.strftime('%Y%m%d')
    
    # 转换为 Unix 时间戳
    start_unix_timestamp = int(first_day_of_previous_month.timestamp())
    # 对于结束日期，将时间调整到当天的最后一秒
    end_of_previous_month = last_day_of_previous_month.replace(hour=23, minute=59, second=59)
    end_unix_timestamp = int(end_of_previous_month.timestamp())
    
    return start_unix_timestamp, end_unix_timestamp


def slice_by_interval_seconds(start_time: int, end_time: int, interval_seconds: int) -> list:
    """按天或周切分时间，返回每一天或每一周的起始和结束时间戳"""
    days = []
    current_time = start_time
    while current_time < end_time:
        next_day_time = current_time + interval_seconds
        days.append((current_time, min(next_day_time - 1, end_time)))
        current_time = next_day_time
    return days


def slice_time_interval(start_time: int, end_time: int) -> list:
    """根据时间间隔分片，并返回起始和结束时间戳"""
    ONE_DAY_SECONDS = 86400
    ONE_WEEK_SECONDS = 604800
    duration = end_time - start_time

    if duration > ONE_WEEK_SECONDS:
        return slice_by_interval_seconds(start_time, end_time, ONE_WEEK_SECONDS)
    elif duration > ONE_DAY_SECONDS:
        return slice_by_interval_seconds(start_time, end_time, ONE_DAY_SECONDS)
    else:
        return [(start_time, end_time)]


def add_overview(result: dict, sliced_result: dict):
    if "overview" not in result.keys():
        result["overview"] = {
            "id": sliced_result["overview"]["id"],
            "name": sliced_result["overview"]["name"],
            "count": 0,
            "children": {},
        }
    result["overview"]["count"] += sliced_result["overview"]["count"]
    for child in sliced_result["overview"]["children"]:
        child_id = child["id"]
        if child_id not in result["overview"]["children"]:
            result["overview"]["children"][child_id] = {"id": child["id"], "name": child["name"], "count": 0}
        result["overview"]["children"][child_id]["count"] += child["count"]


def add_aggs(agg_id_map: dict, result: dict, sliced_result: dict):
    for agg in sliced_result["aggs"]:
        if agg["id"] not in agg_id_map:
            new_agg = copy.deepcopy(agg)
            result["aggs"].append(new_agg)
            agg_id_map[agg["id"]] = len(result["aggs"]) - 1
        else:
            index = agg_id_map[agg["id"]]
            result["aggs"][index]["count"] += agg["count"]
            for child in agg["children"]:
                for res_child in result["aggs"][index]["children"]:
                    if res_child["id"] == child["id"]:
                        res_child["count"] += child["count"]


def process_stage_string(query_string):
    """
    将query_string中的处理阶段信息替换为英文字段名
    example:
    >> process_stage_string('处理阶段 : 已通知 AND 告警名称 : "VMStorage内存使用率" OR 状态 : 未恢复')
    >> 'is_handled : true AND 告警名称 : "VMStorage内存使用率" OR 状态 : 未恢复'
    >>
    >> process_stage_string('(((-处理阶段 : 已通知 )) AND 处理阶段 : 已流控) AND -指标ID : "bk_log_search.index_set.53"')
    >>'((( is_handled : false )) AND is_blocked : true ) AND -指标ID : "bk_log_search.index_set.53"'
    """
    stage_mapping = {
        "已通知": "is_handled",
        "已确认": "is_ack",
        "已屏蔽": "is_shielded",
        "已流控": "is_blocked",
        "is_handled": "is_handled",
        "is_ack": "is_ack",
        "is_shielded": "is_shielded",
        "is_blocked": "is_blocked",
    }

    pattern = fr"(?P<prefix>-|not|)\s*(处理阶段|stage)\s*:\s*(?P<stage>{'|'.join(stage_mapping.keys())})"
    # 遍历所有匹配到的处理阶段信息
    for _ in re.findall(pattern, query_string, re.IGNORECASE):
        match = re.search(pattern, query_string, re.IGNORECASE)
        value = "false" if match.group("prefix") else "true"
        stage = match.group("stage")
        start, end = match.span()
        # 将查询字符串中的处理阶段信息替换为映射后的英文字段名和对应的值
        query_string = query_string[:start] + f" {stage_mapping[stage]} : {value} " + query_string[end:]

    # 去除查询字符串中的多余空白字符，并去除首尾的空白字符
    query_string = re.sub(r"\s+", " ", query_string).strip()
    return query_string


def parse_query_str(query_str: str) -> Q:
    """解析查询字符串，指标ID支持模糊查询，并将其转换为 Elasticsearch 查询对象"""

    def _parse(query_str):
        """递归解析嵌套的 AND 和 OR 条件"""
        # 先处理 OR 条件
        if "OR" in query_str:
            or_conditions = [cond.strip() for cond in query_str.split("OR")]
            return Q('bool', should=[_parse(cond) for cond in or_conditions], minimum_should_match=1)

        # 处理 AND 条件
        and_conditions = [cond.strip() for cond in query_str.split("AND")]
        must_queries = []
        for condition in and_conditions:
            field, value = re.split(r":", condition)
            field = field.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            # 如果是 event.metric 字段，则使用 wildcard 模糊查询
            if field == "event.metric":
                must_queries.append(Q("wildcard", **{field: f"*{value}*"}))
            else:
                # 其他字段使用 term 精确查询
                must_queries.append(Q("term", **{field: value}))

        return Q("bool", must=must_queries)

    return _parse(query_str)
