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

from django.conf import settings
from rest_framework import serializers

from core.drf_resource.contrib.nested_api import KernelAPIResource


class MonitorAPIGWResource(KernelAPIResource):
    TIMEOUT = 300
    base_url_statement = None
    base_url = settings.MONITOR_API_BASE_URL or "%s/api/c/compapi/v2/monitor_v3/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "mointor_v3"

    @property
    def label(self):
        return self.__doc__


class CollectConfigListResource(MonitorAPIGWResource):
    """
    获取采集配置
    """

    action = "/get_collect_config_list/"
    method = "GET"


class UptimeCheckTaskListResource(MonitorAPIGWResource):
    """
    获取拨测任务
    """

    action = "/get_uptime_check_task_list/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        plain = serializers.BooleanField(label="是否返回简单数据", default=True)


class UptimeCheckNodeListResource(MonitorAPIGWResource):
    """
    获取拨测节点
    """

    action = "/get_uptime_check_node_list/"
    method = "GET"


class GetStatisticsByJsonResource(MonitorAPIGWResource):
    """
    查询运营数据
    """

    action = "/get_statistics_by_json/"
    method = "GET"


class GetSettingAndNotifyGroupResource(MonitorAPIGWResource):
    """
    获取配置管理员及其业务、告警接收人及其业务
    """

    action = "/get_setting_and_notify_group/"
    method = "GET"


class TestReportMailResource(MonitorAPIGWResource):
    """
    订阅报表测试
    """

    action = "/test_report_mail/"
    method = "POST"


class SendReportResource(MonitorAPIGWResource):
    """
    发送订阅报表
    """

    action = "/send_report/"
    method = "POST"


class GroupListResource(MonitorAPIGWResource):
    """
    获取组内人员信息
    """

    action = "/group_list/"
    method = "GET"


class CreateCustomTimeSeriesResource(MonitorAPIGWResource):
    """
    创建自定义上报
    """

    action = "/create_custom_time_series/"
    method = "POST"


class IsSuperuser(MonitorAPIGWResource):
    """
    判断用户是否超级管理员
    """

    action = "/is_superuser/"
    method = "POST"


class BatchCreateActionBackendResource(MonitorAPIGWResource):
    """
    批量创建处理任务
    """

    action = "/batch_create_action/"
    method = "POST"


class GetActionParamsBackendResource(MonitorAPIGWResource):
    """
    批量获取处理任务参数
    """

    action = "/get_action_params_by_config/"
    method = "POST"
