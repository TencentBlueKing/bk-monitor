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
from typing import List

from django.utils.translation import gettext_lazy as _lazy

from monitor_web.k8s.scenario import Category, Metric

"""
k8s 性能场景配置, 初版
"""


# 每个场景需要配置一个 get_metrics函数 以返回指标列表
def get_metrics() -> List:
    return [
        Category(
            id="CPU",
            name="CPU",
            children=[
                Metric(
                    id="container_cpu_usage_seconds_total",
                    name=_lazy("CPU使用量"),
                    unit="core",
                    unsupported_resource=[],
                ),
                Metric(
                    id="kube_pod_cpu_requests_ratio",
                    name=_lazy("CPU request使用率"),
                    unit="percentunit",
                    unsupported_resource=["namespace"],
                ),
                Metric(
                    id="kube_pod_cpu_limits_ratio",
                    name=_lazy("CPU limit使用率"),
                    unit="percentunit",
                    unsupported_resource=["namespace"],
                ),
                Metric(
                    id="container_cpu_cfs_throttled_ratio",
                    name=_lazy("CPU 限流占比"),
                    unit="percentunit",
                    unsupported_resource=[],
                ),
            ],
        ),
        Category(
            id="memory",
            name=_lazy("内存"),
            children=[
                Metric(
                    id="container_memory_rss",
                    name=_lazy("内存使用量(rss)"),
                    unit="bytes",
                    unsupported_resource=[],
                ),
                Metric(
                    id="kube_pod_memory_requests_ratio",
                    name=_lazy("内存 request使用率"),
                    unit="percentunit",
                    unsupported_resource=["namespace"],
                ),
                Metric(
                    id="kube_pod_memory_limits_ratio",
                    name=_lazy("内存 limit使用率"),
                    unit="percentunit",
                    unsupported_resource=["namespace"],
                ),
            ],
        ),
        Category(
            id="network",
            name=_lazy("流量"),
            children=[
                Metric(
                    id="container_network_receive_bytes_total",
                    name=_lazy("网络入带宽"),
                    unit="Bps",
                    unsupported_resource=["container"],
                ),
                Metric(
                    id="container_network_transmit_bytes_total",
                    name=_lazy("网络出带宽"),
                    unit="Bps",
                    unsupported_resource=["container"],
                ),
            ],
        ),
    ]
