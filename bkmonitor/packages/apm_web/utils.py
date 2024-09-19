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


def group_by(iterators, get_key):
    res = {}
    for item in iterators:
        key = get_key(item)
        if not key:
            continue

        if key in res:
            res[key].append(item)
        else:
            res[key] = [item]

    return res


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


def fill_series(series, start_time, end_time):
    """
    调整时间戳 将无数据的柱子值设置为 None (适用于柱状图查询)
    """
    # 检查按照最低一分钟聚合的话 是否少于默认数量 30个 如果小于则需要按照原本的数量进行切分
    default_size = 30
    c = int(math.ceil((end_time - start_time) / 60))
    size = default_size if c > default_size else c

    timestamp_range = split_by_size(start_time, end_time, size=size)
    if not series:
        return [{"datapoints": [[None, int((s + e) / 2) * 1000] for s, e in timestamp_range]}]

    res = []
    for i in series:
        result = [[None, int((t_e + t_s) / 2) * 1000] for t_e, t_s in timestamp_range]
        # 如果数据点数量比切分的时间范围数量大 说明有数据点不能放入时间范围中 去掉尾部元素
        dps = (
            i["datapoints"] if len(i["datapoints"]) <= len(timestamp_range) else i["datapoints"][: len(timestamp_range)]
        )
        for j, d in enumerate(dps):
            value, timestamp = d
            if j > 0:
                # 往前移动被覆盖元素
                # 这里的情况可能是 UnifyQuery 返回的前 n 个元素 比 timestamp_range 中 n-1 位的开始时间要小的问题
                # 所以这个 n 位元素应该放在 n-1 位 需要整个 time_range 往前移动
                if timestamp_range[j - 1][0] <= timestamp <= timestamp_range[j - 1][1]:
                    result[j - 1] = d
                    result[j - 2] = i["datapoints"][j - 1]
                    continue

            if result[j][0] is None:
                result[j] = d

        res.append(
            {
                **i,
                "datapoints": sorted(result, key=lambda t: t[-1]),
            }
        )

    return res
