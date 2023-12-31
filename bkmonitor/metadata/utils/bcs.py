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
from typing import Dict, List, Optional

from django.db.models import Q
from django.db.models.query import QuerySet

from metadata.models.bcs import BCSClusterInfo, PodMonitorInfo, ServiceMonitorInfo
from metadata.models.space import Space, SpaceResource, constants


def get_bcs_dataids(bk_biz_ids: list = None, cluster_ids: list = None, mode: str = "both"):
    """获取 bcs 下的数据源 ID
    NOTE: 升级空间后，bk_biz_id, 可能为负数，需要转换到空间属性
    """

    def _filter_cluster(bk_biz_ids: List, clusters: QuerySet) -> QuerySet:
        # 获取 bcs 空间信息
        bcs_spaces = get_bcs_space_by_biz(bk_biz_ids)
        # 过滤需要的参数
        bcs_project_id_list = []
        query_filter_params = Q()
        for sc in bcs_spaces:
            bcs_project_id_list.append(sc["space_code"])
            query_filter_params |= Q(space_type_id=sc["space_type_id"], space_id=sc["space_id"])

        # NOTE: 需要再通过空间获取关联资源的数据
        cluster_id_list = []
        if query_filter_params:
            dimension_list = []
            for obj in SpaceResource.objects.filter(query_filter_params, resource_type=constants.SpaceTypes.BCS.value):
                dimension_list.extend(obj.dimension_values)
            # 过滤使用的共享集群
            cluster_id_list = [
                d["cluster_id"] for d in dimension_list if d["cluster_type"] == "shared" and d["namespace"]
            ]

        # 过滤记录
        clusters = clusters.filter(
            Q(bk_biz_id__in=(bk_biz_ids or []))
            | Q(project_id__in=bcs_project_id_list)
            | Q(cluster_id__in=cluster_id_list)
        )

        return clusters

    # 基于BCS集群信息获取dataid列表，用于过滤
    clusters = BCSClusterInfo.objects.all().only("cluster_id", "K8sMetricDataID", "CustomMetricDataID")
    # 如果集群 id 存在，则以集群 ID 为准
    if cluster_ids:
        clusters = clusters.filter(cluster_id__in=cluster_ids)
    elif bk_biz_ids:
        clusters = _filter_cluster(bk_biz_ids, clusters)

    result_cluster_ids = []
    # dataid集合
    data_ids = set()
    # dataid与集群映射关系
    data_id_cluster_map = {"built_in_metric_data_id_list": []}
    # 判定获取bcs_data_id的类型
    need_k8s_metric = mode == "both" or mode == "k8s"
    need_custom_metric = mode == "both" or mode == "custom"
    for cluster in clusters:
        result_cluster_ids.append(cluster.cluster_id)
        if need_k8s_metric and cluster.K8sMetricDataID not in data_ids:
            data_ids.add(cluster.K8sMetricDataID)
            data_id_cluster_map[cluster.K8sMetricDataID] = cluster.cluster_id
            data_id_cluster_map["built_in_metric_data_id_list"].append(cluster.K8sMetricDataID)
        if need_custom_metric and cluster.CustomMetricDataID not in data_ids:
            data_ids.add(cluster.CustomMetricDataID)
            data_id_cluster_map[cluster.CustomMetricDataID] = cluster.cluster_id
    for resource in (
        ServiceMonitorInfo.objects.filter(cluster_id__in=result_cluster_ids, is_common_data_id=False)
        .values("bk_data_id", "cluster_id")
        .distinct()
    ):
        if resource["bk_data_id"] not in data_ids:
            data_ids.add(resource["bk_data_id"])
            data_id_cluster_map[resource["bk_data_id"]] = resource["cluster_id"]
    for resource in (
        PodMonitorInfo.objects.filter(cluster_id__in=result_cluster_ids, is_common_data_id=False)
        .values("bk_data_id", "cluster_id")
        .distinct()
    ):
        if resource["bk_data_id"] not in data_ids:
            data_ids.add(resource["bk_data_id"])
            data_id_cluster_map[resource["bk_data_id"]] = resource["cluster_id"]
    return data_ids, data_id_cluster_map


def get_bcs_space_by_biz(bk_biz_ids: Optional[List] = None) -> List[Dict]:
    """通过业务获取到 BCS 空间信息"""
    # 如果传递的业务 ID 为空，则直接返回
    if not bk_biz_ids:
        return []
    # 针对业务 ID 为负数的，返回相应的空间信息
    id_list = [abs(bid) for bid in bk_biz_ids if bid < 0]
    # 过滤对应的空间 code
    spaces = Space.objects.filter(id__in=id_list).values("space_type_id", "space_id", "space_code")
    return [sc for sc in spaces if sc["space_code"]]
