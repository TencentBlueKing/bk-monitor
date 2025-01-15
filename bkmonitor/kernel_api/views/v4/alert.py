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

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from fta_web.alert.views import AlertViewSet as FTAAlertViewSet
from kernel_api.resource.qos import FailurePublishResource, FailureRecoveryResource


class AlertInfoViewSet(ResourceViewSet):
    """
    根据事件ID获取告警的相关信息
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert_by_event, endpoint="search_alert_by_event"),
    ]


class SearchAlertViewSet(ResourceViewSet):
    """
    查询告警列表
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert, endpoint="search_alert"),
    ]


class AlertViewSet(FTAAlertViewSet):
    """
    兼容全量事件中心告警接口
    """


class QosViewSet(ResourceViewSet):
    """
    流控管理模块
    """

    resource_routes = [
        ResourceRoute("POST", FailurePublishResource(), endpoint="failure/publish"),
        ResourceRoute("POST", FailureRecoveryResource(), endpoint="failure/recovery"),
    ]
