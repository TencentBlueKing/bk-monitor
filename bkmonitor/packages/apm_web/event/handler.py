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
import logging
from typing import Any, Dict, List, Optional

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import EventServiceRelation
from bkmonitor.utils.cache import lru_cache_with_ttl
from monitor_web.data_explorer.event.constants import EventCategory

logger = logging.getLogger(__name__)


class EventHandler:
    @classmethod
    @lru_cache_with_ttl(maxsize=1024, ttl=60)
    def fetch_relations(cls, bk_biz_id: int, app_name: str, service_name: str) -> List[Dict[str, Any]]:
        table_relation_map: Dict[str, Dict[str, Any]] = {
            relation["table"]: relation
            for relation in EventServiceRelation.fetch_relations(bk_biz_id, app_name, service_name)
        }
        k8s_event_relation: Optional[Dict[str, Any]] = table_relation_map.get(EventCategory.K8S_EVENT.value)
        if k8s_event_relation and not k8s_event_relation["options"].get("is_auto"):
            return list(table_relation_map.values())

        try:
            # 通过自动发现获取关联 Workload
            workloads: List[Dict[str, Any]] = ServiceHandler.list_nodes(bk_biz_id, app_name)[0]["platform"]["workloads"]
            assert workloads
        except (ValueError, IndexError, KeyError, AssertionError):
            return list(table_relation_map.values())

        table_relation_map[EventCategory.K8S_EVENT.value] = {
            "table": EventCategory.K8S_EVENT.value,
            "options": {"is_auto": True},
            "relations": [],
        }
        for workload in workloads:
            workload.pop("update_time", None)
            k8s_event_relation["relations"].append(workload)
        return list(table_relation_map.values())
