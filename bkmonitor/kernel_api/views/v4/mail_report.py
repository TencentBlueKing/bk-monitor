"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from alarm_backends.core.cache.mail_report import MailReportCacheManager
from alarm_backends.service.report.handler import ReportHandler
from alarm_backends.service.report.tasks import render_image_task, render_mails
from bkmonitor.action.serializers.report import (
    FrequencySerializer,
    ReceiverSerializer,
    ReportChannelSerializer,
    ReportContentSerializer,
)
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.permission import Permission
from bkmonitor.iam.resource import ResourceEnum
from bkmonitor.models import RenderImageTask, ReportItems
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.utils.request import get_request, get_request_tenant_id
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
        bk_tenant_id = get_request_tenant_id()

        # 测试邮件只发送给当前用户
        report_handler = ReportHandler(bk_tenant_id=bk_tenant_id)

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
            bk_tenant_id=bk_tenant_id,
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
        bk_tenant_id = get_request_tenant_id()
        try:
            report_item = ReportItems.objects.get(id=params["id"], bk_tenant_id=bk_tenant_id)
        except ReportItems.DoesNotExist:
            raise ValidationError(f"ReportItems id({params['id']}) does not exist")

        # 获取当前用户
        request = get_request(peaceful=True)
        if not request:
            raise ValidationError("request does not exist")
        username = request.user.username
        if not username:
            raise ValidationError("username does not exist")

        # 判断当前用户是否有权限
        manager_users = [manager["id"] for manager in report_item.managers if manager["type"] == "user"]
        if username not in manager_users:
            raise ValidationError("You have no permission to send this report")

        ReportHandler(bk_tenant_id=bk_tenant_id, item_id=report_item.id).process_and_render_mails()


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
        ResourceRoute("GET", resource.report.report_list, endpoint="report_mail_list"),
        ResourceRoute("POST", IsSuperuser, endpoint="is_superuser"),
    ]


class RenderImageResource(Resource):
    """
    渲染图片
    """

    class RequestSerializer(serializers.Serializer):
        type = serializers.ChoiceField(choices=RenderImageTask.TYPE)
        options = serializers.DictField()

        class DashboardOptionsSerializer(serializers.Serializer):
            bk_biz_id = serializers.IntegerField()
            dashboard_uid = serializers.CharField()
            panel_id = serializers.CharField(allow_null=True, allow_blank=True, default=None)
            height = serializers.IntegerField(default=300)
            width = serializers.IntegerField()
            variables = serializers.DictField(default=dict)
            start_time = serializers.IntegerField()
            end_time = serializers.IntegerField()
            scale = serializers.IntegerField(default=2)
            with_panel_title = serializers.BooleanField(default=True)
            image_format = serializers.ChoiceField(choices=["jpeg", "png"], default="jpeg")
            image_quality = serializers.IntegerField(default=85, min_value=0, max_value=100)
            transparent = serializers.BooleanField(default=False)

            def validate(self, attrs):
                # 检查用户是否有权限访问该仪表盘
                p = Permission()
                p.skip_check = False
                result = p.batch_is_allowed(
                    [ActionEnum.VIEW_SINGLE_DASHBOARD],
                    [[ResourceEnum.GRAFANA_DASHBOARD.create_instance(attrs["dashboard_uid"])]],
                )
                if not result.get(attrs["dashboard_uid"], {}).get(ActionEnum.VIEW_SINGLE_DASHBOARD.id):
                    raise PermissionDenied("You have no permission to view this dashboard")

                return attrs

        def validate(self, attrs):
            options = attrs.pop("options")
            if attrs["type"] == RenderImageTask.Type.DASHBOARD:
                serializer = self.DashboardOptionsSerializer(data=options)
            else:
                raise ValidationError(f"Invalid type: {attrs['type']}")
            serializer.is_valid(raise_exception=True)
            attrs["options"] = serializer.validated_data
            return attrs

    def perform_request(self, params):
        # 尝试获取当前用户
        request = get_request(peaceful=True)
        if request:
            username = request.user.username
        else:
            username = "admin"

        task = RenderImageTask.objects.create(
            bk_tenant_id=get_request_tenant_id(),
            type=params["type"],
            options=params["options"],
            status=RenderImageTask.Status.PENDING,
            username=username,
        )
        render_image_task.delay(task)
        return {"task_id": str(task.task_id)}


class GetRenderImageResource(Resource):
    """
    获取渲染图片
    """

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.UUIDField()

    def perform_request(self, params):
        # 尝试获取当前用户
        request = get_request(peaceful=True)
        if request:
            username = request.user.username
        else:
            username = "admin"

        task = RenderImageTask.objects.get(bk_tenant_id=get_request_tenant_id(), task_id=params["task_id"])

        if task.username != username:
            raise ValidationError("You have no permission to visit this task")

        return {
            "status": task.status,
            "image_url": task.image.url if task.image else None,
            "error": task.error,
        }


class RenderImageViewSet(ResourceViewSet):
    """
    渲染图片
    """

    resource_routes = [
        ResourceRoute("POST", RenderImageResource, endpoint="render"),
        ResourceRoute("GET", GetRenderImageResource, endpoint="result"),
    ]
