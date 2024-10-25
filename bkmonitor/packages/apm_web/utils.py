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
import datetime
import math

from core.drf_resource import api


def list_remote_service_callers(bk_biz_id, app_name, remote_service_name):
    """获取自定义服务所有主调服务方"""
    response = api.apm_api.query_topo_relation(bk_biz_id=bk_biz_id, app_name=app_name, to_topo_key=remote_service_name)

    return list({i["from_topo_key"] for i in response})


def get_time_period(start_time, end_time):
    """
    获取时间间隔
    """
    interval = end_time - start_time

    return int(interval / 60), "minute"


def span_time_strft(timestamp) -> str:
    return datetime.datetime.fromtimestamp(int(timestamp // 1000000)).strftime('%Y-%m-%d %H:%M:%S')


def handle_filter_fields(data, filter_fields, value_getter=lambda k, i: i):
    """
    从data列表找到符合filter_fields所有值的item，将其移动至data的第一位
    """
    hit_item = None
    for i in data:
        eq_len = 0
        for key, v in filter_fields.items():
            if value_getter(key, i.get(key)) == v:
                eq_len += 1

        if eq_len == len(filter_fields.keys()):
            hit_item = data.index(i)
            break

    if hit_item is None:
        return data

    return [data.pop(hit_item)] + data


def percentile(data, perc: int):
    """
    P95 P50计算函数
    """
    size = len(data)
    return sorted(data)[int(math.ceil((size * perc) / 100)) - 1]


"""常用的lambda计算函数"""


class Calculator:
    @classmethod
    def avg(cls):
        return lambda i: round(sum(i) / len(i), 2) if len(i) else 0

    @classmethod
    def sum(cls):
        return sum


def get_interval(start_time, end_time, interval="auto"):
    """计算出适合的时间间隔"""
    if not interval or interval == "auto":
        hour_interval = (end_time - start_time) // 3600
        if hour_interval <= 1:
            interval = "1m"
        elif hour_interval <= 3:
            interval = "5m"
        elif hour_interval <= 5:
            interval = "10m"
        elif hour_interval <= 7:
            interval = "15m"
        elif hour_interval <= 72:
            interval = "1h"
        else:
            interval = "1d"

    return interval


def get_interval_number(start_time, end_time, interval="auto"):
    """计算出适合的时间间隔返回 int"""
    if not interval or interval == "auto":
        hour_interval = (end_time - start_time) // 3600
        if hour_interval <= 1:
            interval = 60
        elif hour_interval <= 3:
            interval = 60 * 5
        elif hour_interval <= 5:
            interval = 60 * 10
        elif hour_interval <= 7:
            interval = 60 * 15
        elif hour_interval <= 72:
            interval = 60 * 60
        else:
            interval = 60 * 60 * 24

        return interval

    return 60 if not isinstance(interval, int) else interval


def get_bar_interval_number(start_time, end_time, size=30):
    """计算出柱状图（特殊处理的）的 interval 固定柱子数量"""
    # 最低聚合为一分钟
    c = (end_time - start_time) / 60
    if c < size:
        return 60

    return int((end_time - start_time) // size)


def split_by_size(start_time, end_time, size=30):
    """切分开始时间和结束时间，按照个数返回"""
    start_dt = datetime.datetime.fromtimestamp(start_time)
    end_dt = datetime.datetime.fromtimestamp(end_time)

    total_duration = end_dt - start_dt
    segment_duration = total_duration / size

    segments = []

    for index, i in enumerate(range(size), -1):
        segment_start = start_dt + segment_duration * index
        segment_end = segment_start + segment_duration
        segments.append((int(segment_start.timestamp()), int(segment_end.timestamp())))

    return segments


def split_by_interval(start_time, end_time, interval):
    """根据 interval 对开始时间和结束时间进行分割"""
    if interval[-1] == "s":
        interval_seconds = int(interval[:-1])
    elif interval[-1] == "m":
        interval_seconds = int(interval[:-1]) * 60
    elif interval[-1] == "h":
        interval_seconds = int(interval[:-1]) * 3600
    elif interval[-1] == "d":
        interval_seconds = int(interval[:-1]) * 86400
    else:
        raise ValueError("Invalid interval format")

    start_time = datetime.datetime.fromtimestamp(start_time)
    end_time = datetime.datetime.fromtimestamp(end_time)

    if start_time.second != 0:
        start_time = start_time.replace(second=0)

    if end_time.second != 0:
        end_time += datetime.timedelta(minutes=1)
        end_time = end_time.replace(second=0)

    split_points = []
    current_time = start_time
    while current_time + datetime.timedelta(seconds=interval_seconds) <= end_time:
        next_time = current_time + datetime.timedelta(seconds=interval_seconds)
        split_points.append([int(current_time.timestamp()), int(next_time.timestamp())])
        current_time = next_time

    if split_points:
        min_time = split_points[0][0]
        max_time = split_points[-1][1]
    else:
        min_time = max_time = None

    return split_points, min_time, max_time


def divide_biscuit(iterator, interval):
    """分段"""
    for i in range(0, len(iterator), interval):
        yield iterator[i : i + interval]


def merge_dicts(d1, d2):
    """递归合并字典"""
    merged = d1.copy()
    for key, value in d2.items():
        if key in merged:
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge_dicts(merged[key], value)
            else:
                # 如果不是字典 直接覆盖
                merged[key] = value
        else:
            merged[key] = value
    return merged


def fill_series(series, start_time, end_time, interval):
    """
    调整时间戳 将无数据的柱子值设置为 None (适用于柱状图查询)
    """
    interval = interval * 1000
    default_size = 30
    c = int(math.ceil((end_time - start_time) / 60))
    size = default_size if c > default_size else c

    timestamp_range = [(a * 1000, b * 1000) for a, b in split_by_size(start_time, end_time, size=size)]

    if not series:
        return [{"datapoints": [[None, int((s + e) / 2)] for s, e in timestamp_range]}]

    res = []

    for i in series:
        result = [[None, int((t_e + t_s) / 2)] for t_e, t_s in timestamp_range]
        dps = i["datapoints"]

        for j, (value, timestamp) in enumerate(dps):
            # 如果当前数据点落在此 time_range 区间 补充数据点
            for k, (start, end) in enumerate(timestamp_range):
                if start <= timestamp <= end:
                    result[k] = [value, timestamp]
                    break

            # 检查前一个时间点是否存在且与当前时间点之间的间隔大于 interval 如果不是则不补充空数据避免图表出现断点
            if j > 0:
                prev_timestamp = dps[j - 1][1]
                if timestamp - prev_timestamp > interval:
                    # 插入空数据点
                    empty_count = (timestamp - prev_timestamp) // interval - 1
                    for m in range(1, empty_count + 1):
                        missing_timestamp = prev_timestamp + m * interval
                        for n, (start, end) in enumerate(timestamp_range):
                            if start <= missing_timestamp <= end:
                                result[n] = [None, missing_timestamp]
                                break

        if len(result) < default_size:
            first_timestamp = result[0][1] if result[0][0] is not None else start_time
            last_timestamp = result[-1][1] if result[-1][0] is not None else end_time

            # 头部插入
            while len(result) < default_size and first_timestamp > start_time:
                first_timestamp -= interval
                result.insert(0, [None, first_timestamp])

            # 尾部插入
            while len(result) < default_size and last_timestamp < end_time:
                last_timestamp += interval
                result.append([None, last_timestamp])

        res.append(
            {
                **i,
                "datapoints": result,
            }
        )

    return res
