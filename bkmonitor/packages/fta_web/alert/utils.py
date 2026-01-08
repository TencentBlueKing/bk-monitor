"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import re

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


# 生成从 start 到 end 的每日时间段
def generate_date_ranges(start, end):
    current = datetime.fromtimestamp(start)
    while current < datetime.fromtimestamp(end):
        # 设置每天的结束时间为23:59:59
        end_of_day = datetime(current.year, current.month, current.day, 23, 59, 59)
        yield current, min(end_of_day, datetime.fromtimestamp(end))
        current += timedelta(days=1)


# 计算当日的开始时间和结束时间
def get_day_range_unix(date_str=None):
    # 解析日期字符串
    if not date_str:
        totay = datetime.now()
    else:
        totay = datetime.strptime(date_str, "%Y-%m-%d")

    # 获取当天 00:00 的时间
    start_of_day = datetime(totay.year, totay.month, totay.day)

    # 获取当天 23:59 的时间
    end_of_day = start_of_day + timedelta(hours=23, minutes=59, seconds=59)

    # 转换为 Unix 时间戳
    start_of_day_unix = int(start_of_day.timestamp())
    end_of_day_unix = int(end_of_day.timestamp())

    return start_of_day_unix, end_of_day_unix


# 生成前一周的时间
def get_previous_week_range_unix(today=None):
    # 如果未提供特定日期，则使用当前日期
    if today is None:
        today = datetime.now()

    # 计算本周的第一天（假设一周的开始是星期一）
    start_of_this_week = today - timedelta(days=today.weekday())

    # 计算上周的第一天和最后一天
    start_of_previous_week = start_of_this_week - timedelta(days=7)
    end_of_previous_week = start_of_this_week - timedelta(seconds=1)

    # 调整上周的第一天为00:00:00
    start_of_previous_week = start_of_previous_week.replace(hour=0, minute=0, second=0, microsecond=0)

    # 调整上周的最后一天为23:59:59
    end_of_previous_week = end_of_previous_week.replace(hour=23, minute=59, second=59, microsecond=0)

    # 转换为 Unix 时间戳
    start_unix_timestamp = int(start_of_previous_week.timestamp())
    end_unix_timestamp = int(end_of_previous_week.timestamp())

    return start_unix_timestamp, end_unix_timestamp


def get_previous_month_range_unix(today=None):
    # 获取当前日期
    if today is None:
        today = datetime.now()

    # 获取上个月的最后一天（即当前月的第一天减去一天）
    last_day_of_previous_month = today.replace(day=1) - relativedelta(days=1)

    # 获取上个月的第一天（即上个月最后一天的月份的第一天）

    first_day_of_previous_month = last_day_of_previous_month.replace(day=1, hour=0, minute=0, second=0)

    # 转换为 Unix 时间戳
    start_unix_timestamp = int(first_day_of_previous_month.timestamp())
    # 对于结束日期，将时间调整到当天的最后一秒
    end_of_previous_month = last_day_of_previous_month.replace(hour=23, minute=59, second=59)
    end_unix_timestamp = int(end_of_previous_month.timestamp())

    return start_unix_timestamp, end_unix_timestamp


def slice_by_interval_seconds(start_time: int, end_time: int, interval_seconds: int) -> list:
    """按固定间隔切分时间范围（ES标准左闭右开区间[start, end)）"""
    slices = []
    current = start_time

    while current < end_time:
        next_time = min(current + interval_seconds, end_time)
        slices.append((current, next_time))
        current = next_time

    return slices


def slice_time_interval(start_time: int, end_time: int) -> list:
    """智能分片：根据时间跨度选择周/日分片策略"""
    one_day = 60 * 60 * 24
    one_week = one_day * 7
    one_month = one_day * 30

    duration = end_time - start_time
    if duration > one_month or duration == one_month:
        return slice_by_interval_seconds(start_time, end_time, one_month)
    elif duration > one_week or duration == one_week:
        return slice_by_interval_seconds(start_time, end_time, one_week)
    elif duration >= one_day:
        return slice_by_interval_seconds(start_time, end_time, one_day)
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


def is_include_promql(query_string: str) -> bool:
    """
    判断是否包含promql 语句
    """
    promql_functions = [
        "abs",
        "absent",
        "absent_over_time",
        "avg",
        "avg_over_time",
        "bottomk",
        "ceil",
        "changes",
        "clamp_max",
        "clamp_min",
        "count",
        "count_over_time",
        "count_values",
        "day_of_month",
        "day_of_week",
        "days_in_month",
        "delta",
        "deriv",
        "exp",
        "floor",
        "histogram_quantile",
        "holt_winters",
        "hour",
        "idelta",
        "increase",
        "irate",
        "label_join",
        "label_replace",
        "ln",
        "log2",
        "log10",
        "max",
        "max_over_time",
        "min",
        "min_over_time",
        "minute",
        "month",
        "predict_linear",
        "quantile",
        "quantile_over_time",
        "rate",
        "resets",
        "round",
        "scalar",
        "sort",
        "sort_desc",
        "sqrt",
        "stddev",
        "stddev_over_time",
        "stdvar",
        "stdvar_over_time",
        "sum",
        "sum_over_time",
        "time",
        "timestamp",
        "topk",
        "vector",
        "year",
    ]

    # 匹配promql的函数
    function_pattern = r"\b(?:{})\b.*\(.*\)".format("|".join(promql_functions))

    # 匹配promql的时间窗口
    time_window_pattern = r"\[\d+[smhdw]\s*:\s*?(\d[smhdw])?\]"

    # 匹配promql的过滤条件
    filter_condition_pattern = r"\{.*(=|~).*\}"

    if (
        re.search(function_pattern, query_string, flags=re.IGNORECASE)
        or re.search(time_window_pattern, query_string, flags=re.IGNORECASE)
        or re.search(filter_condition_pattern, query_string, flags=re.IGNORECASE)
    ):
        return True
    return False
