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
            id="traffic",
            name=_lazy("流量"),
            children=[
                Metric(
                    id="nw_container_network_receive_bytes_total",
                    name=_lazy("网络入带宽"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_transmit_bytes_total",
                    name=_lazy("网络出带宽"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
            ],
        ),
        Category(
            id="packets",
            name=_lazy("包量"),
            children=[
                Metric(
                    id="nw_container_network_receive_packets_total",
                    name=_lazy("网络入包量"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_transmit_packets_total",
                    name=_lazy("网络出包量"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_receive_packets_dropped_total",
                    name=_lazy("网络入丢包量"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_transmit_packets_dropped_total",
                    name=_lazy("网络出丢包量"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_receive_packets_dropped_ratio",
                    name=_lazy("网络入丢包率"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
                Metric(
                    id="nw_container_network_transmit_packets_dropped_ratio",
                    name=_lazy("网络出丢包率"),
                    unit="Bps",
                    unsupported_resource=[],
                ),
            ],
        ),
    ]
