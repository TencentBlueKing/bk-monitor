"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# -*- coding: utf-8 -*-
from core.drf_resource import Resource
from fta_web.alert.resources import ListAlertTagsResource  # noqa
from fta_web.alert.resources import SearchAlertByEventResource, SearchAlertResource  # noqa
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer


class ListAlertResource(Resource):
    """告警列表查询接口 (用于 AI MCP 请求)"""

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return SearchAlertResource().request(**validated_request_data)
