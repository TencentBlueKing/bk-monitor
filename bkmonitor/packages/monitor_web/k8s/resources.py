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
from collections import OrderedDict
from typing import Dict, List

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Count
from rest_framework import serializers

from apm_web.utils import get_interval_number
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.models import BCSWorkload
from core.drf_resource import Resource, resource
from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.core.meta import K8sResourceMeta, load_resource_meta
from monitor_web.k8s.scenario import get_metrics


class SpaceRelatedSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def validate_bk_biz_id(self, bk_biz_id):
        return validate_bk_biz_id(bk_biz_id)


class ListBCSCluster(Resource):
    RequestSerializer = SpaceRelatedSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        return resource.scene_view.get_kubernetes_cluster_choices(bk_biz_id=bk_biz_id)


class WorkloadOverview(Resource):
    class RequestSerializer(SpaceRelatedSerializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群id")
        namespace = serializers.CharField(required=False, label="命名空间")
        query_string = serializers.CharField(required=False, label="名字过滤")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]

        queryset = BCSWorkload.objects.filter(
            bk_biz_id=bk_biz_id,
            bcs_cluster_id=bcs_cluster_id,
        )

        # 如果前端传值则添加过滤
        if validated_request_data.get("namespace"):
            # 支持多个ns传递， 默认半角逗号连接
            ns_list = validated_request_data["namespace"].split(",")
            queryset = queryset.filter(namespace__in=ns_list)
        if validated_request_data.get("query_string"):
            queryset = queryset.filter(name__icontains=validated_request_data["query_string"])

        # 统计 workload type 对应的 count
        """
        数据结构示例:
        [
            {"type": "xxx", "count": 0}
        ]
        """
        result = queryset.values('type').annotate(count=Count('name', distinct=True))
        kind_map = OrderedDict.fromkeys(["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"], 0)
        for item in result:
            if item["type"] not in kind_map:
                kind_map[item["type"]] = item["count"]
            else:
                kind_map[item["type"]] += item["count"]

        return [[key, value] for key, value in kind_map.items()]


class ScenarioMetricList(Resource):
    """
    获取场景下指标列表
    # performance场景
    [{'id': 'CPU',
      'name': 'CPU',
      'children': [{'id': 'container_cpu_usage_seconds_total', 'name': 'CPU使用量'},
       {'id': 'kube_pod_cpu_requests_ratio', 'name': 'CPU request使用率'},
       {'id': 'kube_pod_cpu_limits_ratio', 'name': 'CPU limit使用率'}]},
     {'id': 'memory',
      'name': '内存',
      'children': [{'id': 'container_memory_working_set_bytes', 'name': '内存使用量(Working Set)'},
       {'id': 'kube_pod_memory_requests_ratio', 'name': '内存 request使用率'},
       {'id': 'kube_pod_memory_limits_ratio', 'name': '内存 limit使用率'}]}]
    """

    class RequestSerializer(SpaceRelatedSerializer):
        scenario = serializers.ChoiceField(required=True, label="接入场景", choices=["performance"])

    def perform_request(self, validated_request_data):
        # 使用量、limit使用率、request使用率
        return get_metrics(validated_request_data["scenario"])


class GetScenarioMetric(Resource):
    """
    获取场景下指标详情
    """

    class RequestSerializer(SpaceRelatedSerializer):
        scenario = serializers.ChoiceField(required=True, label="接入场景", choices=["performance"])
        metric_id = serializers.CharField(required=True, label="指标id")

    def perform_request(self, validated_request_data):
        metric_list = get_metrics(validated_request_data["scenario"])
        metric_id = validated_request_data["metric_id"]
        for category in metric_list:
            for metric in category["children"]:
                if metric["id"] == metric_id:
                    return metric
        return {}


class MetricGraphQueryConfig(Resource):
    """
    获取指标图表查询配置
    需要和前端一并确定各式，参考数据检索的请求配置
    """

    def perform_request(self, validated_request_data):
        pass


class GetResourceDetail(Resource):
    class RequestSerializer(SpaceRelatedSerializer):
        # 公共参数
        bcs_cluster_id: str = serializers.CharField(required=True)
        namespace: str = serializers.CharField(required=True)
        resource_type: str = serializers.ChoiceField(
            required=True, choices=["pod", "workload", "container", "cluster"], label="资源类型"
        )
        # 私有参数
        pod_name: str = serializers.CharField(required=False, allow_null=True)
        container_name: str = serializers.CharField(required=False, allow_null=True)
        workload_name: str = serializers.CharField(required=False, allow_null=True)
        workload_type: str = serializers.CharField(required=False, allow_null=True)

    def validate_request_data(self, request_data: Dict):
        resource_type = request_data["resource_type"]
        if resource_type == "pod":
            fields = ["pod_name"]
            self.validate_field_exist(resource_type, fields, request_data)

        elif resource_type == "workload":
            fields = ["workload_name", "workload_type"]
            self.validate_field_exist(resource_type, fields, request_data)
        elif resource_type == "container":
            fields = ["pod_name", "container_name"]
            self.validate_field_exist(resource_type, fields, request_data)

        return super().validate_request_data(request_data)

    @classmethod
    def validate_field_exist(cls, resource_type: str, fields: List[str], request_data: Dict) -> None:
        for field in fields:
            if not request_data.get(field):
                raise serializers.ValidationError(
                    f"{field} cannot be null or empty when resource_type is '{resource_type}'."
                )

    @classmethod
    def link_to_string(cls, item: Dict):
        """
        当返回的资源详情中 type == "link" 时,

        转化 type = "string", 且 value = value.value

        """
        if item.get("type") == "link":
            item["type"] = "string"
            item["value"] = item["value"]["value"]

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]

        resource_type = validated_request_data["resource_type"]

        # 不同的 resource_type 对应不同要调用的接口，并且记录额外要传递的参数
        resource_router: Dict[str, List[Dict]] = {
            "cluster": [resource.scene_view.get_kubernetes_cluster, []],
            "pod": [resource.scene_view.get_kubernetes_pod, ["namespace", "pod_name"]],
            "workload": [resource.scene_view.get_kubernetes_workload, ["namespace", "workload_name", "workload_type"]],
            "container": [resource.scene_view.get_kubernetes_container, ["namespace", "pod_name", "container_name"]],
        }
        # 构建同名字典 -> {"field":validated_request_data["field"]}
        extra_request_arg = {key: validated_request_data[key] for key in resource_router[resource_type][1]}

        # 调用对应的资源类型的接口，返回对应的接口数据
        items = resource_router[resource_type][0](
            **{"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id, **extra_request_arg}
        )

        for item in items:
            self.link_to_string(item)

        return items


class FilterDictSerializer(SpaceRelatedSerializer):
    # 用于精确过滤查询
    filter_dict = serializers.DictField(required=False, allow_null=True)

    def validate_filter_dict(self, value):
        field_map = {
            "container": "container_name",
            "pod": "pod_name",
        }
        for key in field_map:
            if key in value:
                value[field_map[key]] = value.pop(key)

        return value


class ListK8SResources(Resource):
    """获取K8s资源列表"""

    class RequestSerializer(FilterDictSerializer):
        bcs_cluster_id = serializers.CharField(required=True)
        resource_type = serializers.ChoiceField(
            required=True,
            choices=["pod", "workload", "namespace", "container", "ingress", "service"],
            label="资源类型",
        )
        # 用于模糊查询
        query_string = serializers.CharField(required=False, default="", allow_blank=True, label="名字过滤")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        # 场景，后续持续补充， 目前暂时没有用的地方， 先传上
        scenario = serializers.ChoiceField(required=True, label="场景", choices=["performance"])
        # 历史出现过的资源
        with_history = serializers.BooleanField(required=False, default=False)
        # 分页
        page_size = serializers.IntegerField(required=False, default=5, label="分页大小")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        page_type = serializers.ChoiceField(
            required=False,
            choices=["scrolling", "traditional"],
            default="scrolling",
            label="分页标识",
        )
        order_by = serializers.ChoiceField(
            required=False,
            choices=["desc", "asc"],
            default="desc",
        )
        method = serializers.ChoiceField(required=False, choices=["max", "avg", "min", "sum", "count"], default="sum")
        column = serializers.ChoiceField(
            required=False,
            choices=[
                'container_cpu_usage_seconds_total',
                'kube_pod_cpu_requests_ratio',
                'kube_pod_cpu_limits_ratio',
                'container_memory_working_set_bytes',
                'kube_pod_memory_requests_ratio',
                'kube_pod_memory_limits_ratio',
                'container_cpu_cfs_throttled_ratio',
                'container_network_transmit_bytes_total',
                'container_network_receive_bytes_total',
                'nw_container_network_transmit_bytes_total',
                'nw_container_network_receive_bytes_total',
                'nw_container_network_receive_packets_dropped_ratio',
                'nw_container_network_transmit_packets_dropped_ratio',
                'nw_container_network_transmit_packets_dropped_total',
                'nw_container_network_receive_packets_dropped_total',
                'nw_container_network_receive_packets_total',
                'nw_container_network_transmit_packets_total',
            ],
            default="container_cpu_usage_seconds_total",
        )

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        bcs_cluster_id: str = validated_request_data["bcs_cluster_id"]
        with_history: bool = validated_request_data["with_history"]

        # 1. 基于resource_type 加载对应资源元信息
        resource_meta: K8sResourceMeta = load_resource_meta(
            validated_request_data["resource_type"], bk_biz_id, bcs_cluster_id
        )
        # 2.0 基于filter_dict 加载 filter
        self.add_filter(resource_meta, validated_request_data["filter_dict"])
        if validated_request_data["query_string"]:
            # 2.1 基于query_string 加载 filter
            resource_meta.filter.add(
                load_resource_filter(
                    validated_request_data["resource_type"],
                    validated_request_data["query_string"],
                    fuzzy=True,
                )
            )
        resource_list = []
        total_count = 0
        # scrolling 分页特性
        page_count = validated_request_data["page"] * validated_request_data["page_size"]
        # 当 with_history = False 对应左侧列表查询
        if not with_history:
            try:
                page_size: int = validated_request_data["page_size"]
                page: int = validated_request_data["page"]

                # 将传统分页转化为滚动分页
                if validated_request_data["page_type"] == "scrolling":
                    page_size = page_count
                    page = 1

                obj_list = resource_meta.distinct(resource_meta.get_from_meta())

                paginator = Paginator(obj_list, page_size)
                total_count = paginator.count
                for k8s_resource in paginator.get_page(page).object_list:
                    if isinstance(k8s_resource, dict):
                        resource_list.append(k8s_resource)
                    else:
                        resource_list.append(k8s_resource.to_meta_dict())
            except FieldError:
                pass
            return {"count": total_count, "items": resource_list}

        # 右侧列表查询, 优先历史数据。 如果有排序，基于分页参数得到展示总量，并根据历史数据补齐
        # 3.0 基于promql 查询历史上报数据。 确认数据是否达到分页要求
        order_by = validated_request_data["order_by"]
        column = validated_request_data["column"]
        order_by = column if order_by == "asc" else "-{}".format(column)

        history_resource_list = resource_meta.get_from_promql(
            validated_request_data["start_time"],
            validated_request_data["end_time"],
            order_by,
            page_count,
            validated_request_data["method"],
        )
        resource_id_set = set()
        for rs in history_resource_list:
            record = rs.to_meta_dict()
            resource_list.append(record)
            resource_id_set.add(tuple(sorted(record.items())))
        # promql 查询数据量不足，从db中补充
        try:
            meta_resource_list = [k8s_resource.to_meta_dict() for k8s_resource in resource_meta.get_from_meta()]
        except FieldError:
            meta_resource_list = []
        all_resource_id_set = {tuple(sorted(rs.items())) for rs in meta_resource_list} | resource_id_set
        total_count = len(all_resource_id_set)

        if len(resource_list) < page_count:
            # 基于需要返回的数量，进行分页
            # 3.1 promql上报数据包含了meta数据，需要去重
            for rs_dict in meta_resource_list:
                if tuple(sorted(rs_dict.items())) not in resource_id_set:
                    resource_list.append(rs_dict)
                    if len(resource_list) >= page_count:
                        break
        else:
            resource_list = resource_list[:page_count]
        return {"count": total_count, "items": resource_list}

    def add_filter(self, meta: K8sResourceMeta, filter_dict: Dict):
        """
        filter_dict = {
            "pod": ["pod1", "pod2"],
            "namespace": ["namespace1", "namespace2"],
            "workload": ["Deployment:xx", "Deployment:zz"],
            "container": ["container1", "container2"],
            }
        """
        for resource_type, values in filter_dict.items():
            meta.filter.add(load_resource_filter(resource_type, values))


class ResourceTrendResource(Resource):
    """资源数据视图"""

    class RequestSerializer(FilterDictSerializer):
        bcs_cluster_id = serializers.CharField(required=True)
        column = serializers.ChoiceField(
            required=True,
            choices=[
                'container_cpu_usage_seconds_total',
                'kube_pod_cpu_requests_ratio',
                'kube_pod_cpu_limits_ratio',
                'container_memory_working_set_bytes',
                'kube_pod_memory_requests_ratio',
                'kube_pod_memory_limits_ratio',
                'container_cpu_cfs_throttled_ratio',
                'container_network_transmit_bytes_total',
                'container_network_receive_bytes_total',
                'nw_container_network_transmit_bytes_total',
                'nw_container_network_receive_bytes_total',
                'nw_container_network_receive_packets_dropped_ratio',
                'nw_container_network_transmit_packets_dropped_ratio',
                'nw_container_network_transmit_packets_dropped_total',
                'nw_container_network_receive_packets_dropped_total',
                'nw_container_network_receive_packets_total',
                'nw_container_network_transmit_packets_total',
            ],
        )
        resource_type = serializers.ChoiceField(
            required=True,
            choices=["pod", "workload", "namespace", "container"],
            label="资源类型",
        )
        method = serializers.ChoiceField(required=True, choices=["max", "avg", "min", "sum", "count"])
        resource_list = serializers.ListField(required=True, label="资源列表")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        bcs_cluster_id: str = validated_request_data["bcs_cluster_id"]
        resource_type: str = validated_request_data["resource_type"]
        resource_list: List[str] = validated_request_data["resource_list"]
        if not resource_list:
            return []
        start_time: int = validated_request_data["start_time"]
        end_time: int = validated_request_data["end_time"]

        # 1. 基于resource_type 加载对应资源元信息
        resource_meta: K8sResourceMeta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)
        agg_method = validated_request_data["method"]
        resource_meta.set_agg_method(agg_method)
        resource_meta.set_agg_interval(start_time, end_time)
        ListK8SResources().add_filter(resource_meta, validated_request_data["filter_dict"])
        column = validated_request_data["column"]
        series_map = {}
        metric = resource.k8s.get_scenario_metric(metric_id=column, scenario="performance", bk_biz_id=bk_biz_id)
        unit = metric["unit"]
        if resource_type == "workload":
            # workload 单独处理
            promql_list = []
            for wl in resource_list:
                # workload 资源，需要带上namespace 信息: blueking|Deployment:bk-monitor-web
                try:
                    ns, wl = wl.split("|")
                except ValueError:
                    # 不符合预期的数据， ns置空
                    ns = ""
                tmp_filter_chain = []
                tmp_filter_chain.append(load_resource_filter(resource_type, [wl]))
                tmp_filter_chain.append(load_resource_filter("namespace", [ns]))
                [resource_meta.filter.add(filter_obj) for filter_obj in tmp_filter_chain]
                promql_list.append(getattr(resource_meta, f"meta_prom_with_{column}"))
                [resource_meta.filter.remove(filter_obj) for filter_obj in tmp_filter_chain]
            promql = " or ".join(promql_list)
        else:
            resource_meta.filter.add(load_resource_filter(resource_type, resource_list))
            # 不用topk 因为有resource_list
            promql = getattr(resource_meta, f"meta_prom_with_{column}")
        interval = get_interval_number(start_time, end_time, interval=60)
        query_params = {
            "bk_biz_id": bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": promql,
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
        series = resource.grafana.graph_unify_query(query_params)["series"]
        max_data_point = 0
        for line in series:
            if line["datapoints"]:
                for point in reversed(line["datapoints"]):
                    if point[0]:
                        max_data_point = max(max_data_point, point[1])

        for line in series:
            resource_name = resource_meta.get_resource_name(line)
            if resource_type == "workload":
                # workload 补充namespace
                resource_name = f"{line['dimensions']['namespace']}|{resource_name}"
            if line["datapoints"][-1][1] == max_data_point:
                datapoints = line["datapoints"][-1:]
            else:
                datapoints = []
            series_map[resource_name] = {"datapoints": datapoints, "unit": unit, "value_title": metric["name"]}

        return [{"resource_name": name, column: info} for name, info in series_map.items()]
