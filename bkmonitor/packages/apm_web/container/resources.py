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

import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from itertools import count

from rest_framework import serializers

from apm_web.container.helpers import ContainerHelper
from core.drf_resource import Resource, api, resource
from monitor_web.collecting.constant import CollectStatus


class PodDetailResource(Resource):
    """获取 Pod 详情"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
        namespace = serializers.CharField(required=False, allow_null=True)
        pod_name = serializers.CharField(required=False, allow_null=True)

    def perform_request(self, validated_data):
        from bkmonitor.models import BCSPod

        query_params = {}
        if validated_data.get("bcs_cluster_id"):
            query_params["bcs_cluster_id"] = validated_data["bcs_cluster_id"]
        if validated_data.get("namespace"):
            query_params["namespace"] = validated_data["namespace"]
        if validated_data.get("pod_name"):
            query_params["name"] = validated_data["pod_name"]

        if BCSPod.objects.filter(**query_params).exists():
            # 存在则交给 Pod 详情接口
            # 获取业务 Id (Pod 可能存在于空间下但是不属于此空间的业务)
            bk_biz_id = BCSPod.objects.filter(**query_params).first().bk_biz_id
            return resource.scene_view.get_kubernetes_pod(**{**validated_data, "bk_biz_id": bk_biz_id})

        res = [{"key": "monitor_status", "name": "状态", "type": "status", "value": {"text": "已销毁", "type": "failed"}}]
        if validated_data.get("pod_name"):
            res.append({"key": "pod_name", "name": "Pod 名称", "type": "string", "value": validated_data["pod_name"]})

        if validated_data.get("bcs_cluster_id"):
            res.append(
                {"key": "bcs_cluster_id", "name": "集群 ID", "type": "string", "value": validated_data["bcs_cluster_id"]}
            )
        if validated_data.get("namespace"):
            res.append(
                {"key": "namespace", "name": "NameSpace", "type": "string", "value": validated_data["namespace"]}
            )

        return res


class ListServicePodsResource(Resource):
    """获取关联 Pod 列表"""

    class SpanSourceType:
        """span关联容器来源"""

        SPAN = "通过 Span 发现"
        SERVICE = "通过 Service 发现"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务 ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        service_name = serializers.CharField(label="服务名称")
        span_id = serializers.CharField(label="Span Id", required=False)

    def perform_request(self, validated_data):
        # 获取服务关联的 Pod 节点
        bk_biz_id = validated_data["bk_biz_id"]
        app_name = validated_data.pop("app_name")
        service_name = validated_data.pop("service_name")

        # 获取节点关系
        relations = ContainerHelper.list_pod_relations(
            bk_biz_id,
            app_name,
            service_name,
            validated_data.pop("start_time"),
            validated_data.pop("end_time"),
        )
        # 批量提取所有节点
        all_nodes = [n for r in relations for n in r.nodes]

        # 生成ID
        id_generator = count(1)
        preassigned_ids = [next(id_generator) for _ in all_nodes]

        # 构建查询条件
        query_values_mapping = defaultdict(set)
        for node in all_nodes:
            source_info = node.source_info.to_source_info()
            if bcs_cluster_id := source_info.get("bcs_cluster_id"):
                query_values_mapping["bcs_cluster_id__in"].add(bcs_cluster_id)
            if namespace := source_info.get("namespace"):
                query_values_mapping["namespace__in"].add(namespace)
            if pod := source_info.get("pod"):
                query_values_mapping["name__in"].add(pod)

        from bkmonitor.models import BCSBase, BCSPod

        current_pods = {
            (i["bcs_cluster_id"], i["namespace"], i["name"]): i
            for i in BCSPod.objects.filter(**query_values_mapping).values(
                "bcs_cluster_id", "namespace", "name", "monitor_status"
            )
        }

        batch_size = max(len(all_nodes) // (os.cpu_count() * 2), 10)
        have_data_pods, no_data_pods = [], []

        def process_batch(nodes_batch, ids_batch):
            batch_results = []
            for node, node_id in zip(nodes_batch, ids_batch):
                source_info = node.source_info.to_source_info()
                source_info.update(
                    {
                        "id": node_id,
                        "pod_name": source_info.get("pod"),
                        "name": source_info.pop("pod"),
                        "app_name": app_name,
                        "service_name": service_name,
                    }
                )

                key = (source_info.get("bcs_cluster_id"), source_info.get("namespace"), source_info.get("pod_name"))

                pod_info = current_pods.get(key)
                if not pod_info:
                    source_info["status"] = CollectStatus.NODATA
                    batch_results.append(("no", source_info))
                    continue

                status_map = {
                    BCSBase.METRICS_STATE_STATE_SUCCESS: CollectStatus.SUCCESS,
                    BCSBase.METRICS_STATE_FAILURE: CollectStatus.FAILED,
                }

                source_info["status"] = status_map.get(pod_info["monitor_status"], CollectStatus.NODATA)

                batch_results.append(("have" if pod_info["monitor_status"] in status_map else "no", source_info))

            return batch_results

        # 动态调整线程池
        optimal_worker = min(32, (os.cpu_count() or 1) * 2)
        with ThreadPoolExecutor(max_workers=optimal_worker) as executor:
            futures = []
            for i in range(0, len(all_nodes), batch_size):
                batch_nodes = all_nodes[i : i + batch_size]
                batch_ids = preassigned_ids[i : i + batch_size]
                futures.append(executor.submit(process_batch, batch_nodes, batch_ids))
            for future in futures:
                try:
                    for result_type, info in future.result():
                        if result_type == "have":
                            have_data_pods.append(info)
                        else:
                            no_data_pods.append(info)
                except Exception:
                    continue

        all_pods = have_data_pods + no_data_pods

        if not validated_data.get("span_id"):
            return all_pods

        # 优先展示此 span 关联的 Pod 并补充来源信息
        span_detail = api.apm_api.query_span_detail(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            span_id=validated_data["span_id"],
        )
        if not span_detail:
            return all_pods
        res = []
        for i in all_pods:
            if i.get("pod_name") == span_detail.get("resource", {}).get("k8s.pod.name"):
                i["source"] = self.SpanSourceType.SPAN
                res.insert(0, i)
            else:
                i["source"] = self.SpanSourceType.SERVICE
                res.append(i)

        return res
