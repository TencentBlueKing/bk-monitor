"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource.contrib.nested_api import KernelAPIResource


class MonitorAPIGWResource(KernelAPIResource):
    TIMEOUT = 300
    base_url_statement = None
    base_url = (
        settings.NEW_MONITOR_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-monitor/{settings.APIGW_STAGE}/"
    )
    # 模块名
    module_name = "mointor_v3"

    @property
    def label(self):
        return self.__doc__


class CollectConfigListResource(MonitorAPIGWResource):
    """
    获取采集配置
    """

    action = "/app/collect_config/list/"
    method = "GET"


class UptimeCheckTaskListResource(MonitorAPIGWResource):
    """
    获取拨测任务
    """

    action = "/app/uptime_check/task/list/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        plain = serializers.BooleanField(label="是否返回简单数据", default=True)
        id = serializers.CharField(label="任务ID", required=False)


class UptimeCheckNodeListResource(MonitorAPIGWResource):
    """
    获取拨测节点
    """

    action = "/app/uptime_check/node/list/"
    method = "GET"


class GetStatisticsByJsonResource(MonitorAPIGWResource):
    """
    查询运营数据
    """

    action = "/app/mail_report/get_statistics_by_json/"
    method = "GET"


class GetSettingAndNotifyGroupResource(MonitorAPIGWResource):
    """
    获取配置管理员及其业务、告警接收人及其业务
    """

    action = "/app/mail_report/get_setting_and_notify_group/"
    method = "GET"


class TestReportMailResource(MonitorAPIGWResource):
    """
    订阅报表测试
    """

    action = "/app/mail_report/test/"
    method = "POST"


class SendReportResource(MonitorAPIGWResource):
    """
    发送订阅报表
    """

    action = "/app/new_report/send_report/"
    method = "POST"


class GroupListResource(MonitorAPIGWResource):
    """
    获取组内人员信息
    """

    action = "/app/mail_report/group_list/"
    method = "GET"


class CreateCustomTimeSeriesResource(MonitorAPIGWResource):
    """
    创建自定义上报
    """

    action = "/app/custom_metric/create/"
    method = "POST"


class CustomTimeSeriesDetailResource(MonitorAPIGWResource):
    """
    获取自定义指标上报详情
    """

    action = "/app/custom_metric/detail/"
    method = "GET"


class BatchCreateActionBackendResource(MonitorAPIGWResource):
    """
    批量创建处理任务
    """

    action = "/app/action/batch_create_action/"
    method = "POST"


class GetActionParamsBackendResource(MonitorAPIGWResource):
    """
    批量获取处理任务参数
    """

    action = "/app/action/get_action_params_by_config/"
    method = "POST"


class GetExperienceResource(MonitorAPIGWResource):
    """
    获取告警处理经验
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        alert_id = serializers.CharField(required=False, label="告警ID")
        metric_id = serializers.CharField(label="指标", required=False)

        def validate(self, attrs):
            if "alert_id" not in attrs and "metric_id" not in attrs:
                raise ValidationError("alert_id and metric_id cannot be empty at the same time")
            return attrs

    action = "/app/alert/get_experience/"
    method = "GET"
