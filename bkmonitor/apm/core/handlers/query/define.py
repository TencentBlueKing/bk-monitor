# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from dataclasses import dataclass


@dataclass
class TraceInfoList:
    total: int
    data: list


class QueryMode:
    """查询视角 Trace/Span"""

    TRACE = "trace"
    ORIGIN_TRACE = "origin_trace"
    SPAN = "span"


class QueryStatisticsMode:
    """查询统计视角 SpanName/Service"""

    SPAN_NAME = "span_name"
    SERVICE = "service"
