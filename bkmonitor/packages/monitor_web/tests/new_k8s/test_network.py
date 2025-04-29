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
    K8sIngressMeta,
    K8sNamespaceMeta,
    K8sPodMeta,
    K8sResourceMeta,
    K8sServiceMeta,
    load_resource_meta,
)
from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListK8SResources,
    ResourceTrendResource,
)
from monitor_web.tests.new_k8s.conftest import BaseMetaPromQL

columns = [
    "nw_container_network_transmit_bytes_total",
    "nw_container_network_receive_bytes_total",
    "nw_container_network_receive_errors_ratio",
    "nw_container_network_transmit_errors_ratio",
    "nw_container_network_transmit_errors_total",
    "nw_container_network_receive_errors_total",
    "nw_container_network_receive_packets_total",
    "nw_container_network_transmit_packets_total",
]
pod_promqls = [
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_bytes_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_bytes_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m]))), "pod_name", "$1", "pod", "(.*)") / label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m]))), "pod_name", "$1", "pod", "(.*)") / label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(last by (namespace, ingress, service,  pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m]))), "pod_name", "$1", "pod", "(.*)")""",
]  # noqa: E501
pod_promqls_with_interval = [
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_bytes_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)") / label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)") / label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
    """label_replace(sum by (namespace, ingress, service, pod) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total{}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")""",
]
namespace_promqls = [
    """sum by (namespace) (rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_receive_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])) / sum by (namespace) (rate(container_network_receive_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_transmit_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])) / sum by (namespace) (rate(container_network_transmit_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_transmit_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_receive_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_receive_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
    """sum by (namespace) (rate(container_network_transmit_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m]))""",
]
namespace_promqls_with_interval = [
    """sum by (namespace) (last_over_time(rate(container_network_transmit_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_receive_bytes_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_receive_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:])) / sum by (namespace) (last_over_time(rate(container_network_receive_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_transmit_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:])) / sum by (namespace) (last_over_time(rate(container_network_transmit_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_transmit_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_receive_errors_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_receive_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
    """sum by (namespace) (last_over_time(rate(container_network_transmit_packets_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}[1m])[1m:]))""",
]

ingress_promqls = [
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_bytes_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_bytes_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m]))) / last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m]))) / last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m])))""",
    """last by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m])))""",
]
ingress_promqls_with_interval = [
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_bytes_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total[1m])[1m:]))) / sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total[1m])[1m:]))) / sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total[1m])[1m:])))""",
    """sum by (ingress, namespace) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total[1m])[1m:])))""",
]
service_promqls = [
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_bytes_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_bytes_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m]))) / last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m]))) / last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_errors_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_errors_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_receive_packets_total[1m])))""",
    """last by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (rate(container_network_transmit_packets_total[1m])))""",
]
service_promqls_with_interval = [
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_bytes_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total[1m])[1m:]))) / sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total[1m])[1m:]))) / sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_errors_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_errors_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_packets_total[1m])[1m:])))""",
    """sum by (namespace, ingress, service) (count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"}) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_transmit_packets_total[1m])[1m:])))""",
]


class TestMetaPromQLWithNetwork(BaseMetaPromQL):
    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, pod_promqls, pod_promqls_with_interval),
    )
    def test_meta_by_sort_with_pod(self, column, promql, promql_with_interval):
        meta: K8sPodMeta = load_resource_meta("pod", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, namespace_promqls, namespace_promqls_with_interval),
    )
    def test_meta_by_sort_with_namespace(self, column, promql, promql_with_interval):
        meta: K8sNamespaceMeta = load_resource_meta("namespace", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, ingress_promqls, ingress_promqls_with_interval),
    )
    def test_meta_by_sort_with_ingress(self, column, promql, promql_with_interval):
        meta: K8sIngressMeta = load_resource_meta("ingress", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)

    @pytest.mark.parametrize(
        BaseMetaPromQL.build_argnames(),
        BaseMetaPromQL.build_argvalues(columns, service_promqls, service_promqls_with_interval),
    )
    def test_meta_by_sort_with_service(self, column, promql, promql_with_interval):
        meta: K8sServiceMeta = load_resource_meta("service", 2, "BCS-K8S-00000")
        self.assert_meta_promql(meta, column, promql, promql_with_interval)


class TestResourceTrendWithNetwork:
    @staticmethod
    def build_argvalues(columns) -> List[pytest.param]:
        scenario = "network"
        resource_types = [
            "namespace",
            "ingress",
            "service",
            "pod",
        ]
        resource_lists = [
            ["aiops-default"],
            ["bcs-ui"],
            ["bcs-api-gateway"],
            ["apm-demo-859495cbd7-7tjn5"],
        ]
        argvalues = []

        for resource_type, resource_list in zip(resource_types, resource_lists):
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
                "target": "{bcs_cluster_id=BCS-K8S-00000, bk_biz_id=2, namespace=aiops-default}",
                "metric_field": "_result_",
                "datapoints": [
                    [0.411495, 1742290260000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]
        match resource_type:
            case "namespace":
                query_result[0]["dimensions"] = {"namespace": "aiops-default"}
            case "ingress":
                query_result[0]["dimensions"] = {
                    "ingress": "bcs-ui",
                    "namespace": "bcs-system",
                }
            case "service":
                query_result[0]["dimensions"] = {
                    "ingress": "bcs-ui",
                    "namespace": "bcs-system",
                    "service": "bcs-api-gateway",
                }
            case "pod":
                query_result[0]["dimensions"] = {
                    "ingress": "bcs-ui",
                    "namespace": "bcs-system",
                    "pod": "bcs-services-stack-bk-micro-gateway-7f447d8547-wsgp2",
                    "pod_name": "bcs-services-stack-bk-micro-gateway-7f447d8547-wsgp2",
                    "service": "bcs-api-gateway",
                }
        resource_meta: K8sResourceMeta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)
        resource_meta.set_agg_method(agg_method)
        resource_meta.set_agg_interval(start_time, end_time)

        resource_name = resource_meta.get_resource_name(query_result[0])
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


class TestK8sListResourceWithNetwork:
    network_resource_type = ["namespace", "ingress", "service", "pod"]
    network_columns = [
        "nw_container_network_transmit_bytes_total",
        "nw_container_network_receive_bytes_total",
        "nw_container_network_receive_errors_ratio",
        "nw_container_network_transmit_errors_ratio",
        "nw_container_network_transmit_errors_total",
        "nw_container_network_receive_errors_total",
        "nw_container_network_receive_packets_total",
        "nw_container_network_transmit_packets_total",
    ]

    def setup_method(self, create_workloads, create_pods, create_containers):
        create_workloads()

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_namespace(self, column, method):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "column": column,
            "resource_type": "namespace",
            "scenario": "network",
            "start_time": 1742286763,
            "end_time": 1742290363,
            "method": method,
        }

        resource_type = validated_request_data["resource_type"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        # resource_type = validated_request_data["resource_type"]
        # agg_method = validated_request_data["method"]
        # start_time = validated_request_data["start_time"]
        # end_time = validated_request_data["end_time"]
        # column = validated_request_data["column"]
        # scenario = validated_request_data["scenario"]

        # 校验重点，检查 orm 和 promql 语句的变化

        # 1. 校验初始化时的 orm
        resource_meta: K8sResourceMeta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)

        # 2. 校验 添加了 query_string 之后的 orm

        # 3.

        assert ListK8SResources()(validated_request_data) == {}

    def test_with_namespace_with_left(self):
        pass

    def test_with_namespace_with_right(self):
        ...

    # def test_with_ingress(self):
    #     pass

    # def test_with_service(self):
    #     pass

    # def test_with_pod(self):
    #     pass

    def test_heihe(self):
        """黑盒测试

        传入参数，只校验最终返回的结果， 不校验中间的过程
        """
        pass

    def test_get_service_with_right(self):
        """过滤pod，获取ingress维度"""
        validated_request_data = {
            "scenario": "network",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {
                "namespace": ["blueking"],
                "pod": ["bk-apigateway-apigateway-66655dc754-lvxd6"],
            },
            "start_time": 1744089328,
            "end_time": 1744092928,
            "page_size": 20,
            "page": 1,
            "resource_type": "service",  # 记得修改成 ingress
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        resource_type = validated_request_data["resource_type"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        order_by = validated_request_data["order_by"]
        page_size = validated_request_data["page_size"]
        page = validated_request_data["page"]
        method = validated_request_data["method"]
        column = validated_request_data["column"]

        resource_meta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)
        assert isinstance(resource_meta, K8sServiceMeta)  # 记得修改成 ingress

        order_by = column if order_by == "desc" else f"-{column}"
        page_count = page_size * page

        # 校验 promql
        meta_prom_func = f"meta_prom_with_{column}"
        promql = getattr(resource_meta, meta_prom_func)

        history_resource_list = resource_meta.get_from_promql(start_time, end_time, order_by, page_count, method)
        assert history_resource_list == []  # 记得补充

        expect_result = {
            "count": 1,
            "items": [
                {
                    "pod": "bk-apigateway-apigateway-66655dc754-lvxd6",
                    "namespace": "blueking",
                }
            ],
        }
        assert ListK8SResources()(**validated_request_data) == expect_result

    def test_get_ingress_with_right(self):
        """ """
        pass

    def test_with_xuqiu1(self):
        """从需求角度出发，校验传参和返回值，不考虑过程"""
        pass

    def test_with_daimaluoji(self):
        """从代码逻辑出发，考虑代码中走不同分支数据的变化"""
        pass
