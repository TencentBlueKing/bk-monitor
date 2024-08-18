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
from bkmonitor.utils.enum import ChoicesEnum


class StatisticsMetric(ChoicesEnum):
    """支持进行统计的 metric 指标"""

    REQUEST_COUNT = "request_count"
    ERROR_COUNT = "error_count"
    AVG_DURATION = "avg_duration"

    _choices_labels = (
        (REQUEST_COUNT, "请求数"),
        (ERROR_COUNT, "错误数"),
        (AVG_DURATION, "平均耗时"),
    )
