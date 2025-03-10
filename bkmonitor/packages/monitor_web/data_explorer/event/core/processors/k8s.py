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

from typing import Any, Dict, List

from .base import BaseEventProcessor


class K8sEventProcessor(BaseEventProcessor):
    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == ("kubernetes", "bcs")

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue

            processed_events.append(
                {
                    "time": {"value": 1736927543000, "alias": 1736927543000},
                    "source": {"value": "BCS", "alias": "Kubernetes/BCS"},
                    "event_name": {"value": "FailedMount", "alias": "卷挂载失效（FailedMount）"},
                    "event.content": {
                        "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                        "alias": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                        "detail": {
                            "bcs_cluster_id": {
                                "label": "集群",
                                "value": "BCS-K8S-90001",
                                # TODO 从 resource.scene_view.get_kubernetes_cluster_choices(bk_biz_id=bk_biz_id) 拿名称
                                # 后续可能会有多业务 ID 的场景
                                # 可以考虑维护一个 Map[Tuple(bk_biz_id, cluster_id), cluster_name] 的 map，便于扩展
                                # 其他涉及业务的可读数据也类似，可以考虑抽象出不同类型的 EventContext 便于多个 Processor 共享。
                                "alias": "[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)",
                                "type": "link",
                                # 带集群 ID 跳转到新版容器监控页面
                                "scenario": "容器监控",
                                "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001",
                            },
                            "namespace": {
                                "label": "NameSpace",
                                "value": "127.0.0.1",
                                "alias": "kube-system",
                                # 带 namespace & 集群 ID 跳转到新版容器监控页面
                                "type": "link",
                                "scenario": "容器监控",
                                "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
                            },
                            "name": {
                                "label": "工作负载",
                                "value": "bk-log-collector-fx97q",
                                "alias": "Pod/bk-log-collector-fx97q",
                                "type": "link",
                                "scenario": "容器监控",
                                # 带 namespace & bcs_cluster_id & workload_type & workload_name 跳转到新版容器监控页面
                                "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
                            },
                            "event.content": {
                                "label": "事件内容",
                                "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                                "failed to sync configmap cache: timed out waiting for the condition",
                                "alias": "MountVolume.SetUp failed for volume bk-log-main-config: "
                                "failed to sync configmap cache: timed out waiting for the condition",
                            },
                        },
                    },
                    "target": {
                        "value": "kubelet",
                        "alias": "BCS-K8S-90001/kube-system/Pod/bk-log-collector-fx97q",
                        "scenario": "容器监控",
                        # 带 namespace & bcs_cluster_id & workload_type & workload_name 跳转到新版容器监控页面
                        "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
                    },
                },
            )

        return processed_events
