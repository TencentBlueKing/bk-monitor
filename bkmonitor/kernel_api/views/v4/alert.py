"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rest_framework import serializers
from rest_framework.decorators import action

from alarm_backends.core.alert.alert import Alert
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from bkmonitor.documents.alert import AlertDocument
from constants.alert import EventStatus
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from fta_web.alert.serializers import AlertIDField
from fta_web.alert.views import AlertViewSet as FTAAlertViewSet
from kernel_api.resource.qos import FailurePublishResource, FailureRecoveryResource


class AlertInfoViewSet(ResourceViewSet):
    """
    根据事件ID获取告警的相关信息
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert_by_event, endpoint="search_alert_by_event"),
        ResourceRoute("POST", resource.alert.list_alert_tags, endpoint="list_alert_tags"),
    ]


class SearchAlertViewSet(ResourceViewSet):
    """
    查询告警列表
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert, endpoint="search_alert"),
    ]


class CloseAlertSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    ids = serializers.ListField(label="告警ID列表", child=AlertIDField())
    message = serializers.CharField(allow_blank=True, label="确认信息", default="")


class AlertViewSet(FTAAlertViewSet):
    """
    兼容全量事件中心告警接口
    """

    @action(detail=False, methods=["POST"], url_path="alert/close")
    def close_alert(self, request, *args, **kwargs):
        serializer = CloseAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_request_data: dict[str, Any] = dict(serializer.validated_data)

        alert_ids = validated_request_data["ids"]

        # 需要关闭的告警
        alerts_should_close = set()
        # 已经结束的告警
        alerts_already_end = set()

        alerts = AlertDocument.mget(alert_ids)

        for alert in alerts:
            # 告警状态为异常且未确认，则需要关闭
            if alert.status == EventStatus.ABNORMAL and not alert.is_ack:
                alerts_should_close.add(alert.id)
                CloseStatusChecker.close(Alert(alert.to_dict()), validated_request_data["message"])
            else:
                alerts_already_end.add(alert.id)

        # 不存在的告警
        alerts_not_exist = set(alert_ids) - alerts_should_close - alerts_already_end

        return {
            "alerts_close_success": list(alerts_should_close),
            "alerts_not_exist": list(alerts_not_exist),
            "alerts_already_end": list(alerts_already_end),
        }


class QosViewSet(ResourceViewSet):
    """
    流控管理模块
    """

    resource_routes = [
        ResourceRoute("POST", FailurePublishResource(), endpoint="failure/publish"),
        ResourceRoute("POST", FailureRecoveryResource(), endpoint="failure/recovery"),
    ]
