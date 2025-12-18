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
from core.drf_resource.viewsets import ResourceRoute

# 复用原有alert模块的ViewSet实现
from fta_web.alert.views import (
    AlertViewSet as _BaseAlertViewSet,
    QuickAlertHandleViewSet as _BaseQuickAlertHandleViewSet,
    SearchFavoriteViewSet as _BaseSearchFavoriteViewSet,
)


class AlertV2ViewSet(_BaseAlertViewSet):
    """
    告警模块V2版本 - 复用原有实现
    新版本可以在这里添加特定的业务逻辑或覆盖原有方法
    """

    resource_routes = [
        ResourceRoute("GET", resource.alert_v2.alert_detail, endpoint="alert/detail"),
        ResourceRoute("GET", resource.alert_v2.alert_events, endpoint="alert/events"),
        ResourceRoute("GET", resource.alert_v2.alert_k8s_scenario_list, endpoint="alert/k8s_scenario_list"),
        ResourceRoute("GET", resource.alert_v2.alert_k8s_metric_list, endpoint="alert/k8s_metric_list"),
        ResourceRoute("GET", resource.alert_v2.alert_k8s_target, endpoint="alert/k8s_target"),
        ResourceRoute("GET", resource.alert_v2.alert_host_target, endpoint="alert/host_target"),
    ]


class QuickAlertHandleV2ViewSet(_BaseQuickAlertHandleViewSet):
    """
    快捷告警处理V2版本 - 复用原有实现
    """

    pass


class SearchFavoriteV2ViewSet(_BaseSearchFavoriteViewSet):
    """
    搜索收藏V2版本 - 复用原有实现
    """

    pass
