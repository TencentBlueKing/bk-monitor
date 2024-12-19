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
from typing import Dict, Optional

from django.utils.functional import cached_property

from apm_web.utils import get_interval_number
from bkmonitor.models import BCSContainer, BCSPod, BCSWorkload
from core.drf_resource import resource
from monitor_web.k8s.core.filters import load_resource_filter


class FilterCollection(object):
    """
    过滤查询集合

    内部过滤条件是一个字典， 可以通过 add、remove来添加过滤条件
    """

    def __init__(self, meta):
        self.filters = dict()
        self.meta = meta
        self.query_set = meta.resource_class.objects.all()
        if meta.only_fields:
            self.query_set = self.query_set.only(*self.meta.only_fields)

    def add(self, filter_obj):
        self.filters[filter_obj.filter_uid] = filter_obj
        return self

    def remove(self, filter_obj):
        self.filters.pop(filter_obj.filter_uid, None)
        return self

    @cached_property
    def filter_queryset(self):
        for filter_obj in self.filters.values():
            self.query_set = self.query_set.filter(**self.transform_filter_dict(filter_obj))
        return self.query_set

    def transform_filter_dict(self, filter_obj) -> Dict:
        """用于ORM的查询条件"""
        resource_type = filter_obj.resource_type
        resource_meta = load_resource_meta(resource_type, self.meta.bk_biz_id, self.meta.bcs_cluster_id)
        if not resource_meta:
            return filter_obj.filter_dict

        orm_filter_dict = {}
        for key, value in filter_obj.filter_dict.items():
            # 解析查询条件， 带双下划线表示特殊查询条件，不带表示等于
            parsed_token = key.split("__", 1)
            if parsed_token[0] == key:
                field_name = key
            else:
                field_name, condition = parsed_token
            # 字段映射， prometheus数据字段 映射到 ORM中的 模型字段
            field_name = self.meta.column_mapping.get(field_name, field_name)
            # 重新组装特殊查询条件
            new_key = field_name if len(parsed_token) == 1 else f"{field_name}__{condition}"
            orm_filter_dict[new_key] = value
        return orm_filter_dict

    def filter_string(self):
        for filter_type, filter_obj in self.filters.items():
            if filter_type.startswith("workload") and len(filter_obj.value) > 1:
                # 多个 workload_id 查询支持
                filter_obj.value = filter_obj.value[:1]
                # workload_filters = [load_resource_filter("workload", value, fuzzy=filter_obj.fuzzy)
                #                     for value in filter_obj.value]
                # self.filters.pop(filter_type, None)
                # return list(self.make_multi_workload_filter_string(workload_filters))
        return ",".join([filter_obj.filter_string() for filter_obj in self.filters.values()])

    def make_multi_workload_filter_string(self, workload_filters):
        for workload_filter in workload_filters:
            self.filters[workload_filter.filter_uid] = workload_filter
            yield self.filter_string()
            self.filters.pop(workload_filter.filter_uid, None)


class K8sResourceMeta(object):
    """
    k8s资源基类
    """

    filter = None
    resource_field = ""
    resource_class = None
    column_mapping = {}
    only_fields = []

    def __init__(self, bk_biz_id, bcs_cluster_id):
        """
        初始化时还会实例化一个 FilterCollection()
        附带有 集群id和业务id信息
        """
        self.bk_biz_id = bk_biz_id
        self.bcs_cluster_id = bcs_cluster_id
        self.setup_filter()

    def setup_filter(self):
        """
        启动过滤查询条件
        默认添加 集群id 和业务id 两个过滤信息
        """
        if self.filter is not None:
            return
        self.filter = FilterCollection(self)
        # 默认范围，业务-集群
        self.filter.add(load_resource_filter("bcs_cluster_id", self.bcs_cluster_id))
        self.filter.add(load_resource_filter("bk_biz_id", self.bk_biz_id))

    def get_from_meta(self):
        """
        数据获取来源

        从 meta 获取数据
        """
        return self.filter.filter_queryset

    def get_from_promql(self, start_time, end_time, order_by="", page_size=20):
        """
        数据获取来源
        """
        query_params = {
            "bk_biz_id": self.bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": self.meta_prom_by_sort(order_by=order_by, page_size=page_size),
                    "interval": get_interval_number(start_time, end_time, interval=60),
                    "alias": "result",
                }
            ],
            "expression": "",
            "alias": "result",
            "start_time": start_time,
            "end_time": end_time,
            "type": "range",
            "slimit": 10001,
            "down_sample_range": "",
        }
        ret = resource.grafana.graph_unify_query(query_params)["series"]
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
        """不带排序的资源查询promql"""
        return ""

    def meta_prom_by_sort(self, order_by="", page_size=20):
        order_type = "DESC" if order_by.startswith("-") else "ASC"
        order_func = "topk" if order_type == "DESC" else "bottomk"
        order_field = order_by.strip("-")

        meta_prom_func = f"meta_prom_with_{order_field}"
        if hasattr(self, meta_prom_func):
            return f"{order_func}({page_size}, {getattr(self, meta_prom_func)})"
        return self.meta_prom

    @property
    def meta_prom_with_mem(self):
        """按内存排序的资源查询promql"""
        return ""

    @property
    def meta_prom_with_cpu(self):
        """按cpu排序的资源查询promql"""
        return self.meta_prom

    def add_filter(self, filter_obj):
        self.filter.add(filter_obj)


class K8sPodMeta(K8sResourceMeta):
    resource_field = "pod_name"
    resource_class = BCSPod
    column_mapping = {"workload_kind": "workload_type", "pod_name": "name"}
    only_fields = ["name", "namespace", "workload_type", "workload_name", "bk_biz_id", "bcs_cluster_id"]

    @property
    def meta_prom(self):
        return (
            "sum by (workload_kind, workload_name, namespace, pod_name) "
            f"(rate(container_cpu_system_seconds_total{{{self.filter.filter_string()}}}[1m]))"
        )

    @property
    def meta_prom_with_mem(self):
        """按内存排序的资源查询promql"""
        return (
            "sum by (workload_kind, workload_name, namespace, pod_name) "
            f"(container_memory_rss{{{self.filter.filter_string()}}})"
        )


class K8sNodeMeta(K8sResourceMeta):
    pass


class NameSpaceQuerySet(list):
    def count(self):
        return len(self)

    def order_by(self, *field_names):
        # 如果没有提供字段名，则不进行排序
        if not field_names:
            return self

        def get_sort_key(item):
            key = []
            for field in field_names:
                # 检查是否为降序字段
                if field.startswith('-'):
                    field_name = field[1:]
                    # 使用负值来反转排序
                    key.append(-item.get(field_name, 0))
                else:
                    key.append(item.get(field, 0))
            return tuple(key)

        # 使用 sorted 函数进行排序
        sorted_data = sorted(self, key=get_sort_key)
        return NameSpaceQuerySet(sorted_data)


class NameSpace(dict):
    columns = ["bk_biz_id", "bcs_cluster_id", "namespace"]

    @property
    def __dict__(self):
        return self

    @property
    def objects(self):
        return BCSWorkload.objects.values(*self.columns)

    def __getattr__(self, item):
        if item in self:
            return self[item]
        return None

    def __setattr__(self, item, value):
        self[item] = value

    def __call__(self, **kwargs):
        ns = NameSpace.fromkeys(NameSpace.columns, None)
        ns.update(kwargs)
        return ns

    def to_meta_dict(self):
        return self


class K8sNamespaceMeta(K8sResourceMeta):
    resource_field = "namespace"
    resource_class = NameSpace.fromkeys(NameSpace.columns, None)
    column_mapping = {}

    @property
    def meta_prom(self):
        return (
            f"""sum by ({",".join(NameSpace.columns)}) """
            f"""(container_cpu_system_seconds_total{{{self.filter.filter_string()}}})"""
        )

    def get_from_meta(self):
        return self.distinct(self.filter.filter_queryset)

    @property
    def meta_prom_with_cpu(self):
        return f"sum by (namespace) (rate(container_cpu_system_seconds_total{{{self.filter.filter_string()}}}[1m]))"

    @property
    def meta_prom_with_mem(self):
        """按内存排序的资源查询promql"""
        return f"sum by (namespace) (container_memory_rss{{{self.filter.filter_string()}}})"

    @classmethod
    def distinct(cls, objs):
        unique_ns_query_set = set()
        for ns in objs:
            row = tuple(ns[field] for field in NameSpace.columns)
            unique_ns_query_set.add(row)
        # 默认按照namespace(第三个字段)排序
        return NameSpaceQuerySet(
            [NameSpace(zip(NameSpace.columns, ns)) for ns in sorted(unique_ns_query_set, key=lambda x: x[2])]
        )


class K8sWorkloadMeta(K8sResourceMeta):
    # todo 支持多workload
    resource_field = "workload_name"
    resource_class = BCSWorkload
    column_mapping = {"workload_kind": "type", "workload_name": "name"}
    only_fields = ["type", "name", "namespace", "bk_biz_id", "bcs_cluster_id"]

    @property
    def meta_prom(self):
        return (
            "sum by (workload_kind, workload_name, namespace) "
            f"(rate(container_cpu_system_seconds_total{{{self.filter.filter_string()}}}[1m]))"
        )

    @property
    def meta_prom_with_mem(self):
        """按内存排序的资源查询promql"""
        return (
            f"sum by (workload_kind, workload_name, namespace) (container_memory_rss{{{self.filter.filter_string()}}})"
        )


class K8sContainerMeta(K8sResourceMeta):
    resource_field = "container_name"
    resource_class = BCSContainer
    column_mapping = {"workload_kind": "workload_type", "container_name": "name"}
    only_fields = ["name", "namespace", "pod_name", "workload_type", "workload_name", "bk_biz_id", "bcs_cluster_id"]

    @property
    def meta_prom(self):
        return (
            f"sum by (workload_kind, workload_name, namespace, container_name, pod_name) "
            f"(rate(container_cpu_system_seconds_total{{{self.filter.filter_string()}}}[1m]))"
        )

    @property
    def meta_prom_with_mem(self):
        """按内存排序的资源查询promql"""
        return (
            "sum by (workload_kind, workload_name, namespace, container_name, pod_name)"
            f" (container_memory_rss{{{self.filter.filter_string()}}})"
        )


def load_resource_meta(resource_type: str, bk_biz_id: int, bcs_cluster_id: str) -> Optional[K8sResourceMeta]:
    resource_meta_map = {
        'node': K8sNodeMeta,
        'container': K8sContainerMeta,
        'pod': K8sPodMeta,
        'workload': K8sWorkloadMeta,
        'namespace': K8sNamespaceMeta,
    }
    if resource_type not in resource_meta_map:
        return None
    meta_class = resource_meta_map[resource_type]
    return meta_class(bk_biz_id, bcs_cluster_id)
