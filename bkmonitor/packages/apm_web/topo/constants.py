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
from django.utils.translation import gettext_lazy as _

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

    ERROR_COUNT_CALLER = "error_count_caller"
    ERROR_COUNT_CALLEE = "error_count_callee"
    DURATION_MAX_CALLER = "duration_max_caller"
    DURATION_MAX_CALLEE = "duration_max_callee"
    DURATION_MIN_CALLER = "duration_min_callee"
    DURATION_MIN_CALLEE = "duration_min_callee"
    DURATION_P50_CALLER = "duration_p50_caller"
    DURATION_P50_CALLEE = "duration_p50_callee"
    DURATION_P99_CALLER = "duration_p99_caller"
    DURATION_P99_CALLEE = "duration_p99_callee"
    DURATION_P95_CALLER = "duration_p95_caller"
    DURATION_P95_CALLEE = "duration_p95_callee"

    # 下拉框选项共下面五项
    _choices_labels = (
        (Apdex, _("apdex")),
        (Alert, _("告警事件")),
        (ErrorRateCaller, _("主调错误率")),
        (ErrorRateCallee, _("被调错误率")),
        (ErrorRate, _("错误率")),
        (ERROR_COUNT_CALLER, _("主调错误数")),
        (ERROR_COUNT_CALLEE, _("被调错误数")),
        (DURATION_MAX_CALLER, _("主调最大耗时")),
        (DURATION_MAX_CALLEE, _("被调最大耗时")),
        (DURATION_MIN_CALLER, _("主调最小耗时")),
        (DURATION_MIN_CALLEE, _("被调最小耗时")),
        (DURATION_P50_CALLER, _("主调 P50 耗时")),
        (DURATION_P50_CALLEE, _("被调 P50 耗时")),
        (DURATION_P99_CALLER, _("主调 P99 耗时")),
        (DURATION_P99_CALLEE, _("被调 P99 耗时")),
        (DURATION_P95_CALLER, _("主调 P95 耗时")),
        (DURATION_P95_CALLEE, _("被调 P95 耗时")),
    )


class TopoEdgeDataType(ChoicesEnum):
    """拓扑图连接线数据类型"""

    REQUEST_COUNT = "request_count"
    DURATION_AVG = "duration_avg"
    DURATION_P99 = "duration_p99"
    DURATION_P95 = "duration_p95"
    DURATION_P50 = "duration_p50"
    ERROR_RATE = "error_rate"
    ERROR_COUNT = "error_count"

    _choices_labels = (
        (REQUEST_COUNT, _("请求数")),
        (DURATION_AVG, _("平均耗时")),
        (DURATION_P99, _("P99耗时")),
        (DURATION_P95, _("P95耗时")),
        (DURATION_P50, _("P50耗时")),
        (ERROR_RATE, _("错误率")),
        (ERROR_COUNT, _("错误数")),
    )


class GraphPluginType(ChoicesEnum):
    """图表插件类型"""

    # 节点数据插件
    NODE = "node_data"
    # 边数据插件
    EDGE = "edge_data"
    # 接口节点数据插件
    ENDPOINT = "endpoint_data"

    # 节点 UI 插件
    NODE_UI = "node_ui"
    # 边 UI 插件
    EDGE_UI = "edge_ui"
    # 接口 UI 插件
    ENDPOINT_UI = "endpoint_ui"


class GraphViewType(ChoicesEnum):
    """图表显示类型"""

    TOPO = "topo"
    TABLE = "table"
    TOPO_DIFF = "topo_diff"

    _choices_labels = (
        (TOPO, _("视图")),
        (TABLE, _("表格")),
        (TOPO_DIFF, _("视图(对比模式)")),
    )


class RelationResourcePathType(ChoicesEnum):
    """关联指标 - 路径查询类型"""

    DEFAULT = "default"
    SPECIFIC = "specific"

    _choices_labels = ((DEFAULT, _("默认查询")), (SPECIFIC, _("指定路径查询")))


class SourceType(ChoicesEnum):
    """[UnifyQuery] 资源类型"""

    APM_SERVICE = "apm_service"
    APM_SERVICE_INSTANCE = "apm_service_instance"
    POD = "pod"
    NODE = "node"
    SERVICE = "service"
    SYSTEM = "system"
    DATA_SOURCE = "datasource"

    _choices_labels = (
        (APM_SERVICE, _("APM 应用服务")),
        (APM_SERVICE_INSTANCE, _("APM 应用服务实例")),
        (POD, _("[K8S] Pod")),
        (NODE, _("node")),
        (SERVICE, _("[K8S] Service")),
        (SYSTEM, _("Host")),
        (DATA_SOURCE, _("datasource")),
    )


class RelationResourcePath(ChoicesEnum):
    """关联指标 - 指定查询路径"""

    INSTANCE_TO_SYSTEM = "apm_service_to_apm_service_instance_to_system"
    INSTANCE_TO_POD_TO_SYSTEM = "apm_service_to_apm_service_instance_to_pod_to_system"
    INSTANCE_TO_SERVICE_TO_SYSTEM = "apm_service_to_apm_service_instance_to_service_to_system"

    _choices_labels = (
        (INSTANCE_TO_SYSTEM, _("实例->机器")),
        (INSTANCE_TO_POD_TO_SYSTEM, _("实例->K8s Pod->机器")),
        (INSTANCE_TO_SERVICE_TO_SYSTEM, _("实例->K8s Service->机器")),
    )


class TopoLinkType(ChoicesEnum):
    """拓扑图中可供跳转的链接日期"""

    ALERT = "alert"
    TOPO_SOURCE = "topo_source"

    _choices_labels = (
        (ALERT, _("跳转到告警中心")),
        (TOPO_SOURCE, _("资源拓扑链接跳转处理")),
    )
