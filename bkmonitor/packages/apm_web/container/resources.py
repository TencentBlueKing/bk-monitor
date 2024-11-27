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

from rest_framework import serializers

from apm_web.container.helpers import ContainerHelper
from core.drf_resource import Resource
from monitor_web.collecting.constant import CollectStatus


class ListServicePodsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务 ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        service_name = serializers.CharField(label="服务名称")

    def perform_request(self, validated_data):
        # 获取服务关联的 Pod 节点
        app_name = validated_data.pop("app_name")
        service_name = validated_data.pop("service_name")

        relations = ContainerHelper.list_pod_relations(
            validated_data["bk_biz_id"],
            app_name,
            service_name,
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

        from bkmonitor.models import BCSBase, BCSPod

        current_pods = {
            (i["bcs_cluster_id"], i["namespace"], i["name"]): i
            for i in BCSPod.objects.filter(**query_values_mapping).values(
                "bcs_cluster_id", "namespace", "name", "monitor_status"
            )
        }

        res = []
        index = 1
        for i in relations:
            for n in i.nodes:
                source_info = n.source_info.to_source_info()
                source_info["id"] = index
                source_info["pod_name"] = source_info.pop("pod")
                # 前端侧边栏需要有 name 字段 单独加上
                source_info["name"] = source_info["pod_name"]
                source_info["app_name"] = app_name
                source_info["service_name"] = service_name
                key = (source_info.get("bcs_cluster_id"), source_info.get("namespace"), source_info.get("pod_name"))
                if key in current_pods:
                    pod_info = current_pods[key]
                    if pod_info.get("monitor_status") == BCSBase.METRICS_STATE_STATE_SUCCESS:
                        source_info["status"] = CollectStatus.SUCCESS
                    elif pod_info.get("monitor_status") == BCSBase.METRICS_STATE_FAILURE:
                        source_info["status"] = CollectStatus.FAILED
                    else:
                        source_info["status"] = CollectStatus.NODATA
                else:
                    source_info["status"] = CollectStatus.NODATA

                res.append(source_info)
                index += 1

        return res
