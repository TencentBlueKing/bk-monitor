"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.db.models import Count
from django.utils.functional import cached_property
from monitor_web.statistics.v2.base import BaseCollector

from bkmonitor.models import (
    BCSCluster,
    BCSContainer,
    BCSNode,
    BCSPod,
    BCSPodMonitor,
    BCSServiceMonitor,
    BCSWorkload,
)
from core.statistics.metric import Metric, register


class K8SCollector(BaseCollector):
    """
    容器监控采集器
    """

    @cached_property
    def bcs_clusters(self):
        return BCSCluster.objects.all()

    @cached_property
    def bcs_cluster_id_name_map(self):
        return {x["bcs_cluster_id"]: x["name"] for x in BCSCluster.objects.all().values("bcs_cluster_id", "name")}

    @cached_property
    def bcs_workloads(self):
        return BCSWorkload.objects.all()

    @cached_property
    def bcs_pods(self):
        return BCSPod.objects.all()

    @cached_property
    def bcs_containers(self):
        return BCSContainer.objects.all()

    @cached_property
    def bcs_nodes(self):
        return BCSNode.objects.all()

    @cached_property
    def bcs_service_monitors(self):
        return BCSServiceMonitor.objects.all()

    @cached_property
    def bcs_pod_monitors(self):
        return BCSPodMonitor.objects.all()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id"))
    def k8s_cluster_count(self, metric: Metric):
        """K8S接入集群数"""
        for cluster in self.bcs_clusters.values("bk_biz_id", "bcs_cluster_id", "name"):
            bk_biz_id = cluster["bk_biz_id"]
            bcs_cluster_id = cluster["bcs_cluster_id"]
            name = cluster["name"]

            bk_biz_name = self.get_biz_name(bk_biz_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=bk_biz_name,
                cluster_name=name,
                cluster_id=bcs_cluster_id,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id"))
    def k8s_workload_count(self, metric: Metric):
        """采集workload的数量 ."""
        for workload in self.bcs_workloads.values("bk_biz_id", "bcs_cluster_id").annotate(
            count=Count("bcs_cluster_id")
        ):
            bk_biz_id = workload["bk_biz_id"]
            bcs_cluster_id = workload["bcs_cluster_id"]
            count = workload["count"]

            bk_biz_name = self.get_biz_name(bk_biz_id)
            cluster_name = self.bcs_cluster_id_name_map.get(bcs_cluster_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=bk_biz_name,
                cluster_name=cluster_name,
                cluster_id=bcs_cluster_id,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id"))
    def k8s_pod_count(self, metric: Metric):
        """采集pod的数量 ."""
        for pod in self.bcs_pods.values("bk_biz_id", "bcs_cluster_id").annotate(count=Count("bcs_cluster_id")):
            bk_biz_id = pod["bk_biz_id"]
            bcs_cluster_id = pod["bcs_cluster_id"]
            count = pod["count"]

            bk_biz_name = self.get_biz_name(bk_biz_id)
            cluster_name = self.bcs_cluster_id_name_map.get(bcs_cluster_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=bk_biz_name,
                cluster_name=cluster_name,
                cluster_id=bcs_cluster_id,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id"))
    def k8s_container_count(self, metric: Metric):
        """采集container的数量 ."""
        for container in self.bcs_containers.values("bk_biz_id", "bcs_cluster_id").annotate(
            count=Count("bcs_cluster_id")
        ):
            bk_biz_id = container["bk_biz_id"]
            bcs_cluster_id = container["bcs_cluster_id"]
            count = container["count"]

            bk_biz_name = self.get_biz_name(bk_biz_id)
            cluster_name = self.bcs_cluster_id_name_map.get(bcs_cluster_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=bk_biz_name,
                cluster_name=cluster_name,
                cluster_id=bcs_cluster_id,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id"))
    def k8s_node_count(self, metric: Metric):
        """采集node的数量 ."""
        for node in self.bcs_nodes.values("bk_biz_id", "bcs_cluster_id").annotate(count=Count("bcs_cluster_id")):
            bk_biz_id = node["bk_biz_id"]
            bcs_cluster_id = node["bcs_cluster_id"]
            count = node["count"]

            bk_biz_name = self.get_biz_name(bk_biz_id)
            cluster_name = self.bcs_cluster_id_name_map.get(bcs_cluster_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=bk_biz_name,
                cluster_name=cluster_name,
                cluster_id=bcs_cluster_id,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "cluster_name", "cluster_id", "type"))
    def k8s_monitor_count(self, metric: Metric):
        """ServiceMonitor/PodMonitor的采集数量"""
        for monitor_type, monitor_models in [
            (BCSServiceMonitor.PLURAL, self.bcs_service_monitors),
            (BCSPodMonitor.PLURAL, self.bcs_pod_monitors),
        ]:
            for monitor_model in monitor_models.values("bk_biz_id", "bcs_cluster_id").annotate(
                count=Count("name", distinct=True)
            ):
                bk_biz_id = monitor_model["bk_biz_id"]
                bcs_cluster_id = monitor_model["bcs_cluster_id"]
                count = monitor_model["count"]

                bk_biz_name = self.get_biz_name(bk_biz_id)
                cluster_name = self.bcs_cluster_id_name_map.get(bcs_cluster_id)

                metric.labels(
                    bk_biz_id=bk_biz_id,
                    bk_biz_name=bk_biz_name,
                    cluster_name=cluster_name,
                    cluster_id=bcs_cluster_id,
                    type=monitor_type,
                ).inc(count)
