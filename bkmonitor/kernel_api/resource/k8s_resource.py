"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import operator
from functools import reduce

from django.core.exceptions import EmptyResultSet
from django.db.models import Q, QuerySet
from rest_framework import serializers

from bkmonitor.models import BCSContainer, BCSPod, BCSWorkload
from core.drf_resource import Resource

# 维度粒度档位，决定级联查询路由到哪张缓存表。
# 取 (目标维度 ∪ 过滤条件维度) 中的最细档：
# - 只有 workload 级约束时必须查 BCSWorkload，replica=0 / 完成态 Job 的负载
#   没有对应 Pod/容器行，查更细的表会漏掉它们；
# - 条件一旦包含 pod/container 级维度，该条件本身已断言 Pod/容器存在，
#   查更细的表既不会漏也不会错。
GRAIN_WORKLOAD = 0
GRAIN_POD = 1
GRAIN_CONTAINER = 2

DIMENSION_GRAIN = {
    "namespace": GRAIN_WORKLOAD,
    "workload_type": GRAIN_WORKLOAD,
    "workload_name": GRAIN_WORKLOAD,
    "pod_name": GRAIN_POD,
    "node_ip": GRAIN_POD,
    "container_name": GRAIN_CONTAINER,
}

# 各档位的源表与 维度 -> 模型字段 映射
GRAIN_TABLES = {
    GRAIN_WORKLOAD: (
        BCSWorkload,
        {"namespace": "namespace", "workload_type": "type", "workload_name": "name"},
    ),
    GRAIN_POD: (
        BCSPod,
        {
            "namespace": "namespace",
            "workload_type": "workload_type",
            "workload_name": "workload_name",
            "pod_name": "name",
            "node_ip": "node_ip",
        },
    ),
    GRAIN_CONTAINER: (
        BCSContainer,
        {
            "namespace": "namespace",
            "workload_type": "workload_type",
            "workload_name": "workload_name",
            "pod_name": "pod_name",
            "node_ip": "node_ip",
            "container_name": "name",
        },
    ),
}


class ListK8sResourceCandidatesResource(Resource):
    """容器资源过滤候选值检索（级联过滤）。

    基于监控 DB 缓存表（BCSWorkload/BCSPod/BCSContainer）返回指定维度的候选值，
    供日志平台等调用方做容器场景检索的字段联想。已选条件按维度粒度路由源表后
    逐项过滤；目标维度自身的已选条件不参与过滤（多选场景下取候选时必须忽略
    本维度已选值，否则候选只剩已选项）。

    缓存为当前态快照（25 分钟级同步）：已删除 Pod 的名字不在候选中；
    集群不属于请求业务时返回空而非报错。
    """

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            key = serializers.ChoiceField(label="维度", choices=list(DIMENSION_GRAIN))
            method = serializers.ChoiceField(label="匹配方式", choices=["eq", "include"], required=False, default="eq")
            value = serializers.ListField(
                label="维度值", child=serializers.CharField(allow_blank=False), allow_empty=False
            )

        bk_biz_id = serializers.IntegerField(label="业务ID")
        bcs_cluster_ids = serializers.ListField(label="集群ID列表", child=serializers.CharField(), allow_empty=False)
        resource_type = serializers.ChoiceField(label="目标维度", choices=list(DIMENSION_GRAIN))
        conditions = ConditionSerializer(label="已选过滤条件", many=True, required=False, default=list)
        query_string = serializers.CharField(label="候选值模糊检索", required=False, default="", allow_blank=True)
        page = serializers.IntegerField(label="页码", required=False, default=1, min_value=1)
        page_size = serializers.IntegerField(label="分页大小", required=False, default=500, min_value=1, max_value=1000)

    def perform_request(self, params):
        target: str = params["resource_type"]
        conditions = [cond for cond in params["conditions"] if cond["key"] != target]
        grain = max([DIMENSION_GRAIN[target]] + [DIMENSION_GRAIN[cond["key"]] for cond in conditions])
        offset = (params["page"] - 1) * params["page_size"]

        try:
            if target == "namespace" and grain == GRAIN_WORKLOAD:
                # workload 级约束下 namespace 候选取 workload ∪ pod 两表并集，
                # 兜住只有裸 Pod（无 ownerReferences，workload 字段为空串）的命名空间
                values = set(self._build_values_queryset(GRAIN_WORKLOAD, target, conditions, params))
                values |= set(self._build_values_queryset(GRAIN_POD, target, conditions, params))
                # 排序与 MySQL ci collation 行为对齐（大小写不敏感）
                ordered = sorted(values, key=str.lower)
                return {"count": len(ordered), "items": ordered[offset : offset + params["page_size"]]}

            queryset = self._build_values_queryset(grain, target, conditions, params)
            return {"count": queryset.count(), "items": list(queryset[offset : offset + params["page_size"]])}
        except EmptyResultSet:
            # filter_by_biz_id 对名下无集群的 BCS 空间直接抛出
            return {"count": 0, "items": []}

    @staticmethod
    def _build_values_queryset(grain: int, target: str, conditions: list[dict], params: dict) -> QuerySet:
        model, field_map = GRAIN_TABLES[grain]
        # filter_by_biz_id 承载共享集群租户隔离（负数 biz 仅放行授权 namespace），
        # 与请求集群求交集：未授权集群自然查空，不报错也不泄漏集群存在性
        queryset = model.objects.filter_by_biz_id(params["bk_biz_id"]).filter(
            bcs_cluster_id__in=params["bcs_cluster_ids"]
        )
        for cond in conditions:
            field = field_map[cond["key"]]
            if cond["method"] == "eq":
                queryset = queryset.filter(**{f"{field}__in": cond["value"]})
            else:
                queryset = queryset.filter(
                    reduce(operator.or_, (Q(**{f"{field}__icontains": value}) for value in cond["value"]))
                )

        target_field = field_map[target]
        if params["query_string"]:
            queryset = queryset.filter(**{f"{target_field}__icontains": params["query_string"]})
        # 排除空值：裸 Pod 的 workload 字段为空串，node_ip 可能为 NULL
        queryset = queryset.exclude(Q(**{target_field: ""}) | Q(**{f"{target_field}__isnull": True}))
        return queryset.values_list(target_field, flat=True).distinct().order_by(target_field)
