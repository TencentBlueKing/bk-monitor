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
from typing import Any
from collections.abc import Callable

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
        service_relations: dict[str, list[dict[str, Any]]] = EventServiceRelation.fetch_relations(
            bk_biz_id, app_name, service_names
        )
        processed_service_relations: dict[str, list[dict[str, Any]]] = {}
        for service_name in service_names:
            relations: list[dict[str, Any]] = service_relations.get(service_name, [])
            table_relation_map: dict[str, dict[str, Any]] = {relation["table"]: relation for relation in relations}
            k8s_event_relation: dict[str, Any] | None = table_relation_map.get(EventCategory.K8S_EVENT.value)
            if (
                k8s_event_relation
                and not k8s_event_relation["options"].get("is_auto")
                and k8s_event_relation.get("relations")
            ):
                # 没有配置自动发现，且手动关联了具体的 workload，直接使用手动配置的关联关系。
                processed_service_relations[service_name] = list(table_relation_map.values())
                continue

            try:
                workloads: list[dict[str, Any]] = get_node(bk_biz_id, app_name, service_name)["platform"]["workloads"]
            except Exception:  # pylint: disable=broad-except
                processed_service_relations[service_name] = list(table_relation_map.values())
                continue

            table_relation_map[EventCategory.K8S_EVENT.value] = {
                "table": EventCategory.K8S_EVENT.value,
                "options": {"is_auto": True},
                "relations": [],
            }
            for workload in workloads:
                workload.pop("update_time", None)
                table_relation_map[EventCategory.K8S_EVENT.value]["relations"].append(workload)

            processed_service_relations[service_name] = list(table_relation_map.values())

        return processed_service_relations
