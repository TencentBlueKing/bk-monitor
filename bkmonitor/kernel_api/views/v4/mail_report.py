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
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from alarm_backends.core.cache.mail_report import MailReportCacheManager
from alarm_backends.service.report.handler import ReportHandler
from alarm_backends.service.report.tasks import render_mails
from bkmonitor.action.serializers.report import (
    FrequencySerializer,
    ReceiverSerializer,
    ReportChannelSerializer,
    ReportContentSerializer,
)
from bkmonitor.models import ReportItems
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.views import serializers
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class GetStatisticsByJson(Resource):
    """
    获取json格式的运营数据
    """

    def perform_request(self, params):
        result = resource.statistics.get_statistics_data(response_format="json")

        return to_dict(result)


class GetSettingAndNotifyGroup(Resource):
    """
    获取配置管理员及其业务、告警接收人及其业务
    """

    def perform_request(self, params):
        result = MailReportCacheManager().fetch_groups_and_user_bizs()

        return result


class IsSuperuser(Resource):
    """
    判断用户是否超级管理员
    """

    class RequestSerializer(serializers.Serializer):
        username = serializers.ListField(required=True)

    def perform_request(self, params):
        users_is_superuser = {}
        user_model = get_user_model()
        bkuser = user_model.objects.filter(username__in=params["username"])
        for user in bkuser:
            users_is_superuser[str(user)] = user.is_superuser
        return users_is_superuser


class TestReportMail(Resource):
    """
    发送订阅报表测试
    """

    class RequestSerializer(serializers.Serializer):
        creator = serializers.CharField(required=True, max_length=512)
        mail_title = serializers.CharField(required=True, max_length=512)
        receivers = ReceiverSerializer(many=True)
        channels = ReportChannelSerializer(many=True, required=False)
        is_link_enabled = serializers.BooleanField(required=False, default=True)
        report_contents = ReportContentSerializer(many=True)
        frequency = FrequencySerializer(required=False)

    def perform_request(self, params):
        # 测试邮件只发送给当前用户
        report_handler = ReportHandler()

        # 是否超管
        is_superuser = False
        user_model = get_user_model()
        try:
            bkuser = user_model.objects.get(username=params["creator"])
            if bkuser.is_superuser:
                is_superuser = True
        except user_model.DoesNotExist:
            is_superuser = False

        # 获取当前用户有权限的业务列表
        item = ReportItems(
            mail_title=params["mail_title"],
            receivers=[{"id": params["creator"], "is_enabled": True, type: "user"}],
            channels=params["channels"],
            is_link_enabled=params["is_link_enabled"],
            managers=[params["creator"]],
            frequency=params["frequency"],
        )
        # 赋予一个缺省值
        report_handler.item_id = -1

        render_mails.apply_async(
            args=(report_handler, item, params["report_contents"], [params["creator"]], is_superuser)
        )
        for channel in item.channels:
            if channel.get("is_enabled"):
                # 所有的channel, 无法校验权限，只要满足条件，默认全部接口
                subscribers = [subscriber["username"] for subscriber in channel["subscribers"]]
                render_mails.apply_async(
                    args=(report_handler, item, params["report_contents"], subscribers, True),
                    kwargs={"channel_name": channel["channel_name"]},
                )
        return "success"


class SendReportMail(Resource):
    """
    发送订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)

    def perform_request(self, params):
        try:
            report_item = ReportItems.objects.get(id=params["id"])
        except ReportItems.DoesNotExist:
            raise ValidationError(f"ReportItems id({params['id']}) does not exist")

        ReportHandler(report_item.id).process_and_render_mails()


class MailReportViewSet(ResourceViewSet):
    """
    邮件订阅
    """

    resource_routes = [
        ResourceRoute("GET", GetStatisticsByJson, endpoint="get_statistics_by_json"),
        ResourceRoute("GET", GetSettingAndNotifyGroup, endpoint="get_setting_and_notify_group"),
        ResourceRoute("POST", TestReportMail, endpoint="test_report_mail"),
        ResourceRoute("POST", SendReportMail, endpoint="send_report_mail"),
        ResourceRoute("GET", resource.report.group_list, endpoint="group_list"),
        ResourceRoute("POST", IsSuperuser, endpoint="is_superuser"),
    ]
