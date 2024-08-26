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


def split_by_interval(start_time, end_time, interval):
    """根据 interval 对开始时间和结束时间进行分割"""
    if interval[-1] == "m":
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
