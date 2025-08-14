"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

from django.conf import settings
from rest_framework import serializers

from core.drf_resource import APIResource


class QcloudMonitorAPIResource(APIResource, metaclass=abc.ABCMeta):
    # 设置超时时间为 30s
    TIMEOUT = 30

    base_url_statement = None
    base_url = getattr(settings, "QCLOUD_MONITOR_API_BASE_URL", "http://qcloudmonitor")

    # 模块名
    module_name = "qcloud_monitor"

    @property
    def label(self):
        return self.__doc__

    def get_request_url(self, validated_request_data):
        return super().get_request_url(validated_request_data).format(**validated_request_data)

    def validate_response_data(self, response_data):
        return response_data


class QueryInstancesResource(QcloudMonitorAPIResource):
    """
    查询腾讯云产品实例接口
    """

    action = "/instances"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        secretId = serializers.CharField(required=True, label="腾讯云SecretId", help_text="腾讯云账号的SecretId")
        secretKey = serializers.CharField(required=True, label="腾讯云SecretKey", help_text="腾讯云账号的SecretKey")
        namespace = serializers.CharField(required=True, label="产品命名空间", help_text="产品名称，如 QCE/LB_PRIVATE")
        region = serializers.CharField(required=True, label="地域代码", help_text="地域代码，如: ap-beijing")

        # 标签过滤条件
        tags = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            default=list,
            label="标签选择器",
            help_text="标签过滤条件，支持fuzzy匹配",
        )

        # 字段过滤器
        filters = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            default=list,
            label="字段过滤器",
            help_text="每种产品支持的字段会有差异",
        )

    class ResponseSerializer(serializers.Serializer):
        total = serializers.IntegerField(label="实例总数", help_text="查询到的实例总数")
        data = serializers.ListField(
            child=serializers.DictField(),
            label="实例列表",
            help_text="实例数据，每个实例的信息都不一样，不做过滤全部返回",
        )
