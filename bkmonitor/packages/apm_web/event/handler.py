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

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import EventServiceRelation
from bkmonitor.utils.cache import lru_cache_with_ttl
from monitor_web.data_explorer.event.constants import EventCategory

logger = logging.getLogger(__name__)


class EventHandler:
    @classmethod
    @lru_cache_with_ttl(maxsize=1024, ttl=60)
    def fetch_relations(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        table_relation_map: dict[str, dict[str, Any]] = {
            relation["table"]: relation
            for relation in EventServiceRelation.fetch_relations(bk_biz_id, app_name, service_name)
        }
        k8s_event_relation: dict[str, Any] | None = table_relation_map.get(EventCategory.K8S_EVENT.value)
        if k8s_event_relation and not k8s_event_relation["options"].get("is_auto"):
            return list(table_relation_map.values())

        try:
            # 通过自动发现获取关联 Workload
            workloads: list[dict[str, Any]] = ServiceHandler.list_nodes(bk_biz_id, app_name, service_name)[0][
                "platform"
            ]["workloads"]
        except Exception as e:  # pylint: disable=broad-except
            # 打印异常代替页面报错。
            logger.warning("[fetch_relations] get workloads failed: %s", e)
            return list(table_relation_map.values())

        table_relation_map[EventCategory.K8S_EVENT.value] = {
            "table": EventCategory.K8S_EVENT.value,
            "options": {"is_auto": True},
            "relations": [],
        }
        for workload in workloads:
            workload.pop("update_time", None)
            table_relation_map[EventCategory.K8S_EVENT.value]["relations"].append(workload)
        return list(table_relation_map.values())
