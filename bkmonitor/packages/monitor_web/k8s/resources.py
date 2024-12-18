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

from bkmonitor.models import BCSWorkload
from core.drf_resource import Resource, resource
from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.core.meta import K8sResourceMeta, load_resource_meta
from monitor_web.k8s.scenario import get_metrics


class ListBCSCluster(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        return resource.scene_view.get_kubernetes_cluster_choices(bk_biz_id=bk_biz_id)


class WorkloadOverview(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
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
            queryset = queryset.filter(namespace=validated_request_data["namespace"])
        if validated_request_data.get("query_string"):
            queryset = queryset.filter(name__icontains=validated_request_data["query_string"])

        # 统计 workload type 对应的 count
        """
        数据结构示例:
        [
            {"type": "xxx", "count": 0}
        ]
        """
        result = queryset.values('type').annotate(count=Count('name'))
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
      'children': [{'id': 'container_memory_rss', 'name': '内存使用量(rss)'},
       {'id': 'kube_pod_memory_requests_ratio', 'name': '内存 request使用率'},
       {'id': 'kube_pod_memory_limits_ratio', 'name': '内存 limit使用率'}]}]
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.ChoiceField(required=True, label="接入场景", choices=["performance"])

    def perform_request(self, validated_request_data):
        # 使用量、limit使用率、request使用率
        return get_metrics(validated_request_data["scenario"])


class MetricGraphQueryConfig(Resource):
    """
    获取指标图表查询配置
    需要和前端一并确定各式，参考数据检索的请求配置
    """

    def perform_request(self, validated_request_data):
        pass


class GetResourceDetail(Resource):
    class RequestSerializer(serializers.Serializer):
        # 公共参数
        bcs_cluster_id: str = serializers.CharField(required=True)
        bk_biz_id: int = serializers.IntegerField(required=True)
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


class ListK8SResources(Resource):
    """获取K8s资源列表"""

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        resource_type = serializers.ChoiceField(
            required=True,
            choices=["pod", "workload", "namespace", "container"],
            label="资源类型",
        )
        # 用于模糊查询
        query_string = serializers.CharField(required=False, default="", allow_blank=True, label="名字过滤")
        # 用于精确过滤查询
        filter_dict = serializers.DictField(required=False, allow_null=True)
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
            default="traditional",
            label="分页标识",
        )
        order_by = serializers.ChoiceField(
            required=False, default="-cpu", label="排序", choices=["cpu", "-cpu", "mem", "-mem"]
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
        # 当 with_history = False 对应左侧列表查询
        if not with_history:
            try:
                total_count: int = resource_meta.get_from_meta().count()
                resource_meta = self.get_resource_meta_by_pagination(resource_meta, validated_request_data)
                resource_list = [k8s_resource.to_meta_dict() for k8s_resource in resource_meta.filter.query_set]
            except FieldError:
                pass
            return {"count": total_count, "items": resource_list}

        if with_history:
            page_count = 0
            # 右侧列表查询, 优先历史数据。 如果有排序，基于分页参数得到展示总量，并根据历史数据补齐
            # 3.0 基于promql 查询历史上报数据。 确认数据是否达到分页要求
            if validated_request_data["order_by"]:
                page_count = validated_request_data["page"] * validated_request_data["page_size"]

            history_resource_list = resource_meta.get_from_promql(
                validated_request_data["start_time"],
                validated_request_data["end_time"],
                validated_request_data["order_by"],
                page_count,
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
            # 不需要分页，全量返回
            page_count = total_count if page_count == 0 else page_count

            if len(resource_list) < page_count:
                # 基于需要返回的数量，进行分页
                # 3.1 promql上报数据包含了meta数据，需要去重
                for rs_dict in meta_resource_list:
                    if tuple(sorted(rs_dict.items())) not in resource_id_set:
                        resource_list.append(rs_dict)
                        if len(resource_list) >= total_count:
                            break

        return {"count": total_count, "items": resource_list}

    def get_resource_meta_by_pagination(
        self, resource_meta: K8sResourceMeta, validated_request_data: Dict
    ) -> K8sResourceMeta:
        """
        获取分页后的 K8sResourceMeta
        """
        page_size: int = validated_request_data["page_size"]
        page: int = validated_request_data["page"]
        page_type: str = validated_request_data["page_type"]

        # 将传统分页转化为滚动分页
        if page_type == "scrolling":
            page_size = page * page_size
            page = 1

        # 添加默认 id 排序
        resource_meta.filter.query_set = resource_meta.get_from_meta().order_by("id")

        paginator = Paginator(resource_meta.filter.query_set, page_size)
        resource_meta.filter.query_set = paginator.get_page(page).object_list
        return resource_meta

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
    """资源趋势缩略图"""

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        resource_type = serializers.ChoiceField(
            required=True,
            choices=["pod", "node", "workload", "namespace", "container"],
            label="资源类型",
        )
        resource_list = serializers.ListField(required=True, label="资源列表")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
