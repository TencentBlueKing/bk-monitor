"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from ... import catalog
from ..codec import MonitorV4Codec
from .registry import V4CallbackRegistry
from .service import V4CallbackService

# callback 项目显式持有 registry 和 service；Provider 不导入、创建或调用它们。
_registry = V4CallbackRegistry()
_callback_service = V4CallbackService(codec=MonitorV4Codec(), registry=_registry)


def get_callback_service() -> V4CallbackService:
    """返回监控项目独立组装的 V4 callback service。"""
    return _callback_service


@_registry.register_list_instance("space")
def _list_space(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("space", filter_data, page)


@_registry.register_fetch_instance_info("space")
def _fetch_space(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("space", ids, requires)


@_registry.register_list_instance("apm_application")
def _list_apm(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("apm_application", filter_data, page)


@_registry.register_fetch_instance_info("apm_application")
def _fetch_apm(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("apm_application", ids, requires)


@_registry.register_list_instance("grafana_dashboard")
def _list_grafana(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("grafana_dashboard", filter_data, page)


@_registry.register_fetch_instance_info("grafana_dashboard")
def _fetch_grafana(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("grafana_dashboard", ids, requires)


@_registry.register_list_instance("rum_application")
def _list_rum(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("rum_application", filter_data, page)


@_registry.register_fetch_instance_info("rum_application")
def _fetch_rum(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("rum_application", ids, requires)
