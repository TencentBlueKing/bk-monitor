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
import datetime
import logging
from typing import Any, Dict, List, Optional

from apm_web.container.helpers import ContainerHelper
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import EventServiceRelation
from apm_web.service.resources import ServiceConfigResource
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from monitor_web.data_explorer.event.constants import EventCategory

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, bk_biz_id: int, app_name: str):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name

    def _discover_service_k8s_event_relations(self, service_name: str):
        """自动发现服务 k8s 事件关联关系"""
        table_relation_map: Dict[str, Dict[str, Any]] = {
            relation["table"]: relation
            for relation in EventServiceRelation.fetch_relations(self.bk_biz_id, self.app_name, service_name)
        }
        k8s_event_relation: Optional[Dict[str, Any]] = table_relation_map.get(EventCategory.K8S_EVENT.value)
        if k8s_event_relation and not k8s_event_relation["options"].get("is_auto"):
            # 调用接口相比于查询 DB 是一个更重的操作，这里应该先判断是否开启自动关联，再查询关联关系，减少无效调用。
            logger.info(
                "[_discover_service_k8s_event_relations] auto discover disabled:"
                "bk_biz_id -> %s, app_name -> %s, service_name -> %s",
                self.bk_biz_id,
                self.app_name,
                service_name,
            )
            return

        end_time: int = int(datetime.datetime.now().timestamp())
        start_time: int = end_time - int(datetime.timedelta(hours=1).total_seconds())
        workloads: List[Dict[str, str]] = ContainerHelper.list_apm_service_workloads(
            self.bk_biz_id, self.app_name, service_name, start_time, end_time
        )
        if not workloads:
            logger.info(
                "[_discover_service_k8s_event_relations] no workloads found: "
                "bk_biz_id -> %s, app_name -> %s, service_name -> %s",
                self.bk_biz_id,
                self.app_name,
                service_name,
            )
            return

        ServiceConfigResource.update_event_relations(
            self.bk_biz_id,
            self.app_name,
            service_name,
            [{"table": EventCategory.K8S_EVENT.value, "options": {"is_auto": True}, "relations": workloads}],
        )
        logger.info(
            "[_discover_service_k8s_event_relations] update k8s event relations success:"
            "bk_biz_id -> %s, app_name -> %s, service_name -> %s, workloads -> %s",
            self.bk_biz_id,
            self.app_name,
            service_name,
            workloads,
        )

    def discover_app_k8s_event_relations(self):
        """自动发现应用 k8s 事件关联关系"""
        service_names: List[str] = [
            node["topo_key"] for node in ServiceHandler.list_nodes(self.bk_biz_id, self.app_name)
        ]

        # 分批，避免一次性处理过多服务
        batch: int = 20
        for idx in range(0, len(service_names), batch):
            partial_service_names = service_names[idx : idx + batch]
            logger.info(
                "[discover_app_k8s_event_relations] start to discover service k8s event relations: "
                "bk_biz_id -> %s, app_name -> %s, total -> %s, idx -> %s, service_names -> %s",
                self.bk_biz_id,
                self.app_name,
                len(service_names),
                idx,
                partial_service_names,
            )
            run_threads(
                [
                    InheritParentThread(target=self._discover_service_k8s_event_relations, args=(service_name,))
                    for service_name in partial_service_names
                ]
            )
            logger.info(
                "[discover_app_k8s_event_relations] end to discover service k8s event relations: "
                "bk_biz_id -> %s, app_name -> %s, service_num -> %s, idx -> %s",
                self.bk_biz_id,
                self.app_name,
                len(service_names),
                idx,
            )
