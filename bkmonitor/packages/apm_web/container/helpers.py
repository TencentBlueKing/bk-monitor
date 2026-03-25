"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from apm_web.strategy.dispatch.entity import EntitySet
from apm_web.topo.handle.relation.define import SourceK8sPod, SourceService
from apm_web.topo.handle.relation.query import RelationQ


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
    def get_service_related_k8s_targets(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
    ) -> list[dict[str, Any]]:
        """获取服务关联的标准化 K8S 容器负载目标列表。

        基于 EntitySet 获取原始负载数据并标准化字段名，过滤不完整记录。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :return: 标准化容器负载目标列表
        """
        entity_set: EntitySet = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name, service_names=[service_name])

        workload_field_mapping: dict[str, str] = {
            "bcs_cluster_id": "bcs_cluster_id",
            "namespace": "namespace",
            "kind": "workload_kind",
            "name": "workload_name",
        }

        return [
            target
            for workload in entity_set.get_workloads(service_name)
            # 过滤不完整的记录
            if all(
                (
                    target := {
                        standard_key: workload.get(raw_key, "")
                        for raw_key, standard_key in workload_field_mapping.items()
                    }
                ).values()
            )
        ]
