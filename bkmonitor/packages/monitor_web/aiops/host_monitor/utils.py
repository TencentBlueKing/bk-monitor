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

import time

from monitor_web.aiops.host_monitor.constant import (
    BKDATA_MIN_INTERVAL,
    DEFAULT_QUERY_ANOMALY_TIME_RANGE,
)

from bkmonitor.data_source.data_source import get_auto_interval


def build_start_time_and_end_time(start_time=None, end_time=None):
    if not end_time:
        end_time = int(time.time())
    if not start_time:
        start_time = end_time - DEFAULT_QUERY_ANOMALY_TIME_RANGE
    return start_time, end_time


def build_interval(start_time, end_time, interval):
    result_interval = 0
    if interval == "auto":
        result_interval = get_auto_interval(BKDATA_MIN_INTERVAL, start_time, end_time)
    else:
        result_interval = int(interval)
    result_interval = max(result_interval, BKDATA_MIN_INTERVAL)
    return result_interval
