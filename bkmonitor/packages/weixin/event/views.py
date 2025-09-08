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
from rest_framework.authentication import SessionAuthentication

from bkmonitor.middlewares.authentication import NoCsrfSessionAuthentication
from bkmonitor.views.renderers import PlainTextRenderer
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class EventViewSet(ResourceViewSet):
    """
    获取全部通知对象
    """

    def get_authenticators(self):
        authenticators = super(EventViewSet, self).get_authenticators()
        authenticators = [
            authenticator for authenticator in authenticators if not isinstance(authenticator, SessionAuthentication)
        ]
        authenticators.append(NoCsrfSessionAuthentication())
        return authenticators

    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("GET", resource.weixin.event.get_alarm_detail, endpoint="get_alarm_detail"),
        ResourceRoute("GET", resource.weixin.event.get_event_detail, endpoint="get_event_detail"),
        ResourceRoute("GET", resource.weixin.event.get_event_graph_view, endpoint="get_event_graph_view"),
        ResourceRoute("POST", resource.weixin.event.quick_shield, endpoint="quick_shield"),
        ResourceRoute("GET", resource.weixin.event.get_event_list, endpoint="get_event_list"),
        ResourceRoute("POST", resource.weixin.event.ack_event, endpoint="ack_event"),
    ]


class QuickAlertHandleViewSet(ResourceViewSet):
    renderer_classes = [PlainTextRenderer]
    # 快捷操作
    resource_routes = [
        ResourceRoute("GET", resource.alert.quick_alert_shield, endpoint="alert/quick_shield"),
        ResourceRoute("GET", resource.alert.quick_alert_ack, endpoint="alert/quick_ack"),
    ]
