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

from typing import Optional

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, resource

from . import handler, serializers


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        start_time: Optional[int] = validated_request_data.get("start_time")
        end_time: Optional[int] = validated_request_data.get("end_time")

        base_q: QueryConfigBuilder = (
            QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.BK_APM))
            .time_field("time")
            .interval(60)
            .filter(**{"dimensions.bk_biz_id": bk_biz_id})
        )
        k8s_q: QueryConfigBuilder = (
            base_q.table("k8s_event")
            .alias("a")
            .metric(field="_index", method="SUM", alias="a")
            .filter(**{"dimensions.bcs_cluster_id": "BCS-K8S-00000"})
        )
        system_q = base_q.table("system_event").alias("b").metric(field="_index", method="SUM", alias="b")

        qs: UnifyQuerySet = (
            handler.EventQueryHelper.time_range_qs(start_time=start_time, end_time=end_time)
            .scope(bk_biz_id)
            .add_query(k8s_q)
            .add_query(system_q)
            .expression("a + b")
        )
        return resource.grafana.graph_unify_query(qs.config)


class EventListResource(Resource):
    RequestSerializer = serializers.EventListRequestSerializer

    def perform_request(self, validated_request_data):
        return {
            "list": [
                {
                    "time": 1736927543000,
                    "event_name": {
                        "key": "event_name",
                        "value": "OOM",
                        "display_key": "事件名",
                        "display_value": "进程 OOM",
                    },
                    "source": {
                        "key": "source",
                        "value": "SYSTEM",
                        "key_display": "来源",
                        "display_value": "系统 / 主机",
                    },
                    "content": {
                        "key": "event.content",
                        "value": "oom",
                        "display_key": "事件内容",
                        "display_value": "发现进程 OOM 异常事件（进程: chrome）",
                    },
                    "target": {
                        "key": "target",
                        "value": "target",
                        "display_key": "目标",
                        "display_value": "127.0.0.1",
                        "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
                    },
                    "dimensions": [
                        {
                            "key": "dimensions.bk_target_cloud_id",
                            "value": "0",
                            "display_key": "管控区域",
                            "display_value": "直连区域 [0]",
                        },
                        {
                            "key": "dimensions.bk_target_ip",
                            "value": "127.0.0.1",
                            "display_key": "IP",
                            "display_value": "127.0.0.1",
                        },
                    ],
                    "origin": {
                        "time": 1737281113,
                        "dimensions.ip": "127.0.0.1",
                        "dimensions.task_memcg": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                        "dimensions.message": "系统发生OOM异常事件",
                        "dimensions.process": "chrome",
                        "dimensions.constraint": "CONSTRAINT_MEMCG",
                        "dimensions.task": "chrome",
                        "dimensions.bk_biz_id": "11",
                        "dimensions.oom_memcg": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                        "dimensions.bk_target_cloud_id": "0",
                        "dimensions.bk_target_ip": "127.0.0.1",
                        "dimensions.bk_cloud_id": "0",
                        "event.content": "oom",
                        "event.count": 1,
                        "target": "0:127.0.0.1",
                        "event_name": "OOM",
                    },
                },
                {
                    "time": 1736927543000,
                    "event_name": {
                        "key": "event_name",
                        "value": "FailedMount",
                        "key_display": "事件名",
                        "display_value": "FailedMount（卷挂载失效）",
                    },
                    "source": {
                        "key": "source",
                        "value": "BCS",
                        "key_display": "来源",
                        "display_value": "Kubernetes / BCS（蓝鲸容器平台）",
                    },
                    "content": {
                        "key": "event.content",
                        "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                        "display_key": "事件内容",
                        "display_value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                    },
                    "target": {
                        "key": "target",
                        "value": "target",
                        "display_key": "目标",
                        "display_value": "BCS-K8S-90001 / kube-system / Pod / bk-log-collector-fx97q",
                        "url": "https://bk.monitor.com/k8s-new/?kind=Pod&name=bk-log-collector-fx97q&"
                        "bcs_cluster_id=BCS-K8S-90001&namespace=bk-system",
                    },
                    "dimensions": [
                        {
                            "key": "dimensions.bcs_cluster_id",
                            "value": "BCS-K8S-90001",
                            "display_key": "集群",
                            "display_value": "[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)",
                        },
                        {
                            "key": "dimensions.namespace",
                            "value": "kube-system",
                            "display_key": "Namespace",
                            "display_value": "kube-system",
                        },
                        {
                            "key": "dimensions.name",
                            "value": "bk-log-collector-fx97q",
                            "display_key": "工作负载",
                            "display_value": "Pod / bk-log-collector-fx97q",
                        },
                    ],
                    "origin_data": {
                        "dimensions.apiVersion": "v1",
                        "dimensions.bcs_cluster_id": "BCS-K8S-90001",
                        "dimensions.bk_biz_id": "7",
                        "dimensions.host": "127.0.0.1",
                        "dimensions.kind": "Pod",
                        "dimensions.name": "bk-log-collector-fx97q",
                        "dimensions.namespace": "kube-system",
                        "dimensions.type": "Warning",
                        "dimensions.uid": "bbeea166-7b09-487a-bed5-66756c25b7b5",
                        "event.content": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                        "event.count": 1,
                        "event_name": "FailedMount",
                        "target": "kubelet",
                        "time": "1736927543000",
                    },
                },
            ]
        }
