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

import re

import pytest

from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.core.meta import load_resource_meta


class TestPromQL:
    start_time = 1745391585
    end_time = 1745395185

    PERFORMANCE_DEFAULT_COLUMN = "container_cpu_usage_seconds_total"
    NETWORK_DEFAULT_COLUMN = "nw_container_network_receive_bytes_total"
    CAPACITY_DEFAULT_COLUMN = "node_boot_time_seconds"

    PERFORMANCE_ARGVALUES = [
        # namespace -
        # - 不带过滤
        (
            "namespace",
            PERFORMANCE_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # - column = container_memory_working_set_bytes
        (
            "namespace",
            "container_memory_working_set_bytes",
            {},
            "",
            'topk(10, sum by (namespace) (last_over_time(container_memory_working_set_bytes{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dict = {namespace: ["aiops-default"]}
        (
            "namespace",
            PERFORMANCE_DEFAULT_COLUMN,
            {"namespace": ["aiops-default"]},
            "",
            'topk(10, sum by (namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",namespace="aiops-default"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # workload
        # - nothing
        (
            "workload",
            PERFORMANCE_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"workload": "Deployment:"}
        (
            "workload",
            PERFORMANCE_DEFAULT_COLUMN,
            {"workload": "Deployment:"},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",workload_kind="Deployment"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"namespace": ["aiops-default"], "workload": ["Deployment:agent-plugin--web"]}
        (
            "workload",
            PERFORMANCE_DEFAULT_COLUMN,
            {"namespace": ["aiops-default"], "workload": ["Deployment:agent-plugin--web"]},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",namespace="aiops-default",workload_kind="Deployment",workload_name="agent-plugin--web"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # - query_dict = "Deployment:"
        (
            "workload",
            PERFORMANCE_DEFAULT_COLUMN,
            {},
            "Deployment:",
            'topk(10, sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",workload_name=~"Deployment:"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # pod
        # - nothing
        (
            "pod",
            PERFORMANCE_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dict = {{"namespace": "aiops-default"],"workload": ["Deployment:agent-plugin--web"], "pod": ["pod-1", "pod-2"]}}  # noqa
        (
            "pod",
            PERFORMANCE_DEFAULT_COLUMN,
            {
                "namespace": ["aiops-default"],
                "workload": ["Deployment:agent-plugin--web"],
                "pod": [
                    "python-backend--0--session-default---experiment-clear-backbvcgm",
                    "python-backend--0--session-default---scene-service-period-d2cn7",
                ],
            },
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",namespace="aiops-default",workload_kind="Deployment",workload_name="agent-plugin--web",pod_name=~"^(python-backend--0--session-default---experiment-clear-backbvcgm|python-backend--0--session-default---scene-service-period-d2cn7)$"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # container
        # - nothing
        (
            "container",
            PERFORMANCE_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
        # -filter_dict = {"container": ["aiops", "apisix"]}
        (
            "container",
            PERFORMANCE_DEFAULT_COLUMN,
            {"container": ["aiops", "apisix"]},
            "",
            'topk(10, sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",container_name=~"^(aiops|apisix)$"}[1m])[1m:])) * -1) * -1',  # noqa
        ),
    ]

    NETWORK_ARGVALUES = [
        # namespace
        # - nothing
        (
            "namespace",
            NETWORK_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (namespace) (sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"namespace": ["aiops-default", "bcs-op"]}
        (
            "namespace",
            NETWORK_DEFAULT_COLUMN,
            {"namespace": ["aiops-default", "bcs-op"]},
            "",
            'topk(10, sum by (namespace) (sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{namespace=~"^(aiops-default|bcs-op)$"}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # ingress
        # - nothing
        (
            "ingress",
            NETWORK_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (ingress, namespace) ((count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod)(ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * 0 + 1)* on (namespace, service) group_left(pod)(count by (service, namespace, pod) (pod_with_service_relation))* on (namespace, pod) group_left()sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"ingress": "stack-bcs-api-gateway-http","agent-plugin-subpath"]}
        (
            "ingress",
            NETWORK_DEFAULT_COLUMN,
            {"ingress": ["stack-bcs-api-gateway-http", "agent-plugin-subpath"]},
            "",
            'topk(10, sum by (ingress, namespace) ((count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod)(ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",ingress=~"^(agent-plugin-subpath|stack-bcs-api-gateway-http)$"}) * 0 + 1)* on (namespace, service) group_left(pod)(count by (service, namespace, pod) (pod_with_service_relation))* on (namespace, pod) group_left()sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # service
        # - nothing
        (
            "service",
            NETWORK_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (namespace, service) ((count by (service, namespace, pod) (pod_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * 0 + 1) * on (namespace, pod) group_left()sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"namespace": ["aiops-default"], "service": ["service-1"]}
        (
            "service",
            NETWORK_DEFAULT_COLUMN,
            {"namespace": ["aiops-default"], "service": ["service-1"]},
            "",
            'topk(10, sum by (namespace, service) ((count by (service, namespace, pod) (pod_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",namespace="aiops-default",service="service-1"}) * 0 + 1) * on (namespace, pod) group_left()sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{namespace="aiops-default"}[1m])[1m:]))) * -1) * -1',  # noqa
        ),
        # pod
        # - nothing
        (
            "pod",
            NETWORK_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, label_replace(sum by (namespace, pod) (sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))),"pod_name", "$1", "pod", "(.*)") * -1) * -1',  # noqa
        ),
        # - filter_dict = {"pod": ["pod-1", "pod-2"]}
        (
            "pod",
            NETWORK_DEFAULT_COLUMN,
            {"pod": ["pod-1", "pod-2"]},
            "",
            'topk(10, label_replace(sum by (namespace, pod) (sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{pod_name=~"^(pod-1|pod-2)$"}[1m])[1m:]))),"pod_name", "$1", "pod", "(.*)") * -1) * -1',  # noqa
        ),
    ]
    CAPACITY_ARGVALUES = [
        # node
        # - nothing
        (
            "node",
            CAPACITY_DEFAULT_COLUMN,
            {},
            "",
            'topk(10, sum by (node) (last_over_time(node_boot_time_seconds{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dict = {"node": "master-127-0-0-1"}
        (
            "node",
            CAPACITY_DEFAULT_COLUMN,
            {"node": "master-127-0-0-1"},
            'topk(10, sum by (node) (last_over_time(node_boot_time_seconds{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",node="master-127-0-0-1"}[1m:])) * -1) * -1',  # noqa
        ),
        # - filter_dcit = {"node": ["master-127-0-0-1", "master-127-0-0-2"]}
        (
            "node",
            CAPACITY_DEFAULT_COLUMN,
            {"node": ["master-127-0-0-1", "master-127-0-0-2"]},
            'topk(10, sum by (node) (last_over_time(node_boot_time_seconds{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",node=~"^(master-127-0-0-1|master-127-0-0-2)$"}[1m:])) * -1) * -1',  # noqa
        ),
    ]

    def base(self, resource_type, column, filter_dict, query_string, expected_promql):
        order_by = "asc"
        page_size = 10

        order_by = column if order_by == "asc" else "-{}".format(column)

        # 默认属性配置
        meta = load_resource_meta(resource_type, 2, "BCS-K8S-00000")
        meta.set_agg_method("sum")
        meta.set_agg_interval(self.start_time, self.end_time)

        # 过滤条件添加
        for _resource_type, _values in filter_dict.items():
            meta.filter.add(load_resource_filter(_resource_type, _values))
        if query_string:
            meta.filter.add(load_resource_filter(resource_type, query_string, fuzzy=True))

        actual_promql = meta.meta_prom_by_sort(order_by=order_by, page_size=page_size)

        # 去掉多余的空格和回车
        actual_promql = re.sub(r'\n\s+', '', actual_promql)
        assert actual_promql == expected_promql

    @pytest.mark.parametrize(
        ["resource_type", "column", "filter_dict", "query_string", "expected_promql"],
        [
            pytest.param(*item, id=" | ".join(["performance", *item[:2], str(item[2]), item[3]]))
            for item in PERFORMANCE_ARGVALUES
        ],
    )
    def test_with_performance(self, resource_type, column, filter_dict, query_string, expected_promql):
        self.base(resource_type, column, filter_dict, query_string, expected_promql)

    @pytest.mark.parametrize(
        ["resource_type", "column", "filter_dict", "query_string", "expected_promql"],
        [
            pytest.param(*item, id=" | ".join(["network", *item[:2], str(item[2]), item[3]]))
            for item in NETWORK_ARGVALUES
        ],
    )
    def test_with_network(self, resource_type, column, filter_dict, query_string, expected_promql):
        self.base(resource_type, column, filter_dict, query_string, expected_promql)

    @pytest.mark.parametrize(
        ["resource_type", "column", "filter_dict", "query_string", "expected_promql"],
        [
            pytest.param(*item, id=" | ".join(["capacity", *item[:2], str(item[2]), item[3]]))
            for item in NETWORK_ARGVALUES
        ],
    )
    def test_with_capacity(self, resource_type, column, filter_dict, query_string, expected_promql):
        self.base(resource_type, column, filter_dict, query_string, expected_promql)
