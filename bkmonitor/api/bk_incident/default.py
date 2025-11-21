"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

from django.conf import settings

from rest_framework import serializers

from core.drf_resource.contrib.api import APIResource


class IncidentBaseResource(APIResource, metaclass=abc.ABCMeta):
    module_name = "bk_incident"

    @property
    def base_url(self):
        if settings.BK_INCIDENT_APIGW_URL:
            return settings.BK_INCIDENT_APIGW_URL
        return f"{settings.BK_COMPONENT_API_URL}/api/incident-manger/prod/"


class GetTemplateListResource(IncidentBaseResource):
    """
    拉取业务下的执行流程列表
    """

    action = "/bkflow/template/list/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=True)


class GetTemplateInfoResource(IncidentBaseResource):
    """
    拉取业务下的执行流程模版信息(参数)
    """

    action = "/bkflow/template/{template_id}/fetch_template/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=True)
        template_id = serializers.CharField(label="模版ID", required=True)


class CreateTaskResource(IncidentBaseResource):
    """
    创建故障分析任务
    """

    action = "/bkflow/task/create/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=True)
        template_id = serializers.IntegerField(label="模版ID", required=True)
        constants = serializers.DictField(label="流程参数", required=False, default=dict)
        name = serializers.CharField(label="任务名称", required=True)


class StartTaskResource(IncidentBaseResource):
    """
    启动故障分析任务
    """

    action = "/bkflow/task/{task_id}/start/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.IntegerField(label="任务ID", required=True)
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=True)


class GetTaskStatusResource(IncidentBaseResource):
    """
    查询故障分析任务状态
    """

    action = "/bkflow/task/{task_id}/status/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.IntegerField(label="任务ID", required=True)
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=True)
