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
