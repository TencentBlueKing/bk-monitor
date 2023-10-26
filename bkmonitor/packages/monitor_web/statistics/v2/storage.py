"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.functional import cached_property

from monitor_web.statistics.v2.base import BaseCollector
from core.statistics.metric import register, Metric

from metadata.models import InfluxDBClusterInfo, ClusterInfo


class StorageCollector(BaseCollector):
    """存储指标采集器"""

    @cached_property
    def influxdb_cluster_info(self):
        return InfluxDBClusterInfo.objects.all()

    @cached_property
    def elasticsearch_cluster(self):
        return ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_ES)

    @register(labelnames=("register_system",))
    def elasticsearch_cluster_count(self, metric: Metric):
        """ES 集群数"""
        register_system_map = {
            ClusterInfo.DEFAULT_REGISTERED_SYSTEM: "bk_monitor",
            ClusterInfo.LOG_PLATFORM_REGISTERED_SYSTEM: "bk_log",
        }

        for cluster in self.elasticsearch_cluster:
            metric.labels(register_system=register_system_map.get(cluster.registered_system)).inc()

    # 尚未明确指标，暂时未开启
    # @register()
    # def influxdb_cluster_count(self, metric: Metric):
    #     """influxDB 集群数"""
    #     metric.set(self.influxdb_cluster_info.distinct("cluster_name").count())

    @register(labelnames=("cluster_name",))
    def influxdb_host_count(self, metric: Metric):
        """influxDB 主机数"""
        # InfluxDBClusterInfo 实际上是按照主机维度平铺
        for info in self.influxdb_cluster_info:
            metric.labels(cluster_name=info.cluster_name).inc()
