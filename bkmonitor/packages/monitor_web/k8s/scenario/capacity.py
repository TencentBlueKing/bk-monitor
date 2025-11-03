"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _lazy

from monitor_web.k8s.scenario import Category, Metric

"""
k8s 容量场景配置, 初版
"""


# 每个场景需要配置一个 get_metrics函数 以返回指标列表
def get_metrics() -> list:
    return [
        Category(
            id="CPU",
            name="CPU",
            children=[
                Metric(
                    id="node_cpu_seconds_total",
                    name=_lazy("CPU使用量"),
                    unit="core",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (node)
                Metric(
                    id="node_cpu_capacity_ratio",
                    name=_lazy("CPU装箱率"),
                    unit="percentunit",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # kube_node_status_allocatable 依赖bk-monitor-operator升级
                # sum(kube_pod_container_resource_requests{resource="cpu"}) by (node)
                # /
                # kube_node_status_allocatable{resource="cpu"} * 100
                Metric(
                    id="node_cpu_usage_ratio",
                    name=_lazy("CPU使用率"),
                    unit="percent",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) by (node)) * 100
            ],
        ),
        Category(
            id="memory",
            name=_lazy("内存"),
            children=[
                Metric(
                    id="node_memory_working_set_bytes",
                    name=_lazy("内存使用量"),
                    unit="bytes",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # sum by (node)(node_memory_MemTotal_bytes) - sum by (node) (node_memory_MemAvailable_bytes)
                Metric(
                    id="node_memory_capacity_ratio",
                    name=_lazy("内存装箱率"),
                    unit="percentunit",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # kube_node_status_allocatable 依赖bk-monitor-operator升级
                # sum(kube_pod_container_resource_requests{resource="memory"}) by (node)
                # /
                # kube_node_status_allocatable{resource="memory"} * 100
                Metric(
                    id="node_memory_usage_ratio",
                    name=_lazy("内存使用率"),
                    unit="percentunit",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # (1 - (sum by (node)(node_memory_MemAvailable_bytes) / sum by (node)(node_memory_MemTotal_bytes)))
            ],
        ),
        Category(
            id="capacity",
            name=_lazy("容量"),
            children=[
                Metric(
                    id="master_node_count",
                    name=_lazy("集群Master节点计数"),
                    unit="none",
                    unsupported_resource=["node"],
                    show_chart=True,
                ),
                # count(sum by (node)(kube_node_role{role=~"master|control-plane"}))
                Metric(
                    id="worker_node_count",
                    name=_lazy("集群Worker节点计数"),
                    unit="none",
                    unsupported_resource=["node"],
                    show_chart=True,
                ),
                # count(kube_node_labels) - count(sum by (node)(kube_node_role{role=~"master|control-plane"}))
                Metric(
                    id="node_pod_usage",
                    name=_lazy("Pod个数使用率"),
                    unit="percentunit",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # sum by (node)(kubelet_running_pods) / sum by (node)(kube_node_status_capacity_pods)
            ],
        ),
        Category(
            id="network",
            name=_lazy("网络"),
            children=[
                Metric(
                    id="node_network_receive_bytes_total",
                    name=_lazy("网络入带宽"),
                    unit="Bps",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*"}[1m])) by (node)
                Metric(
                    id="node_network_transmit_bytes_total",
                    name=_lazy("网络出带宽"),
                    unit="Bps",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*"}[1m])) by (node)
                Metric(
                    id="node_network_receive_packets_total",
                    name=_lazy("网络入包量"),
                    unit="pps",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # 需要升级bk-monitor-operator
                # sum(rate(node_network_receive_packets_total{device!~"lo|veth.*"}[1m])) by (node)
                Metric(
                    id="node_network_transmit_packets_total",
                    name=_lazy("网络出包量"),
                    unit="pps",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                # 需要升级bk-monitor-operator
                # sum(rate(node_network_transmit_packets_total{device!~"lo|veth.*"}[1m])) by (node)
            ],
        ),
    ]
