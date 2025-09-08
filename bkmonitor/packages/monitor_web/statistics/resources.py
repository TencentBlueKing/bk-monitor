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

import logging

from monitor_web.statistics.v2.factory import CollectorFactory
from rest_framework import serializers

from core.drf_resource import Resource

logger = logging.getLogger(__name__)


class ResponseFormat(object):
    JSON = "json"
    PROMETHEUS = "prometheus"


class GetStatisticsDataResource(Resource):
    """
    获取统计数据
    """

    class RequestSerializer(serializers.Serializer):
        response_format = serializers.ChoiceField(
            required=False,
            default=ResponseFormat.PROMETHEUS,
            label="返回格式",
            choices=[ResponseFormat.PROMETHEUS, ResponseFormat.JSON],
        )

    def perform_request(self, validated_request_data):
        response_format = validated_request_data["response_format"]
        if response_format == ResponseFormat.JSON:
            return CollectorFactory.export_json()
        return CollectorFactory.export_text()
