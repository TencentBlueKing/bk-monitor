"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from abc import ABC
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BaseInstanceData(ABC):
    id: int | None = None
    updated_at: datetime | None = None


@dataclass
class EndpointInstanceData(BaseInstanceData):
    service_name: str | None = None
    endpoint_name: str | None = None
    category_id: str | None = None
    category_kind_key: str | None = None
    category_kind_value: str | None = None
    span_kind: int | None = None


@dataclass
class TopoInstanceData(BaseInstanceData):
    topo_node_key: str | None = None
    instance_id: str | None = None
    instance_topo_kind: str | None = None
    component_instance_category: str | None = None
    component_instance_predicate_value: str | None = None
    sdk_name: str | None = None
    sdk_version: str | None = None
    sdk_language: str | None = None


@dataclass
class HostInstanceData(BaseInstanceData):
    bk_cloud_id: int | None = None
    bk_host_id: int | None = None
    ip: str | None = None
    topo_node_key: str | None = None
