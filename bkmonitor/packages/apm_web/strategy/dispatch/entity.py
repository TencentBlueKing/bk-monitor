"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import threading
from functools import cached_property
from typing import Any

from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.cache import lru_cache_with_ttl
from core.drf_resource import api
from apm_web.constants import TopoNodeKind
from apm_web.event.handler import EventHandler
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.service_handler import ServiceHandler
from monitor_web.data_explorer.event.constants import EventCategory


class EntitySet:
    def __init__(self, bk_biz_id: int, app_name: str, service_names: list[str] | None = None):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name

        nodes: list[dict[str, Any]] = []
        is_all_scope: bool = not service_names
        service_node_map: dict[str, dict[str, Any]] = {}
        duplicated_service_names: set[str] = set(service_names or [])
        for node in ServiceHandler.list_nodes(self.bk_biz_id, self.app_name):
            # 策略只针对真实服务做下发，忽略虚拟节点。
            kind: str | None = node.get("extra_data", {}).get("kind")
            if kind != TopoNodeKind.SERVICE:
                continue

            service_name: str = node.get("topo_key", "")
            if service_name in duplicated_service_names or is_all_scope:
                service_node_map[service_name] = node
                nodes.append(node)

        miss_service_names: set[str] = duplicated_service_names - {node["topo_key"] for node in nodes}
        if miss_service_names:
            raise ValueError(_("部分服务不存在：{}").format(", ".join(miss_service_names)))

        self.nodes: list[dict[str, Any]] = nodes
        self.service_names: list[str] = list(service_node_map.keys())
        self._service_node_map: dict[str, dict[str, Any]] = service_node_map

        # 缓存关联数据初始化一个锁用于保证懒加载仅执行一次。
        self._lock: threading.Lock = threading.Lock()

    @cached_property
    def _service_log_indexes_map(self) -> dict[str, list[dict[str, Any]]]:
        """
        获取服务关联的日志索引集
        :return: 服务名<>关联的日志索引集列表
        """
        service_indexes: dict[str, list[dict[str, Any]]] = {}
        datasource_index_set_id: int | None = ServiceLogHandler.get_and_check_datasource_index_set_id(
            self.bk_biz_id, self.app_name
        )
        if datasource_index_set_id:
            for service_name in self.service_names:
                service_indexes[service_name] = [{"index_set_id": datasource_index_set_id, "is_app_datasource": True}]

        for relation in ServiceLogHandler.get_log_relations(self.bk_biz_id, self.app_name, self.service_names):
            if relation.related_bk_biz_id != self.bk_biz_id:
                # 跨业务关联意味着告警也要跨业务下发，当前不支持。
                continue

            service_indexes.setdefault(relation.service_name, []).extend(
                [{"index_set_id": index_set_id, "is_app_datasource": False} for index_set_id in relation.value_list]
            )

        return service_indexes

    @cached_property
    def _service_workloads_map(self) -> dict[str, list[dict[str, Any]]]:
        """
        获取服务关联的容器负载
        :return: 服务名<>关联的容器负载列表
        """
        service_relations: dict[str, list[dict[str, Any]]] = EventHandler.fetch_relations_by_nodes(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            service_names=self.service_names,
            get_node=lambda ___, __, _service_name: self._service_node_map[_service_name],
        )
        service_workloads: dict[str, list[dict[str, Any]]] = {}
        for service_name, relations in service_relations.items():
            for relation in relations:
                if relation["table"] == EventCategory.K8S_EVENT.value:
                    service_workloads[service_name] = relation["relations"]
                    break

        return service_workloads

    @cached_property
    def _application_info(self):
        return api.apm_api.detail_application(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

    def get_first_log_index_set_id_or_none(self, service_name: str) -> int | None:
        """
        获取服务关联的第一个日志索引集ID
        :param service_name: 服务名
        :return: 日志索引集 ID 或 None
        """
        try:
            with self._lock:
                return self._service_log_indexes_map[service_name][0]["index_set_id"]
        except (KeyError, IndexError):
            return None

    def get_workloads(self, service_name: str) -> list[dict[str, Any]]:
        """
        获取服务关联的容器负载
        :param service_name: 服务名
        :return: 容器负载列表
        """
        with self._lock:
            return self._service_workloads_map.get(service_name, [])

    def get_datasource_index_set_id_or_none(self, datasource: str) -> int | None:
        """
        获取应用数据源索引集 ID
        :param datasource: 数据源类型，支持 "log" 或 "trace"
        :return: 索引集 ID 或 None
        """
        try:
            with self._lock:
                return self._application_info[f"{datasource}_config"]["index_set_id"]
        except (KeyError, TypeError):
            return None

    def get_log_datasource_index_set_id_or_none(self) -> int | None:
        """
        获取应用日志数据源索引集 ID
        :return: 日志索引集 ID 或 None
        """
        return self.get_datasource_index_set_id_or_none("log")

    def get_trace_datasource_index_set_id_or_none(self) -> int | None:
        """
        获取应用调用链数据源索引集 ID
        :return: 调用链索引集 ID 或 None
        """
        return self.get_datasource_index_set_id_or_none("trace")

    @lru_cache_with_ttl(ttl=60, maxsize=128)
    def get_rpc_service_config_or_none(self, service_name: str) -> dict[str, Any] | None:
        """
        获取服务 RPC 配置
        :param service_name: 服务名
        :return: RPC 配置或 None
        """
        return ServiceHandler.get_rpc_service_config_or_none(self._service_node_map[service_name])
