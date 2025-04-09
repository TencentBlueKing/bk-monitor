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
from typing import Dict, List, Optional, Set

from apm_web.topo.handle.relation.define import SourceK8sPod, SourceService
from apm_web.topo.handle.relation.query import RelationQ
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.models import BCSPod
from bkmonitor.utils.cache import lru_cache_with_ttl


class ContainerHelper:
    @classmethod
    def list_pod_relations(cls, bk_biz_id, app_name, service_name, start_time, end_time):
        """获取服务的 Pod 关联信息"""
        return RelationQ.query(
            RelationQ.generate_q(
                bk_biz_id=bk_biz_id,
                source_info=SourceService(
                    apm_application_name=app_name,
                    apm_service_name=service_name,
                ),
                target_type=SourceK8sPod,
                start_time=start_time,
                end_time=end_time,
            )
        )

    @classmethod
    @lru_cache_with_ttl(ttl=60)
    def _validate_bk_biz_id(cls, bk_biz_id: int) -> int:
        """将负数项目空间 ID，转为关联业务 ID"""
        return validate_bk_biz_id(bk_biz_id)

    @classmethod
    def list_apm_service_workloads(
        cls, bk_biz_id: int, app_name: str, service_name: str, start_time: int, end_time: int
    ) -> List[Dict[str, str]]:
        """获取服务关联的工作负载
        为什么不直接使用 Pod 关联信息？
        - k8s 的设计理念是「控制器」，Pod 是当前存活的实例，而工作负载是 Pod 的模板。
        - Pod 可能会随时被销毁，而工作负载则会长期存在。
        - 将观测建立在工作负载上，可以更稳定地获取到服务的关联信息，并直观反映、对比发布前后 Pod 的变化（副本数、CPU、内存）。
        - btw：目前 APM 关联容器页面将 Pod 平铺的方式，缺少基于 Workload 聚合查看的能力，后续可以考虑结合新版容器监控优化。
        """
        relations = cls.list_pod_relations(bk_biz_id, app_name, service_name, start_time, end_time)

        pod_nams: Set[str] = set()
        namespaces: Set[str] = set()
        bcs_cluster_ids: Set[str] = set()
        for relation in relations:
            for node in relation.nodes:
                source_info = node.source_info.to_source_info()
                namespace: Optional[str] = source_info.get("namespace")
                bcs_cluster_id: Optional[str] = source_info.get("bcs_cluster_id")
                pod_name: Optional[str] = source_info.get("pod")
                if pod_name and bcs_cluster_id and namespace:
                    pod_nams.add(pod_name)
                    namespaces.add(namespace)
                    bcs_cluster_ids.add(bcs_cluster_id)

        if not pod_nams:
            return []

        workloads: List[Dict[str, str]] = BCSPod.objects.filter(
            bk_biz_id=cls._validate_bk_biz_id(bk_biz_id),
            bcs_cluster_id__in=bcs_cluster_ids,
            namespace__in=namespaces,
            name__in=pod_nams,
        ).values("bcs_cluster_id", "namespace", "workload_type", "workload_name")

        # 基于 Pod 查询的 Workloads 可能存在重复，需要去重
        duplicated_workloads: Set[frozenset] = set()
        for workload in workloads:
            workload["kind"] = workload.pop("workload_type")
            workload["name"] = workload.pop("workload_name")
            duplicated_workloads.add(frozenset(workload.items()))

        return [dict(workload) for workload in duplicated_workloads]
