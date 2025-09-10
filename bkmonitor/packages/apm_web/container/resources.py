# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from rest_framework import serializers

from apm_web.container.helpers import ContainerHelper
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.request import get_request
from core.drf_resource import CacheResource, Resource, api, resource
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


class ListServicePodsResource(CacheResource):
    """获取关联 Pod 列表"""

    cache_type = CacheType.APM(60 * 5)

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

    def round_to_five_minutes(self, timestamps):
        """将时间戳按5分钟取整"""
        if timestamps is None:
            return None
        period = 5 * 60  # 5分钟秒数
        return int(timestamps // period) * period

    def _wrap_request(self):
        """
        将原有的request方法替换为支持缓存的request方法
        """

        def func_key_generator(resource):
            request = get_request()
            try:
                start_time = request.GET.get("start_time") or request.POST.get("start_time")
                end_time = request.GET.get("end_time") or request.POST.get("end_time")

                start = self.round_to_five_minutes(int(start_time)) if start_time else 0
                end = self.round_to_five_minutes(int(end_time)) if end_time else 0
            except (AttributeError, ValueError, TypeError):
                start = end = 0

            key = f"{resource.__self__.__class__.__module__}.{resource.__self__.__class__.__name__}"

            if all((start, end)):
                return f"{key}.{start}_{end}"
            return key

        self.request = using_cache(
            cache_type=self.cache_type,
            backend_cache_type=self.backend_cache_type,
            user_related=self.cache_user_related,
            compress=self.cache_compress,
            is_cache_func=self.cache_write_trigger,
            func_key_generator=func_key_generator,
        )(self.request)

    def perform_request(self, validated_data):
        # 获取服务关联的 Pod 节点
        bk_biz_id = validated_data["bk_biz_id"]
        app_name = validated_data.pop("app_name")
        service_name = validated_data.pop("service_name")

        relations = ContainerHelper.list_pod_relations(
            bk_biz_id,
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

        have_data_pods = []
        no_data_pods = []
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
                        have_data_pods.append(source_info)
                    elif pod_info.get("monitor_status") == BCSBase.METRICS_STATE_FAILURE:
                        source_info["status"] = CollectStatus.FAILED
                        have_data_pods.append(source_info)
                    else:
                        source_info["status"] = CollectStatus.NODATA
                        no_data_pods.append(source_info)
                else:
                    source_info["status"] = CollectStatus.NODATA
                    no_data_pods.append(source_info)

                index += 1

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
