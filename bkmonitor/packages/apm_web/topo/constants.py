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
from django.utils.translation import ugettext_lazy as _

from bkmonitor.utils.enum import ChoicesEnum


class BarChartDataType(ChoicesEnum):
    """拓扑图数据类型"""

    Apdex = "apdex"
    Alert = "alert"
    ErrorRateCaller = "error_rate_caller"
    ErrorRateCallee = "error_rate_callee"
    ErrorRate = "error_rate"

    REQUEST_COUNT = "request_count"
    REQUEST_COUNT_CALLER = "request_count_caller"
    REQUEST_COUNT_CALLEE = "request_count_callee"
    AVG_DURATION_CALLER = "avg_duration_caller"
    AVG_DURATION_CALLEE = "avg_duration_callee"
    INSTANCE_COUNT = "instance_count"

    # 下拉框选项共下面五项
    _choices_labels = (
        (Apdex, _("apdex")),
        (Alert, _("告警事件")),
        (ErrorRateCaller, _("主调错误率")),
        (ErrorRateCallee, _("被调错误率")),
        (ErrorRate, _("错误率")),
    )


class TopoEdgeDataType(ChoicesEnum):
    """拓扑图连接线数据类型"""

    REQUEST_COUNT = "request_count"
    DURATION_AVG = "duration_avg"
    DURATION_P99 = "duration_p99"
    DURATION_P95 = "duration_p95"
    ERROR_RATE = "error_rate"

    _choices_labels = (
        (REQUEST_COUNT, _("请求数")),
        (DURATION_AVG, _("平均耗时")),
        (DURATION_P99, _("P99耗时")),
        (DURATION_P95, _("P95耗时")),
        (ERROR_RATE, _("错误率")),
    )


class GraphPluginType(ChoicesEnum):
    """图表插件类型"""

    # 节点数据插件
    NODE = "node_data"
    # 边数据插件
    EDGE = "edge_data"

    # 节点 UI 插件
    NODE_UI = "node_ui"
    # 边 UI 插件
    EDGE_UI = "edge_ui"


class GraphViewType(ChoicesEnum):
    """图表显示类型"""

    TOPO = "topo"
    TABLE = "table"

    _choices_labels = (
        (TOPO, _("视图")),
        (TABLE, _("表格")),
    )
