"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from collections import OrderedDict
from typing import Any, Literal

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from rest_framework import serializers

from apm_web.utils import get_interval_number
from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.models import BCSWorkload
from core.drf_resource import Resource, resource
from metadata import models
from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.core.meta import K8sResourceMeta, load_resource_meta
from monitor_web.k8s.scenario import get_all_metrics, get_metrics


class SpaceRelatedSerializer(serializers.Serializer):
    # 忽略业务id关联, 容器场景只依赖集群id进行数据路由即可。
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    # def validate_bk_biz_id(self, bk_biz_id):
    #     try:
    #         bk_biz_id = validate_bk_biz_id(bk_biz_id)
    #     except NoRelatedResourceError:
    #         bk_biz_id = bk_biz_id
    #     return bk_biz_id


class ListBCSCluster(Resource):
    RequestSerializer = SpaceRelatedSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        cluster_list = resource.scene_view.get_kubernetes_cluster_choices(bk_biz_id=bk_biz_id)
        cluster_id_list = [cluster["id"] for cluster in cluster_list]
        event_data_id_values = models.BCSClusterInfo.objects.filter(
            cluster_id__in=cluster_id_list, status=models.BCSClusterInfo.CLUSTER_STATUS_RUNNING
        ).values("cluster_id", "K8sEventDataID")
        event_data_id_map = {}
        for data_id_info in event_data_id_values:
            event_data_id_map[data_id_info["cluster_id"]] = data_id_info["K8sEventDataID"]
        for cluster in cluster_list:
            event_data_id = event_data_id_map.get(cluster["id"]) or 0
            data_source_result = models.DataSourceResultTable.objects.filter(bk_data_id=event_data_id).first()
            result_table_id = ""
            if data_source_result:
                result_table_id = data_source_result.table_id
            cluster["event_table_id"] = result_table_id
        return cluster_list


class WorkloadOverview(Resource):
    class RequestSerializer(SpaceRelatedSerializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群id")
        namespace = serializers.CharField(required=False, label="命名空间")
        query_string = serializers.CharField(required=False, label="名字过滤")

        def validate_bk_biz_id(self, bk_biz_id):
            try:
                bk_biz_id = validate_bk_biz_id(bk_biz_id)
            except NoRelatedResourceError:
                bk_biz_id = bk_biz_id
            return bk_biz_id

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
        result = queryset.values("type").annotate(count=Count("name", distinct=True))
        kind_map = OrderedDict.fromkeys(["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"], 0)
        for item in result:
            if item["type"] not in kind_map:
                kind_map[item["type"]] = item["count"]
            else:
                kind_map[item["type"]] += item["count"]

        return [[key, value] for key, value in kind_map.items()]


class NamespaceWorkloadOverview(Resource):
    class RequestSerializer(SpaceRelatedSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True, label="集群id")
        query_string = serializers.CharField(required=False, label="名字过滤", default="", allow_blank=True)
        page_size = serializers.IntegerField(required=False, default=5, label="分页大小")
        page = serializers.IntegerField(required=False, default=1, label="页数")

        def validate_bk_biz_id(self, bk_biz_id):
            try:
                bk_biz_id = validate_bk_biz_id(bk_biz_id)
            except NoRelatedResourceError:
                bk_biz_id = bk_biz_id
            return bk_biz_id

    @classmethod
    def _get_workload_count(cls, workload_overview: list[list[int]]) -> int:
        return sum([item[1] for item in workload_overview])

    @classmethod
    def _get_workload_count_by_queryset(cls, queryset: QuerySet[BCSWorkload]) -> int:
        queryset = queryset.values("type").annotate(count=Count("name", distinct=True))
        return sum([item["count"] for item in queryset])

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        bcs_cluster_id: str = validated_request_data["bcs_cluster_id"]
        query_string: str = validated_request_data["query_string"]

        workload_count: int = 0
        filter_dict: dict[str, list[str]] = {}
        page: int = validated_request_data["page"]
        page_size: int = validated_request_data["page_size"]
        queryset: QuerySet[BCSWorkload] = BCSWorkload.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        if query_string:
            namespaces: list[str] = []
            queryset = queryset.filter(Q(namespace__icontains=query_string) | Q(name__icontains=query_string))
            for item in queryset.values("type", "namespace").order_by().annotate(count=Count("name", distinct=True)):
                namespaces.append(item["namespace"])
                workload_count += item["count"]

            filter_dict["namespace"] = list(set(namespaces))
        else:
            workload_count: int = self._get_workload_count_by_queryset(queryset)

        namespace_page: dict[str, Any] = ListK8SResources().perform_request(
            {
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
                "resource_type": "namespace",
                "scenario": "performance",
                "query_string": "",
                "filter_dict": filter_dict,
                "page": page,
                "page_size": page_size,
                "page_type": "scrolling",
                "with_history": False,
                "start_time": 0,
                "end_time": 0,
            }
        )
        namespace_page["workload_count"] = workload_count

        for namespace_info in namespace_page.get("items", []):
            query_kwargs: dict[str, Any] = {
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
                "namespace": namespace_info["namespace"],
            }
            workload_overview: list[list[int]] = WorkloadOverview().perform_request(
                {
                    **query_kwargs,
                    "query_string": query_string,
                }
            )
            namespace_workload_count: int = self._get_workload_count(workload_overview)

            query_from: str = "workload"
            if not namespace_workload_count and query_string:
                query_from: str = "namespace"
                # 获取不到说明关键字仅命中 Namespace，去掉关键字再请求一遍 Workload
                workload_overview = WorkloadOverview().perform_request(query_kwargs)
                namespace_workload_count = self._get_workload_count(workload_overview)

            namespace_info["query_from"] = query_from
            namespace_info["workload_overview"] = workload_overview
            namespace_info["workload_count"] = namespace_workload_count

        return namespace_page


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
        scenario = serializers.ChoiceField(
            required=True, label="接入场景", choices=["performance", "network", "capacity", "tke_gpu"]
        )

    def perform_request(self, validated_request_data):
        # 使用量、limit使用率、request使用率
        return get_metrics(validated_request_data["scenario"])


class GetScenarioMetric(Resource):
    """
    获取场景下指标详情
    """

    class RequestSerializer(SpaceRelatedSerializer):
        scenario = serializers.ChoiceField(
            required=True, label="接入场景", choices=["performance", "network", "capacity", "tke_gpu"]
        )
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
        namespace: str = serializers.CharField(required=False)
        resource_type: str = serializers.ChoiceField(
            required=True,
            choices=["pod", "workload", "container", "cluster", "service", "ingress", "node"],
            label="资源类型",
        )
        # 私有参数
        pod_name: str = serializers.CharField(required=False, allow_null=True)
        container_name: str = serializers.CharField(required=False, allow_null=True)
        workload_name: str = serializers.CharField(required=False, allow_null=True)
        workload_type: str = serializers.CharField(required=False, allow_null=True)
        service_name: str = serializers.CharField(required=False, allow_null=True)
        ingress_name: str = serializers.CharField(required=False, allow_null=True)
        node_name: str = serializers.CharField(required=False, allow_null=True)

    def validate_request_data(self, request_data: dict):
        resource_type = request_data["resource_type"]
        resource_require_fields = {
            "pod": ["namespace", "pod_name"],
            "workload": ["namespace", "workload_name", "workload_type"],
            "container": ["namespace", "pod_name", "container_name"],
            "service": ["namespace", "service_name"],
            "ingress": ["namespace", "ingress_name"],
            "node": ["node_name"],
        }

        if resource_require_fields.get(resource_type):
            fields = resource_require_fields[resource_type]
            self.validate_field_exist(resource_type, fields, request_data)

        return super().validate_request_data(request_data)

    @classmethod
    def validate_field_exist(cls, resource_type: str, fields: list[str], request_data: dict) -> None:
        for field in fields:
            if not request_data.get(field):
                raise serializers.ValidationError(
                    f"{field} cannot be null or empty when resource_type is '{resource_type}'."
                )

    @classmethod
    def link_to_string(cls, item: dict):
        """
        当返回的资源详情中 type == "link" 时,

        转化 type = "string", 且 value = value.value

        """
        if item.get("type") == "link":
            item["type"] = "string"
            item["value"] = item["value"]["value"]

    def get_pod_resource_relation(
        self, bk_biz_id: int, fields: dict, resource_type: Literal["service", "ingress"]
    ) -> list[str]:
        """
        通过 promql 查询 pod 与 service 以及 service 与 ingress 的关联关系
        """
        labels = ",".join([f'{key}="{value}"' for key, value in fields.items()])
        if resource_type == "service":
            promql = f"""count by (namespace, service, pod)
            (pod_with_service_relation{{{labels}}})
            """
        elif resource_type == "ingress":
            promql = f"""count by (bk_biz_id, bcs_cluster_id, pod,namespace, service,ingress, pod)
            (ingress_with_service_relation{{{labels}}})
            """

        query_params = {
            "bk_biz_id": bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": promql,
                    "interval": 60,
                    "alias": "result",
                }
            ],
            "expression": "",
            "alias": "result",
            "start_time": int(time.time()) - 3600,
            "end_time": int(time.time()),
            "slimit": 10001,
            "down_sample_range": "",
        }
        series = resource.grafana.graph_unify_query(query_params)["series"]

        # 获取 dimensions 中 resource_type 对应的 value
        resource_list: list[str] = []
        for line in series:
            resource_list.append(line["dimensions"][resource_type])

        return resource_list

    def add_pod_service_ingress_relation(self, items: list[dict], validated_request_data: dict):
        """
        为 items 添加 ingress/service 关联信息
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        pod = validated_request_data["pod_name"]
        namespace = validated_request_data["namespace"]

        value: list[str] = []
        service_list: list[str] = self.get_pod_resource_relation(
            bk_biz_id, {"namespace": namespace, "pod": pod}, "service"
        )
        for service in service_list:
            ingress_list: list[str] = self.get_pod_resource_relation(
                bk_biz_id, {"namespace": namespace, "service": service}, "ingress"
            )
            if not ingress_list:
                value.append(f"-/{service}")
            else:
                [value.append(f"{ingress}/{service}") for ingress in ingress_list]

        items.append(
            {
                "key": "ingress_service_relation",
                "name": "ingress/service关联",
                "type": "list",
                "value": value,
            }
        )

    def remove_items_with_keys(self, items: list[dict], keys: list[str]) -> list[dict]:
        """
        删除 items 中的指定 key 的 item
        """
        key_set = set(keys)
        return [item for item in items if "key" in item and item["key"] not in key_set]

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]

        resource_type = validated_request_data["resource_type"]

        # 不同的 resource_type 对应不同要调用的接口，并且记录额外要传递的参数
        resource_router: dict[str, list[dict]] = {
            "cluster": [resource.scene_view.get_kubernetes_cluster, []],
            "pod": [resource.scene_view.get_kubernetes_pod, ["namespace", "pod_name"]],
            "workload": [
                resource.scene_view.get_kubernetes_workload,
                ["namespace", "workload_name", "workload_type"],
            ],
            "container": [
                resource.scene_view.get_kubernetes_container,
                ["namespace", "pod_name", "container_name"],
            ],
            "service": [
                resource.scene_view.get_kubernetes_service,
                ["namespace", "service_name"],
            ],
            "ingress": [
                resource.scene_view.get_kubernetes_ingress,
                ["namespace", "ingress_name"],
            ],
            "node": [resource.scene_view.get_kubernetes_node, ["node_name"]],
        }
        # 构建同名字典 -> {"field":validated_request_data["field"]}
        extra_request_arg = {key: validated_request_data[key] for key in resource_router[resource_type][1]}

        # 调用对应的资源类型的接口，返回对应的接口数据
        items: list[dict] = resource_router[resource_type][0](
            **{
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
                **extra_request_arg,
            }
        )

        resource_ignore_keys: dict[str, list[str]] = {
            "pod": [
                "request_cpu_usage_ratio",  # CPU使用率（request）
                "limit_cpu_usage_ratio",  # CPU使用率（limit）
                "request_memory_usage_ratio",  # 内存使用率（request）
                "limit_memory_usage_ratio",  # 内存使用率（limit）
                "resource_usage_cpu",
                "resource_usage_memory",
                "resource_usage_disk",
                "resource_requests_cpu",
                "resource_limits_cpu",
                "resource_requests_memory",
                "resource_limits_memory",
            ],
            "container": [
                "resource_usage_cpu",  # CPU 使用量
                "resource_usage_memory",  # 内存使用量
                "resource_usage_disk",  # 磁盘使用量
            ],
            "node": [
                "system_cpu_summary_usage",
                "system_mem_pct_used",
                "system_io_util",
                "system_disk_in_use",
                "system_load_load15",
            ],
            "cluster": [
                "cpu_usage_ratio",  # CPU使用率
                "memory_usage_ratio",  # 内存使用率
                "disk_usage_ratio",  # 磁盘使用率
            ],
        }
        if resource_ignore_keys.get(resource_type):
            items = self.remove_items_with_keys(items, resource_ignore_keys[resource_type])

        if resource_type == "pod":
            self.add_pod_service_ingress_relation(items, validated_request_data)

        # 获取 pod 关于 service 和 ingress 的联系
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
            choices=["pod", "workload", "namespace", "container", "ingress", "service", "node", "cluster"],
            label="资源类型",
        )
        # 用于模糊查询
        query_string = serializers.CharField(required=False, default="", allow_blank=True, label="名字过滤")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        # 场景，后续持续补充， 目前暂时没有用的地方， 先传上
        scenario = serializers.ChoiceField(
            required=True, label="场景", choices=["performance", "network", "capacity", "tke_gpu"]
        )
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
            required=False, choices=get_all_metrics(), default="container_cpu_usage_seconds_total"
        )

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        bcs_cluster_id: str = validated_request_data["bcs_cluster_id"]
        with_history: bool = validated_request_data["with_history"]
        resource_type: str = validated_request_data["resource_type"]
        query_string: str = validated_request_data["query_string"]
        filter_dict: dict = validated_request_data["filter_dict"]
        page: int = validated_request_data["page"]
        page_size: int = validated_request_data["page_size"]
        scenario: str = validated_request_data["scenario"]

        # 1. 基于resource_type 加载对应资源元信息
        resource_meta: K8sResourceMeta = load_resource_meta(resource_type, bk_biz_id, bcs_cluster_id)
        # 2.0 基于filter_dict 加载 filter
        self.add_filter(resource_meta, filter_dict)
        if query_string:
            # 2.1 基于query_string 加载 filter
            resource_meta.filter.add(
                load_resource_filter(
                    resource_type,
                    query_string,
                    fuzzy=True,
                )
            )
        obj_list = None
        resource_list = []
        total_count = 0
        # scrolling 分页特性
        page_count = page * page_size
        # 当 with_history = False 对应左侧列表查询
        if not with_history:
            try:
                # 将传统分页转化为滚动分页
                if validated_request_data["page_type"] == "scrolling":
                    page_size = page_count
                    page = 1

                obj_list = resource_meta.distinct(resource_meta.get_from_meta())
            except FieldError:
                # namespace 层级下尝试根据filter 类型进行重新查询
                if scenario == "network":
                    obj_list = resource_meta.distinct(resource_meta.retry_get_from_meta())

            if obj_list is not None:
                paginator = Paginator(obj_list, page_size)
                total_count = paginator.count
                for k8s_resource in paginator.get_page(page).object_list:
                    if isinstance(k8s_resource, dict):
                        resource_list.append(k8s_resource)
                    else:
                        resource_list.append(k8s_resource.to_meta_dict())

            return {"count": total_count, "items": resource_list}

        # 右侧列表查询, 优先历史数据。 如果有排序，基于分页参数得到展示总量，并根据历史数据补齐
        # 3.0 基于promql 查询历史上报数据。 确认数据是否达到分页要求
        order_by = validated_request_data["order_by"]
        column = validated_request_data["column"]

        if scenario == "network":
            column = column if column.startswith("nw_") else "nw_" + column

            if not resource.k8s.get_scenario_metric(scenario="network", metric_id=column, bk_biz_id=bk_biz_id):
                # 网络场景默认指标，用nw_container_network_receive_bytes_total
                column = "nw_container_network_receive_bytes_total"
            # 网络场景，pod不需要workload相关信息
            if resource_meta.resource_field == "pod_name":
                resource_meta.only_fields = ["name", "namespace", "bk_biz_id", "bcs_cluster_id"]

        if scenario == "capacity":
            if not resource.k8s.get_scenario_metric(scenario="capacity", metric_id=column, bk_biz_id=bk_biz_id):
                # 容量场景默认指标: node_boot_time_seconds(用以获取node列表)
                column = "node_boot_time_seconds"

        order_by = column if order_by == "asc" else f"-{column}"

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
            meta_resource_list: list[dict] = [
                k8s_resource.to_meta_dict() for k8s_resource in resource_meta.get_from_meta()
            ]
            if resource_meta.resource_field == "pod_name" and scenario == "network":
                # 网络场景，pod不需要workload相关信息
                [rs.pop("workload") for rs in meta_resource_list if rs.get("workload")]
        except FieldError:
            meta_resource_list = []
            # namespace 层级下尝试根据filter 类型进行重新查询
            if scenario == "network":
                meta_resource_list = resource_meta.distinct(resource_meta.retry_get_from_meta())
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

    def set_default_column(self, scenario: str, column: str):
        """
        根据场景设置默认列
        """
        if scenario == "network":
            # 网络场景默认指标，用nw_container_network_receive_bytes_total
            if not column.startswith("nw_"):
                column = "nw_container_network_receive_bytes_total"

        # 如果是容量场景，则使用容量的指标: node_boot_time_seconds(用以获取node列表)
        if scenario == "capacity":
            column = "node_boot_time_seconds"

    def add_filter(self, meta: K8sResourceMeta, filter_dict: dict):
        """
        filter_dict = {
            "pod": ["pod1", "pod2"],
            "namespace": ["namespace1", "namespace2"],
            "workload": ["Deployment:xx", "Deployment:zz"],
            "container": ["container1", "container2"],
            }
        """
        for resource_type, values in filter_dict.items():
            # 如果 filter_dict 有传入 namespace, 则删除实例化时添加的 namespace_filter
            # 并以传入的为主
            if resource_type == "namespace":
                for filter_obj in meta.filter.filters.values():
                    if filter_obj.resource_type == "namespace":
                        meta.filter.remove(filter_obj)

            meta.filter.add(load_resource_filter(resource_type, values))


class ResourceTrendResource(Resource):
    """资源数据视图"""

    class RequestSerializer(FilterDictSerializer):
        bcs_cluster_id = serializers.CharField(required=True)
        column = serializers.ChoiceField(required=True, choices=get_all_metrics())
        resource_type = serializers.ChoiceField(
            required=True,
            choices=["pod", "workload", "namespace", "container", "ingress", "service", "node", "cluster"],
            label="资源类型",
        )
        method = serializers.ChoiceField(required=True, choices=["max", "avg", "min", "sum", "count"])
        resource_list = serializers.ListField(required=True, label="资源列表")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        scenario = serializers.ChoiceField(
            required=False,
            label="场景",
            choices=["performance", "network", "capacity", "tke_gpu"],
            default="performance",
        )

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        bcs_cluster_id: str = validated_request_data["bcs_cluster_id"]
        resource_type: str = validated_request_data["resource_type"]
        resource_list: list[str] = validated_request_data["resource_list"]
        scenario: str = validated_request_data["scenario"]
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
        metric = resource.k8s.get_scenario_metric(metric_id=column, scenario=scenario, bk_biz_id=bk_biz_id)
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
            if resource_type != "cluster":
                resource_meta.filter.add(load_resource_filter(resource_type, resource_list))
            # 不用topk 因为有resource_list
            promql = getattr(resource_meta, f"meta_prom_with_{column}")

        series = self.get_series_with_promql(promql, start_time, end_time, bk_biz_id)
        max_data_point = 0
        for line in series:
            if line["datapoints"]:
                for point in reversed(line["datapoints"]):
                    if point[0] is not None:
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
            series_map[resource_name] = {
                "datapoints": datapoints,
                "unit": unit,
                "value_title": metric["name"],
            }

        return [{"resource_name": name, column: info} for name, info in series_map.items()]

    def get_series_with_promql(self, promql: str, start_time: int, end_time: int, bk_biz_id: int) -> list[dict]:
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
        return series
