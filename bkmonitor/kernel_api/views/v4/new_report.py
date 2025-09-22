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
from alarm_backends.service.new_report.tasks import send_report
from bkmonitor.action.serializers.report import FrequencySerializer
from bkmonitor.models import Report, ReportChannel
from bkmonitor.report.serializers import (
    ChannelSerializer,
    ContentConfigSerializer,
    ScenarioConfigSerializer,
)
from bkmonitor.report.utils import create_send_record
from bkmonitor.views import serializers
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class SendReport(Resource):
    """
    发送订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        scenario = serializers.CharField(label="订阅场景", required=False)
        channels = ChannelSerializer(many=True, required=False)
        frequency = FrequencySerializer(required=False)
        content_config = ContentConfigSerializer(required=False)
        scenario_config = ScenarioConfigSerializer(required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False, default=None, allow_null=True)
        end_time = serializers.IntegerField(label="结束时间", required=False, default=None, allow_null=True)
        is_manager_created = serializers.BooleanField(required=False, default=False)
        is_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        channels = []
        # 若订阅id不存在则为测试发送，使用缺省值绑定测试发送记录
        report_id = validated_request_data.get("report_id", -1)
        channels_params = validated_request_data.pop("channels", [])
        for channel in channels_params:
            channel["report_id"] = report_id
            channels.append(ReportChannel(**channel))
        send_round = 0
        if validated_request_data.get("report_id"):
            try:
                report = Report.objects.get(id=validated_request_data["report_id"])
            except Report.DoesNotExist:
                raise Exception(f'report {validated_request_data["report_id"]} does not exist.')
            send_round = report.send_round + 1 if report.send_round else 1
            report.send_round = send_round
            report.save()
        else:
            report = Report(**validated_request_data)
        create_send_record(channels, send_round)
        send_report.delay(report, channels)
        return "success"


class NewReportViewSet(ResourceViewSet):
    """
    订阅报表
    """

    resource_routes = [
        ResourceRoute("POST", SendReport, endpoint="send_report"),
        ResourceRoute("POST", resource.new_report.create_or_update_report, endpoint="create_or_update_report"),
        ResourceRoute("GET", resource.new_report.get_exist_reports, endpoint="get_exist_reports"),
        ResourceRoute("GET", resource.new_report.get_variables, endpoint="get_report_variables"),
    ]
