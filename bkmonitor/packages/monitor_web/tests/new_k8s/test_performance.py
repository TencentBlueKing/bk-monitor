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

import mock
import pytest

from monitor_web.k8s.core.meta import (
    K8sContainerMeta,
    K8sNamespaceMeta,
    K8sPodMeta,
    K8sResourceMeta,
    K8sWorkloadMeta,
    load_resource_meta,
)
from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListK8SResources,
    ResourceTrendResource,
)
from monitor_web.tests.new_k8s.conftest import BaseMetaPromQL

columns = [
    "container_cpu_usage_seconds_total",
    "kube_pod_cpu_requests_ratio",
    "kube_pod_cpu_limits_ratio",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "kube_pod_memory_requests_ratio",
    "kube_pod_memory_limits_ratio",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
]
namespace_columns = [
    "container_cpu_usage_seconds_total",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
]
namespace_promqls = [
    """sum by (namespace) 
(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))""",
    """sum by (namespace) 
((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])))""",
    """sum by (namespace) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})""",
    """sum by (namespace) (rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
]
namespace_promqls_with_interval = [
    """sum by (namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))[1m:]))""",
    """sum by (namespace) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
]
workload_promqls = [
    """sum by (workload_kind, workload_name, namespace) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))""",
    """sum by (workload_kind, workload_name, namespace) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, namespace, pod_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, namespace, pod_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) ((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])))""",
    """sum by (workload_kind, workload_name, namespace) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})""",
    """sum by (workload_kind, workload_name, namespace) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (workload_kind, workload_name, namespace) (rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
]
workload_promqls_with_interval = [
    """sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, namespace, pod_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, namespace, pod_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))[1m:]))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
]
pod_promqls = [
    """sum by (workload_kind, workload_name, namespace, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) ((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
]
pod_promqls_with_interval = [
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace,pod_name)\n    (count by (workload_kind, workload_name, pod_name, namespace) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
]

container_columns = [
    "container_cpu_usage_seconds_total",
    "kube_pod_cpu_requests_ratio",
    "kube_pod_cpu_limits_ratio",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "kube_pod_memory_requests_ratio",
    "kube_pod_memory_limits_ratio",
]
container_promqls = [
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name, container_name) ((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"})/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
]
container_promqls_with_interval = [
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_requests_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_limits_cpu_cores{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, pod_name, container_name) (last_over_time((increase(container_cpu_cfs_throttled_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]) / increase(container_cpu_cfs_periods_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_requests_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
    """sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time (container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]))/ (sum by (workload_kind, workload_name, namespace, pod_name, container_name)\n    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (\n        container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    ) *\n    on(pod_name, namespace, container_name)\n    group_right(workload_kind, workload_name)\n    sum by (pod_name, namespace, container_name) (\n      kube_pod_container_resource_limits_memory_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}\n    )))""",
]


class TestMetaPromQLWithPerformance(BaseMetaPromQL):
    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(namespace_columns, namespace_promqls, namespace_promqls_with_interval),
    )
    def test_meta_by_sort_with_namespace(self, column, promql, promql_with_interval):
        meta: K8sNamespaceMeta = load_resource_meta("namespace", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, workload_promqls, workload_promqls_with_interval),
    )
    def test_meta_by_sort_with_workload(self, column, promql, promql_with_interval):
        meta: K8sWorkloadMeta = load_resource_meta("workload", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, pod_promqls, pod_promqls_with_interval),
    )
    def test_meta_by_sort_with_pod(self, column, promql, promql_with_interval):
        meta: K8sPodMeta = load_resource_meta("pod", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(container_columns, container_promqls, container_promqls_with_interval),
    )
    def test_meta_by_sort_with_container(self, column, promql, promql_with_interval):
        meta: K8sContainerMeta = load_resource_meta("container", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)


class TestResourceTrendWithPerformance:
    @staticmethod
    def build_argvalues(columns) -> List[pytest.param]:
        scenario = "performance"
        resource_types = ["namespace", "workload", "pod", "container"]
        resource_lists = [
            ["namespace1"],
            ["workload_type1:workload_name1"],
            ["pod1"],
            ["container1"],
        ]
        argvalues = []

        for resource_type, resource_list in zip(resource_types, resource_lists):
            # 不同资源类型，columns也不同
            match resource_type:
                case "namespace":
                    columns = namespace_columns
                case "container":
                    columns = container_columns
                case _:
                    pass

            for column in columns:
                argvalues.append(
                    pytest.param(
                        scenario,
                        column,
                        resource_type,
                        resource_list,
                        id=f"{column}-{resource_type}-{resource_list}",
                    )
                )

        return argvalues

    @pytest.mark.parametrize(
        ["_scenario", "_column", "_resource_type", "_resource_list"],
        build_argvalues(columns),
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_get_resource_trend(
        self,
        graph_unify_query,
        _scenario,
        _column,
        _resource_type,
        _resource_list,
        ensure_test_get_scenario_metric,
    ):
        validated_request_data = {
            "resource_list": _resource_list,
            "scenario": _scenario,
            "bcs_cluster_id": "BCS-K8S-00000",
            "start_time": 1742286763,
            "end_time": 1742290363,
            "filter_dict": {},
            "column": _column,
            "method": "sum",
            "resource_type": _resource_type,
            "bk_biz_id": 2,
        }

        # 校验1, 直接从请求参数进行校验
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        resource_type = validated_request_data["resource_type"]
        agg_method = validated_request_data["method"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        column = validated_request_data["column"]
        scenario = validated_request_data["scenario"]

        # 校验2, 对最终的结果进行校验
        # unify_query 查询结果模板，需要变更的是 dimensions
        query_result = [
            {
                "dimensions": {},
                "target": "",
                "metric_field": "_result_",
                "datapoints": [
                    [0.411495, 1742290260000],
                ],
                "alias": "",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]
        match resource_type:
            case "namespace":
                query_result[0]["dimensions"] = {"namespace": "aiops-default"}
            case "workload":
                query_result[0]["dimensions"] = {
                    "namespace": "bk-jaeger",
                    "workload_kind": "StatefulSet",
                    "workload_name": "jaeger-cassandra",
                }
            case "pod":
                query_result[0]["dimensions"] = {
                    "namespace": "bk-jaeger",
                    "pod_name": "jaeger-cassandra-0",
                    "workload_kind": "StatefulSet",
                    "workload_name": "jaeger-cassandra",
                }
            case "container":
                query_result[0]["dimensions"] = {
                    "container_name": "bk-audit-risk-worker",
                    "namespace": "bkaudit",
                    "pod_name": "bk-audit-risk-worker-d8dfcc5f4-2hssv",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-audit-risk-worker",
                }
        resource_meta: K8sResourceMeta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)
        resource_meta.set_agg_method(agg_method)
        resource_meta.set_agg_interval(start_time, end_time)

        resource_name = resource_meta.get_resource_name(query_result[0])
        if resource_type == "workload":
            resource_name = f"{query_result[0]['dimensions']['namespace']}|{resource_name}"

        metric = GetScenarioMetric()({"bk_biz_id": bk_biz_id, "scenario": scenario, "metric_id": column})
        graph_unify_query.return_value = {"series": query_result}
        assert ResourceTrendResource()(validated_request_data) == [
            {
                "resource_name": resource_name,
                metric["id"]: {
                    "datapoints": [[0.411495, 1742290260000]],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
            }
        ]


@pytest.mark.django_db
class TestK8sListResourceWithPerformance:
    preformance_resource_types = ["namespace", "workload", "pod", "container"]
    preformance_columns = [
        "container_cpu_usage_seconds_total",
        "kube_pod_cpu_requests_ratio",
        "kube_pod_cpu_limits_ratio",
        "container_cpu_cfs_throttled_ratio",
        "container_memory_working_set_bytes",
        "kube_pod_memory_requests_ratio",
        "kube_pod_memory_limits_ratio",
        "container_network_receive_bytes_total",
        "container_network_transmit_bytes_total",
    ]

    def setup_method(self, create_workloads):
        pass

    @pytest.mark.parametrize(
        ["page", "page_size", "expect_result"],
        [
            # 左侧 K8S 对象列表 初始化获取 5个
            [
                1,
                5,
                [
                    "aiops-default",
                    "apm-demo",
                    "bcs-system",
                    "bk-apigateway-dev",
                    "bk-ci",
                ],
            ],
            # 左侧 K8S 对象列表 点击加载更多
            [
                2,
                5,
                [
                    "aiops-default",
                    "apm-demo",
                    "bcs-system",
                    "bk-apigateway-dev",
                    "bk-ci",
                    "bk-iam-dev",
                    "bk-jaeger",
                    "bk-storage",
                    "bk-user-rabbitmq",
                    "bk-user-v3",
                ],
            ],
        ],
    )
    # @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_left_namespace(
        self,
        # graph_unify_query_mock,
        page,
        page_size,
        expect_result,
    ):
        """
        获取左侧 namespace 列表

        只会查询数据库，所以不需要mock unify_query
        """
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": page_size,
            "page_type": "scrolling",
            "start_time": 1743487312,
            "end_time": 1743490912,
            "resource_type": "namespace",
            "page": page,
            "bk_biz_id": 2,
        }
        _bk_biz_id = validated_request_data["bk_biz_id"]
        _bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        _resource_type = validated_request_data["resource_type"]

        # graph_unify_query_mock.return_value = ...

        result = ListK8SResources()(validated_request_data)

        # 构建期待响应数据
        expect_result = [
            {
                "bk_biz_id": _bk_biz_id,
                "bcs_cluster_id": _bcs_cluster_id,
                _resource_type: item,
            }
            for item in expect_result
        ]

        # 校验最终结果和数量
        # assert result["items"] == expect_result
        assert result["items"] == []
        # assert len(result["items"]) == len(expect_result)
        assert len(result["items"]) == 0
