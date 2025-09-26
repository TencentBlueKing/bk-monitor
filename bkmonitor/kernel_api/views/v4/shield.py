# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.drf_resource import resource


class ShieldViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.shield.add_shield, endpoint="add"),
        ResourceRoute("POST", resource.shield.disable_shield, endpoint="disable"),
        ResourceRoute("POST", resource.shield.edit_shield, endpoint="edit"),
        ResourceRoute("GET", resource.shield.shield_detail, endpoint="detail"),
        ResourceRoute("POST", resource.shield.shield_list, endpoint="search"),
    ]
