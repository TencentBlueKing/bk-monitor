"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class SubscribeViewSet(ResourceViewSet):
    """
    策略订阅API
    """

    resource_routes = [
        ResourceRoute("GET", resource.strategies.list_strategy_subscribe, endpoint="search"),
        ResourceRoute("GET", resource.strategies.detail_strategy_subscribe, endpoint="detail"),
        ResourceRoute("POST", resource.strategies.save_strategy_subscribe, endpoint="save"),
        ResourceRoute("POST", resource.strategies.delete_strategy_subscribe, endpoint="delete"),
        ResourceRoute("POST", resource.strategies.bulk_save_strategy_subscribe, endpoint="bulk_save"),
        ResourceRoute("POST", resource.strategies.bulk_delete_strategy_subscribe, endpoint="bulk_delete"),
    ]
