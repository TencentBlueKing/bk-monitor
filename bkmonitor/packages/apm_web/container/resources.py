# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db.models import Q
from rest_framework import serializers

from apm_web.container.helpers import ContainerHelper
from core.drf_resource import Resource


class ListServicePodsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务 ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        service_name = serializers.CharField(label="服务名称")

        # 以下为 GetKubernetesPodList 接口的参数
        keyword = serializers.CharField(required=False, allow_null=True, label="查询关键词", allow_blank=True)
        status = serializers.CharField(required=False, allow_null=True, label="状态过滤", allow_blank=True)
        condition_list = serializers.ListField(required=False, allow_null=True)
        filter_dict = serializers.DictField(required=False, allow_null=True, label="枚举列过滤")
        sort = serializers.CharField(required=False, allow_null=True, label="排序", allow_blank=True)
        page = serializers.IntegerField(required=False, allow_null=True, label="页码")
        page_size = serializers.IntegerField(required=False, allow_null=True, label="每页条数")

    def perform_request(self, validated_data):
        # 获取服务关联的 Pod 节点
        relations = ContainerHelper.list_pod_relations(
            validated_data["bk_biz_id"],
            validated_data.pop("app_name"),
            validated_data.pop("service_name"),
            validated_data.pop("start_time"),
            validated_data.pop("end_time"),
        )
        # 三个额外的 Pod 过滤条件
        query_values_mapping = {
            "bcs_cluster_id__in": set(),
            "namespace__in": set(),
            "name__in": set(),
        }
        for r in relations:
            for n in r.nodes:
                source_info = n.source_info.to_source_info()

                bcs_cluster_id = source_info.get("bcs_cluster_id")
                if bcs_cluster_id:
                    query_values_mapping["bcs_cluster_id__in"].add(bcs_cluster_id)

                namespace = source_info.get("namespace")
                if namespace:
                    query_values_mapping["namespace__in"].add(namespace)

                pod = source_info.get("pod")
                if pod:
                    query_values_mapping["name__in"].add(pod)

        from monitor_web.scene_view.resources import GetKubernetesPodList

        class ChildPodList(GetKubernetesPodList):
            def add_condition_filter(self, params):
                """
                附加额外的过滤条件 只获取和此服务有关联的 Pod
                如果相同 PodName 分别存在不同集群或不同命名空间中 可能会导致查询出非关联的数据(因为条件为 3 个 in 查询)
                因为这种情况基本没有所有这里不处理这种情况
                """
                super(ChildPodList, self).add_condition_filter(params)
                self.query_set_list += [Q(**{k: v}) for k, v in query_values_mapping.items()]

        pod_resource_instance = ChildPodList()
        response = pod_resource_instance(**validated_data)  # noqa
        return response
