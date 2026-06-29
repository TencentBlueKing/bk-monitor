"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections.abc import Callable
from typing import Any

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import EventServiceRelation
from bkmonitor.utils.cache import lru_cache_with_ttl
from monitor_web.data_explorer.event.constants import EventCategory

logger = logging.getLogger(__name__)


class EventHandler:
    @classmethod
    @lru_cache_with_ttl(maxsize=1024, ttl=60)
    def fetch_relations(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        def _get_node(*args):
            return ServiceHandler.list_nodes(bk_biz_id, app_name, service_name)[0]

        service_relations: dict[str, list[dict[str, Any]]] = cls.fetch_relations_by_nodes(
            bk_biz_id, app_name, [service_name], _get_node
        )
        return service_relations.get(service_name, [])

    @classmethod
    def fetch_relations_by_nodes(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_names: list[str],
        get_node: Callable[[int, str, str], dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        k8s_event_table: str = EventCategory.K8S_EVENT.value
        service_relations: dict[str, list[dict[str, Any]]] = EventServiceRelation.fetch_relations(
            bk_biz_id, app_name, service_names
        )
        processed_service_relations: dict[str, list[dict[str, Any]]] = {}
        for service_name in service_names:
            relations: list[dict[str, Any]] = service_relations[service_name]
            table_relation_map: dict[str, dict[str, Any]] = {relation["table"]: relation for relation in relations}
            k8s_event_relation: dict[str, Any] | None = table_relation_map.get(k8s_event_table)

            try:
                auto_workloads: list[dict[str, Any]] = get_node(bk_biz_id, app_name, service_name)["platform"][
                    "workloads"
                ]
            except Exception:  # pylint: disable=broad-except
                # 拓扑节点不可用时，仅保留已手动关联的 k8s 负载
                if k8s_event_relation:
                    target_k8s_event_relation: dict[str, Any] = k8s_event_relation
                    workload_groups: list[list[dict[str, Any]]] = [k8s_event_relation["relations"]]
                else:
                    processed_service_relations[service_name] = list(table_relation_map.values())
                    continue
            else:
                # 手动关联了具体的 workload 时，按“手动关联负载 -> 拓扑自动发现负载”的顺序做只读并集
                if k8s_event_relation and not k8s_event_relation["options"].get("is_auto"):
                    target_k8s_event_relation = k8s_event_relation
                    workload_groups = [k8s_event_relation["relations"], auto_workloads]
                # 未手动关联时，保持原自动关联语义
                else:
                    target_k8s_event_relation = {
                        "table": k8s_event_table,
                        "options": {"is_auto": True},
                        "relations": [],
                    }
                    workload_groups = [auto_workloads]

            # Workload 去重和 ReplicaSet 对象去除
            workloads: list[dict[str, Any]] = []
            seen_workload_keys: set[tuple[Any, ...]] = set()
            for workload_group in workload_groups:
                for workload in workload_group:
                    if workload.get("kind") == "ReplicaSet":
                        continue

                    workload_key: tuple[Any, ...] = (
                        workload.get("bcs_cluster_id"),
                        workload.get("namespace"),
                        workload.get("kind"),
                        workload.get("name"),
                    )
                    if workload_key in seen_workload_keys:
                        continue

                    # 拓扑返回的 updated_at 不是事件关联维度，需去除，否则会在事件查询时被当成过滤条件
                    workload.pop("updated_at", None)
                    seen_workload_keys.add(workload_key)
                    workloads.append(workload)

            table_relation_map[k8s_event_table] = {
                **target_k8s_event_relation,
                "relations": workloads,
            }
            processed_service_relations[service_name] = list(table_relation_map.values())

        return processed_service_relations
