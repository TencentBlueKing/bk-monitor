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

from django.db.models import F, Max, Value
from django.db.models.functions import Concat
from django.utils.functional import cached_property

from apm_web.utils import get_interval_number
from bkmonitor.models import BCSContainer, BCSIngress, BCSPod, BCSService, BCSWorkload
from bkmonitor.utils.time_tools import hms_string
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
        self.query_set = meta.resource_class.objects.all().order_by("id")
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

    def filter_string(self, exclude=""):
        where_string_list = []
        for filter_type, filter_obj in self.filters.items():
            if exclude and filter_type.startswith(exclude):
                continue

            if filter_type.startswith("workload") and len(filter_obj.value) > 1:
                # 多个 workload_id 查询支持
                filter_obj.value = filter_obj.value[:1]
                # workload_filters = [load_resource_filter("workload", value, fuzzy=filter_obj.fuzzy)
                #                     for value in filter_obj.value]
                # self.filters.pop(filter_type, None)
                # return list(self.make_multi_workload_filter_string(workload_filters))

            where_string_list.append(filter_obj.filter_string())
        return ",".join(where_string_list)

    def make_multi_workload_filter_string(self, workload_filters):
        for workload_filter in workload_filters:
            self.filters[workload_filter.filter_uid] = workload_filter
            yield self.filter_string()
            self.filters.pop(workload_filter.filter_uid, None)


class NetworkWithRelation:
    """网络场景，层级关联支持"""

    def label_join(self, filter_exclude=""):
        return f"""(count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod)
            (ingress_with_service_relation{{{self.filter.filter_string(exclude=filter_exclude)}}})
            * on (namespace, service) group_left(pod)
            (count by (service, namespace, pod) (pod_with_service_relation))
            * on (namespace, pod) group_left(ingress)"""

    def clean_metric_name(self, metric_name):
        if metric_name.startswith("nw_"):
            return metric_name[3:]
        return metric_name


class K8sResourceMeta(object):
    """
    k8s资源基类
    """

    filter = None
    resource_field = ""
    resource_class = None
    column_mapping = {}
    only_fields = []
    method = ""

    @property
    def resource_field_list(self):
        return [self.resource_field]

    def __init__(self, bk_biz_id, bcs_cluster_id):
        """
        初始化时还会实例化一个 FilterCollection()
        附带有 集群id和业务id信息
        """
        self.bk_biz_id = bk_biz_id
        self.bcs_cluster_id = bcs_cluster_id
        self.setup_filter()
        self.agg_interval = ""
        self.set_agg_method()

    def set_agg_interval(self, start_time, end_time):
        """设置聚合查询的间隔"""
        if self.method == "count":
            # count表示数量 不用时间聚合
            self.agg_interval = ""
            return

        if self.method == "sum":
            # 默认sum表示当前最新值 sum ( last_over_time )
            time_passed = get_interval_number(start_time, end_time, interval=60)
        else:
            # 其余方法表示时间范围内的聚合 sum( avg_over_time ), sum (max_over_time), sum(min_over_time)
            time_passed = end_time - start_time
        agg_interval = hms_string(time_passed, upper=True)
        self.agg_interval = agg_interval

    def set_agg_method(self, method="sum"):
        self.method = method
        if method == "count":
            # 重置interval
            self.set_agg_interval(0, 1)

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
        # 默认过滤 container_name!="POD"
        self.filter.add(load_resource_filter("container_exclude", ""))

    def get_from_meta(self):
        """
        数据获取来源

        从 meta 获取数据
        """
        return self.filter.filter_queryset

    @classmethod
    def distinct(cls, queryset):
        # pod不需要去重，因为不会重名，workload，container 在不同ns下会重名，因此需要去重
        return queryset

    def get_from_promql(self, start_time, end_time, order_by="", page_size=20, method="sum"):
        """
        数据获取来源
        """
        self.set_agg_method(method)
        interval = get_interval_number(start_time, end_time, interval=60)
        self.set_agg_interval(start_time, end_time)
        query_params = {
            "bk_biz_id": self.bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": self.meta_prom_by_sort(order_by=order_by, page_size=page_size),
                    "interval": interval,
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
        print(query_params["query_configs"][0]["promql"])
        series = resource.grafana.graph_unify_query(query_params)["series"]
        # 这里需要排序
        # 1. 得到最新时间点
        # 2. 基于最新时间点数据进行排序
        lines = []
        max_data_point = 0
        for line in series:
            if line["datapoints"]:
                for point in reversed(line["datapoints"]):
                    if point[0]:
                        max_data_point = max(max_data_point, point[1])
        for line in series:
            if line["datapoints"][-1][1] == max_data_point:
                lines.append([line["datapoints"][-1][0] or 0, line])
            else:
                lines.append([0, line])
        if order_by:
            reverse = order_by.startswith("-")
            lines.sort(key=lambda x: x[0], reverse=reverse)
        obj_list = []
        resource_id_list = []
        for _, line in lines:
            resource_name = self.get_resource_name(line)
            if resource_name not in resource_id_list:
                resource_obj = self.resource_class()
                obj_list.append(self.clean_resource_obj(resource_obj, line))
                resource_id_list.append(resource_name)
        self.set_agg_method()
        return obj_list

    def get_resource_name(self, series):
        meta_field_list = [series["dimensions"][field] for field in self.resource_field_list]
        return ":".join(meta_field_list)

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
        """默认资源查询promql"""
        return self.meta_prom_with_container_cpu_usage_seconds_total

    def meta_prom_by_sort(self, order_by="", page_size=20):
        order_field = order_by.strip("-")

        meta_prom_func = f"meta_prom_with_{order_field}"
        if hasattr(self, meta_prom_func):
            if order_by.startswith("-"):
                # desc
                return f"topk({page_size}, {getattr(self, meta_prom_func)})"
            else:
                return f"topk({page_size}, {getattr(self, meta_prom_func)} * -1) * -1"
        raise NotImplementedError(f"metric: {order_field} not supported")

    @property
    def meta_prom_with_container_memory_working_set_bytes(self):
        return self.tpl_prom_with_nothing("container_memory_working_set_bytes")

    @property
    def meta_prom_with_container_cpu_usage_seconds_total(self):
        return self.tpl_prom_with_rate("container_cpu_usage_seconds_total")

    @property
    def meta_prom_with_kube_pod_cpu_requests_ratio(self):
        raise NotImplementedError("metric: [kube_pod_cpu_requests_ratio] not supported")

    @property
    def meta_prom_with_kube_pod_cpu_limits_ratio(self):
        raise NotImplementedError("metric: [kube_pod_cpu_limits_ratio] not supported")

    @property
    def meta_prom_with_kube_pod_memory_requests_ratio(self):
        raise NotImplementedError("metric: [kube_pod_memory_requests_ratio] not supported")

    @property
    def meta_prom_with_kube_pod_memory_limits_ratio(self):
        raise NotImplementedError("metric: [kube_pod_memory_limits_ratio] not supported")

    @property
    def meta_prom_with_container_network_receive_bytes_total(self):
        # 网络入流量（性能场景）维度层级: pod_name -> workload -> namespace -> cluster
        return self.tpl_prom_with_rate("container_network_receive_bytes_total", exclude="container_exclude")

    @property
    def meta_prom_with_container_network_transmit_bytes_total(self):
        # 网络出流量（性能场景）维度层级: pod_name -> workload -> namespace -> cluster
        return self.tpl_prom_with_rate("container_network_transmit_bytes_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_receive_bytes_total(self):
        # 网络入流量（网络场景）维度层级: pod_name -> service -> ingress -> namespace -> cluster
        return self.tpl_prom_with_rate("nw_container_network_receive_bytes_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_transmit_bytes_total(self):
        # 网络出流量（网络场景）维度层级: pod_name -> service -> ingress -> namespace -> cluster
        return self.tpl_prom_with_rate("nw_container_network_transmit_bytes_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_receive_packets_total(self):
        return self.tpl_prom_with_rate("nw_container_network_receive_packets_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_transmit_packets_total(self):
        return self.tpl_prom_with_rate("nw_container_network_transmit_packets_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_receive_drop_total(self):
        return self.tpl_prom_with_rate("nw_container_network_receive_drop_total", exclude="container_exclude")

    @property
    def meta_prom_with_nw_container_network_transmit_drop_total(self):
        return self.tpl_prom_with_rate("nw_container_network_transmit_drop_total", exclude="container_exclude")

    @property
    def meta_prom_with_container_cpu_cfs_throttled_ratio(self):
        raise NotImplementedError("metric: [container_cpu_cfs_throttled_ratio] not supported")

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        raise NotImplementedError(f"metric: [{metric_name}] not supported")

    def tpl_prom_with_nothing(self, metric_name, exclude=""):
        raise NotImplementedError(f"metric: [{metric_name}] not supported")

    @property
    def agg_method(self):
        return "last" if self.method == "sum" else self.method

    def add_filter(self, filter_obj):
        self.filter.add(filter_obj)


class K8sPodMeta(K8sResourceMeta, NetworkWithRelation):
    resource_field = "pod_name"
    resource_class = BCSPod
    column_mapping = {"workload_kind": "workload_type", "pod_name": "name"}
    only_fields = ["name", "namespace", "workload_type", "workload_name", "bk_biz_id", "bcs_cluster_id"]

    def nw_tpl_prom_with_rate(self, metric_name, exclude=""):
        metric_name = self.clean_metric_name(metric_name)
        if self.agg_interval:
            return f"""sum by (ingress, namespace, service) {self.label_join(exclude)}
            sum by (namespace, pod)
            ({self.agg_method}_over_time(rate({metric_name}[1m])[{self.agg_interval}:])))"""

        return f"""{self.agg_method} by (ingress, namespace, service) {self.label_join(exclude)}
                    sum by (namespace, pod)
                    (rate({metric_name}[1m])))"""

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        if metric_name.startswith("nw_"):
            # 网络场景下的pod数据，需要关联service 和 ingress
            return self.nw_tpl_prom_with_rate(metric_name, exclude)

        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, pod_name) "
                f"({self.agg_method}_over_time(rate("
                f"{metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m])[{self.agg_interval}:]))"
            )
        return (
            f"{self.method} by (workload_kind, workload_name, namespace, pod_name) "
            f"(rate({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m]))"
        )

    def tpl_prom_with_nothing(self, metric_name, exclude=""):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, pod_name) "
                f"({self.agg_method}_over_time("
                f"{metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[{self.agg_interval}:]))"
            )

        return (
            f"{self.method} by (workload_kind, workload_name, namespace, pod_name) "
            f"({metric_name}{{{self.filter.filter_string(exclude=exclude)}}})"
        )

    @property
    def meta_prom_with_container_cpu_cfs_throttled_ratio(self):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, pod_name) "
                f"({self.agg_method}_over_time((increase("
                f"container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
                f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m]))[{self.agg_interval}:]))"
            )

        return (
            f"{self.method} by (workload_kind, workload_name, namespace, pod_name) "
            f"((increase(container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
            f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m])))"
        )

    @property
    def meta_prom_with_kube_pod_cpu_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace,pod_name)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_cpu_system_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_requests_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_cpu_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace,pod_name)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_cpu_system_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_limits_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace,pod_name)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_requests_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace,pod_name)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_limits_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql


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

    def get_from_meta(self):
        return self.distinct(self.filter.filter_queryset)

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        # 网络场景下的网络指标，默认代了前缀，需要去掉
        if metric_name.startswith("nw_"):
            metric_name = metric_name[3:]

        if self.agg_interval:
            return (
                f"sum by (namespace) ({self.agg_method}_over_time(rate("
                f"{metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m])[{self.agg_interval}:]))"
            )
        return (
            f"{self.method} by (namespace) "
            f"(rate({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m]))"
        )

    def tpl_prom_with_nothing(self, metric_name, exclude=""):
        """按内存排序的资源查询promql"""
        if self.agg_interval:
            return (
                f"sum by (namespace) ({self.agg_method}_over_time("
                f"{metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[{self.agg_interval}:]))"
            )
        return f"{self.method} by (namespace) ({metric_name}{{{self.filter.filter_string(exclude=exclude)}}})"

    @property
    def meta_prom_with_container_cpu_cfs_throttled_ratio(self):
        if self.agg_interval:
            return (
                f"sum by (namespace) "
                f"({self.agg_method}_over_time((increase("
                f"container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
                f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m]))[{self.agg_interval}:]))"
            )

        return (
            f"{self.method} by (namespace) "
            f"((increase(container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
            f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m])))"
        )

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


class K8sIngressMeta(K8sResourceMeta, NetworkWithRelation):
    resource_field = "ingress"
    resource_class = BCSIngress
    column_mapping = {"ingress": "name"}

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        """
                promql示例:
                sum by (ingress, namespace) (count by (ingress, namespace, service, pod)
                (ingress_with_service_relation{ingress="bkunifyquery-test"})
                * on (namespace, service) group_left(pod)
                 (count by (service, namespace, pod)(pod_with_service_relation))
                * on (namespace, pod) group_left(ingress)
                sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total[1m])[1m:]))
        )
        """
        metric_name = self.clean_metric_name(metric_name)
        if self.agg_interval:
            return f"""sum by (ingress, namespace) {self.label_join(exclude)}
            sum by (namespace, pod)
            ({self.agg_method}_over_time(rate({metric_name}[1m])[{self.agg_interval}:])))"""

        return f"""{self.agg_method} by (ingress, namespace) {self.label_join(exclude)}
                    sum by (namespace, pod)
                    (rate({metric_name}[1m])))"""


class K8sServiceMeta(K8sResourceMeta, NetworkWithRelation):
    resource_field = "service"
    resource_class = BCSService
    column_mapping = {"service": "name"}

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        metric_name = self.clean_metric_name(metric_name)
        if self.agg_interval:
            return f"""sum by (ingress, namespace, service) {self.label_join(exclude)}
            sum by (namespace, pod)
            ({self.agg_method}_over_time(rate({metric_name}[1m])[{self.agg_interval}:])))"""

        return f"""{self.agg_method} by (ingress, namespace, service) {self.label_join(exclude)}
                    sum by (namespace, pod)
                    (rate({metric_name}[1m])))"""


class K8sWorkloadMeta(K8sResourceMeta):
    # todo 支持多workload
    resource_field = "workload_name"
    resource_class = BCSWorkload
    column_mapping = {"workload_kind": "type", "workload_name": "name"}
    only_fields = ["type", "name", "namespace", "bk_biz_id", "bcs_cluster_id"]

    @property
    def resource_field_list(self):
        return ["workload_kind", self.resource_field]

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace) ({self.agg_method}_over_time(rate("
                f"{metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m])[{self.agg_interval}:]))"
            )
        return (
            f"{self.method} by (workload_kind, workload_name, namespace) "
            f"(rate({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m]))"
        )

    def tpl_prom_with_nothing(self, metric_name, exclude=""):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace) ({self.agg_method}_over_time"
                f"({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[{self.agg_interval}:]))"
            )
        return (
            f"{self.method} by (workload_kind, workload_name, namespace) "
            f"({metric_name}{{{self.filter.filter_string(exclude=exclude)}}})"
        )

    @property
    def meta_prom_with_container_cpu_cfs_throttled_ratio(self):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace) "
                f"({self.agg_method}_over_time((increase("
                f"container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
                f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m]))[{self.agg_interval}:]))"
            )

        return (
            f"{self.method} by (workload_kind, workload_name, namespace) "
            f"((increase(container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
            f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m])))"
        )

    @property
    def meta_prom_with_kube_pod_cpu_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace)
    (count by (workload_kind, workload_name, namespace, pod_name) (
        container_cpu_usage_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_requests_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_cpu_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace)
    (count by (workload_kind, workload_name, namespace, pod_name) (
        container_cpu_usage_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_limits_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_requests_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace)
    (count by (workload_kind, workload_name, pod_name, namespace) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace) (
      kube_pod_container_resource_limits_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @classmethod
    def distinct(cls, queryset):
        query_set = (
            queryset.values('type', "name")
            .order_by("name")
            .annotate(
                distinct_name=Max("id"),
                workload=Concat(F("type"), Value(":"), F("name")),
            )
            .values("workload")
        )
        return query_set


class K8sContainerMeta(K8sResourceMeta):
    resource_field = "container_name"
    resource_class = BCSContainer
    column_mapping = {"workload_kind": "workload_type", "container_name": "name"}
    only_fields = ["name", "namespace", "pod_name", "workload_type", "workload_name", "bk_biz_id", "bcs_cluster_id"]

    @property
    def resource_field_list(self):
        return ["pod_name", self.resource_field]

    @classmethod
    def distinct(cls, queryset):
        query_set = (
            queryset.values('name')
            .order_by('name')
            .annotate(distinct_name=Max("id"))
            .annotate(container=F("name"))
            .values("container")
        )
        return query_set

    def tpl_prom_with_rate(self, metric_name, exclude=""):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, container_name, pod_name) "
                f"({self.agg_method}_over_time"
                f"(rate({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m])[{self.agg_interval}:]))"
            )
        return (
            f"{self.method} by (workload_kind, workload_name, namespace, container_name, pod_name) "
            f"(rate({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[1m]))"
        )

    def tpl_prom_with_nothing(self, metric_name, exclude=""):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, container_name, pod_name) "
                f"({self.agg_method}_over_time"
                f" ({metric_name}{{{self.filter.filter_string(exclude=exclude)}}}[{self.agg_interval}:]))"
            )
        """按内存排序的资源查询promql"""
        return (
            f"{self.method} by (workload_kind, workload_name, namespace, container_name, pod_name)"
            f" ({metric_name}{{{self.filter.filter_string(exclude=exclude)}}})"
        )

    @property
    def meta_prom_with_container_cpu_cfs_throttled_ratio(self):
        if self.agg_interval:
            return (
                f"sum by (workload_kind, workload_name, namespace, pod_name, container_name) "
                f"({self.agg_method}_over_time((increase("
                f"container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
                f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m]))[{self.agg_interval}:]))"
            )

        return (
            f"{self.method} by (workload_kind, workload_name, namespace, pod_name, container_name) "
            f"((increase(container_cpu_cfs_throttled_periods_total{{{self.filter.filter_string()}}}[1m]) / increase("
            f"container_cpu_cfs_periods_total{{{self.filter.filter_string()}}}[1m])))"
        )

    @property
    def meta_prom_with_kube_pod_cpu_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace, pod_name, container_name)
    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (
        container_cpu_usage_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace, container_name)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace, container_name) (
      kube_pod_container_resource_requests_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_cpu_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_cpu_usage_seconds_total
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace, pod_name, container_name)
    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (
        container_cpu_usage_seconds_total{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace, container_name)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace, container_name) (
      kube_pod_container_resource_limits_cpu_cores{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_requests_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace, pod_name, container_name)
    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace, container_name)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace, container_name) (
      kube_pod_container_resource_requests_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql

    @property
    def meta_prom_with_kube_pod_memory_limits_ratio(self):
        promql = (
            self.meta_prom_with_container_memory_working_set_bytes
            + '/ '
            + f"""(sum by (workload_kind, workload_name, namespace, pod_name, container_name)
    (count by (workload_kind, workload_name, pod_name, namespace, container_name) (
        container_memory_working_set_bytes{{{self.filter.filter_string()}}}
    ) *
    on(pod_name, namespace, container_name)
    group_right(workload_kind, workload_name)
    sum by (pod_name, namespace, container_name) (
      kube_pod_container_resource_limits_memory_bytes{{{self.filter.filter_string(exclude="workload")}}}
    )))"""
        )
        return promql


def load_resource_meta(resource_type: str, bk_biz_id: int, bcs_cluster_id: str) -> Optional[K8sResourceMeta]:
    resource_meta_map = {
        'node': K8sNodeMeta,
        'container': K8sContainerMeta,
        'container_name': K8sContainerMeta,
        'pod': K8sPodMeta,
        'pod_name': K8sPodMeta,
        'workload': K8sWorkloadMeta,
        'namespace': K8sNamespaceMeta,
        'ingress': K8sIngressMeta,
        'service': K8sServiceMeta,
    }
    if resource_type not in resource_meta_map:
        return None
    meta_class = resource_meta_map[resource_type]
    return meta_class(bk_biz_id, bcs_cluster_id)
