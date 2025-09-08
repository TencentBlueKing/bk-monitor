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
import logging

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

logger = logging.getLogger(__name__)


class HomeViewSet(ResourceViewSet):
    def get_permissions(self):
        # 走接口内权限校验
        return []

    resource_routes = [
        ResourceRoute("GET", resource.home.statistics, endpoint="statistics"),
        ResourceRoute("POST", resource.home.favorite, endpoint="favorite"),
        ResourceRoute("POST", resource.home.sticky, endpoint="sticky"),
        ResourceRoute("GET", resource.home.biz_with_alert_statistics, endpoint="biz_with_alert_statistics"),
    ]
