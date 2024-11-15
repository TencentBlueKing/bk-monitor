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
from collections import namedtuple

from apm_web.utils import get_interval_number
from bkmonitor.models import BCSContainer, BCSPod, BCSWorkload
from core.drf_resource import resource
from monitor_web.k8s.core.filters import load_resource_filter


class FilterCollection(object):
    def __init__(self):
        self.filters = dict()

    def add(self, filter_obj):
        self.filters[filter_obj.filter_uid] = filter_obj
        return self

    def remove(self, filter_obj):
        self.filters.pop(filter_obj.filter_uid, None)
        return self

    def filter(self, query_set):
        for filter_obj in self.filters.values():
            query_set = filter_obj.filter(query_set)
        return query_set

    def filter_string(self):
        return ",".join([filter_obj.filter_string() for filter_obj in self.filters.values()])


class K8sResourceMeta(object):
    filter = None
    resource_field = ""
    resource_class = None
    column_mapping = {}

    def __init__(self, bk_biz_id, bcs_cluster_id):
        self.bk_biz_id = bk_biz_id
        self.bcs_cluster_id = bcs_cluster_id
        self.setup_filter()

    def setup_filter(self):
        if self.filter is not None:
            return
        self.filter = FilterCollection()
        self.filter.add(load_resource_filter("cluster", self.bcs_cluster_id))
        self.filter.add(load_resource_filter("space", self.bk_biz_id))

    def get_from_meta(self, meta):
        pass

    def get_interval(self, start, end):
        return get_interval_number(start, end, interval="auto")

    def get_from_prom(self, start_time, end_time):
        query_params = {
            "bk_biz_id": self.bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": self.meta_prom,
                    "interval": self.get_interval(start_time, end_time),
                    "alias": "result",
                }
            ],
            "expression": "",
            "alias": "result",
            "start_time": start_time,
            "end_time": end_time,
            "slimit": 500,
            "down_sample_range": "",
        }
        ret = resource.grafana.graph_unify_query(query_params)["series"]
        """
        [{'dimensions': {'container_name': 'bk-monitor-web',
           'pod_name': 'bk-monitor-web-5dc76bbfd7-8w9c6'},
          'target': '{container_name=bk-monitor-web, pod_name=bk-monitor-web-5dc76bbfd7-8w9c6}',
          'metric_field': '_result_',
          'datapoints': [[356.68, 1731654480000],
            ...
           [379.95, 1731658020000]],
          'alias': '_result_',
          'type': 'line',
          'dimensions_translation': {},
          'unit': ''}]
        """
        resource_map = {}
        for series in ret:
            resource_name = self.get_resource_name(series)
            if resource_name not in resource_map:
                resource_obj = self.resource_class()
                resource_map[resource_name] = self.clean_resource_obj(resource_obj, series)
        return list(resource_map.values())

    def get_resource_name(self, series):
        return series["dimensions"][self.resource_field]

    def clean_resource_obj(self, obj, series):
        dimensions = series["dimensions"]
        for origin, target in self.column_mapping.items():
            if origin in dimensions:
                dimensions[target] = dimensions.pop(origin, None)
        obj.__dict__.update(series["dimensions"])
        obj.bk_biz_id = self.bk_biz_id
        obj.bcs_cluster_id = self.bcs_cluster_id
        return obj

    @property
    def meta_prom(self):
        return ""

    def add_filter(self, filter_obj):
        self.filter.add(filter_obj)


class K8sPodMeta(K8sResourceMeta):
    resource_field = "pod_name"
    resource_class = BCSPod
    column_mapping = {"workload_kind": "workload_type", "pod_name": "name"}

    @property
    def meta_prom(self):
        return f"""sum by (workload_kind, workload_name, namespace, pod_name) (container_cpu_system_seconds_total{{{self.filter.filter_string()}}})"""


class K8sNodeMeta(K8sResourceMeta):
    pass


class NameSpace(dict):
    @property
    def __dict__(self):
        return self


class K8sNamespaceMeta(K8sResourceMeta):
    resource_field = "namespace"
    resource_class = NameSpace.fromkeys(["bk_biz_id", "bcs_cluster_id", "namespace"], None)
    column_mapping = {}

    @property
    def meta_prom(self):
        return f"""sum by (namespace) (kube_namespace_labels{{{self.filter.filter_string()}}})"""


class K8sWorkloadMeta(K8sResourceMeta):
    resource_field = "workload_name"
    resource_class = BCSWorkload
    column_mapping = {"workload_kind": "type", "workload_name": "name"}

    @property
    def meta_prom(self):
        return f"""sum by (workload_kind, workload_name, namespace) (container_cpu_system_seconds_total{{{self.filter.filter_string()}}})"""


class K8sContainerMeta(K8sResourceMeta):
    resource_field = "container_name"
    resource_class = BCSContainer
    column_mapping = {"workload_kind": "workload_type", "container_name": "name"}

    def get_from_prom(self, prom):
        return f"""sum by (workload_kind, workload_name, namespace, container_name, pod_name) (container_cpu_system_seconds_total{{{self.filter.filter_string()}}})"""
