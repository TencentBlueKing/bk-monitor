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
from enum import Enum


class ETLConfig(Enum):
    """场景类型

    TODO: 确认包含场景类型
    """

    ALL = "all"
    TRACE = "trace"
    METRIC = "metric"
    LOG = "log"
    APM = "apm"
    EVENT = "event"
    ALERT = "alert"

    _choices_labels = (
        (ALL, "all"),
        (TRACE, "trace"),
        (METRIC, "metric"),
        (LOG, "log"),
        (APM, "apm"),
        (EVENT, "event"),
        (ALERT, "alert"),
    )


# 默认每页的大小
DEFAULT_PAGE_SIZE = 10
# 默认第一页
MIN_PAGE_NUM = 1
