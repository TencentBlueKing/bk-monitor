"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict

from django.utils.functional import cached_property

from apm.models import TopoInstance, TopoNode, TraceDataSource
from apm_ebpf.models import DeepflowWorkload
from apm_web.models import Application
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class APMCollector(BaseCollector):
    """APM 指标采集器"""

    @cached_property
    def applications_biz_map(self) -> dict:
        biz_map = defaultdict(list)
        for app in Application.objects.filter(bk_biz_id__in=list(self.biz_info.keys()), is_enabled=True):
            biz_map[app.bk_biz_id].append(app)

        return biz_map

    @cached_property
    def top_node_biz_map(self) -> dict:
        biz_map = defaultdict(list)
        for node in TopoNode.objects.filter(bk_biz_id__in=list(self.biz_info.keys())):
            biz_map[node.bk_biz_id].append(node)

        return biz_map

    @cached_property
    def top_ins_biz_map(self) -> dict:
        biz_map = defaultdict(list)
        for ins in TopoInstance.objects.filter(bk_biz_id__in=list(self.biz_info.keys())):
            biz_map[ins.bk_biz_id].append(ins)

        return biz_map

    @cached_property
    def trace_datasource_map(self) -> dict:
        biz_map = defaultdict(list)
        for ins in TraceDataSource.objects.filter(bk_biz_id__in=list(self.biz_info.keys())):
            biz_map[ins.bk_biz_id].append(ins)

        return biz_map

    @register(labelnames=("bk_biz_id", "bk_biz_name", "data_status"))
    def application_count(self, metric: Metric):
        """应用数"""
        for biz_id, apps in self.applications_biz_map.items():
            bk_biz_name = self.get_biz_name(biz_id)
            for app in apps:
                metric.labels(bk_biz_id=biz_id, bk_biz_name=bk_biz_name, data_status=app.data_status).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def ebpf_k8s_count(self, metric: Metric):
        """ebpf使用的k8s集群数"""

        biz_map = defaultdict(list)
        for obj in DeepflowWorkload.objects.values("bk_biz_id", "cluster_id").distinct():
            biz_map[obj["bk_biz_id"]].append(obj)

        for biz_id, objs in biz_map.items():
            bk_biz_name = self.get_biz_name(biz_id)
            metric.labels(bk_biz_id=biz_id, bk_biz_name=bk_biz_name).inc(len(objs))

    # @register(labelnames=("bk_biz_id", "bk_biz_name", "app_name"))
    # def span_count(self, metric: Metric):
    #     """APM 存储文档数量"""
    #     for biz_id, apps in self.applications_biz_map.items():
    #         for app in apps:
    #             metric.labels(bk_biz_id=biz_id, bk_biz_name=self.get_biz_name(biz_id), app_name=app.app_name).inc(
    #                 app.doc_count
    #             )

    @register(labelnames=("bk_biz_id", "bk_biz_name", "app_name"))
    def service_count(self, metric: Metric):
        """存储数量"""
        for biz_id, nodes in self.top_node_biz_map.items():
            for node in nodes:
                metric.labels(bk_biz_id=biz_id, bk_biz_name=self.get_biz_name(biz_id), app_name=node.app_name).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "app_name"))
    def service_instance_count(self, metric: Metric):
        """存储数量"""
        for biz_id, instances in self.top_ins_biz_map.items():
            for ins in instances:
                metric.labels(bk_biz_id=biz_id, bk_biz_name=self.get_biz_name(biz_id), app_name=ins.app_name).inc()
