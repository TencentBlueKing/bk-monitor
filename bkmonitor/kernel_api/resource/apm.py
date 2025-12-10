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
from core.drf_resource import Resource
from rest_framework import serializers
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer
from apm.resources import ListApplicationResources, QueryTraceDetailResource, QuerySpanDetailResource
from apm_web.trace.resources import ListTraceViewConfigResource, ListFlattenSpanResource

logger = logging.getLogger(__name__)

# -------------------- APM MCP 相关服务接口 -------------------- #

"""
工作流:
1. 获取业务下的APM应用列表  - ListApmApplicationResource
2. 获取某个APM应用的搜索过滤条件 - GetApmSearchFiltersResource
3. 组装过滤条件,查询Trace / Span 列表 - ListApmSpanResource
4. 查询单个的Trace / Span 详情 - QueryApmTraceDetailResource / QueryApmSpanDetailResource
"""


class ListApmApplicationResource(Resource):
    """
    获取 APM 应用列表,类似 list_services
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_request_data):
        """
        获取 APM 应用列表
        """
        return ListApplicationResources().request(**validated_request_data)


class GetApmSearchFiltersResource(Resource):
    """
    获取某个APM应用的搜索过滤条件
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        """
        获取某个APM应用的搜索过滤条件
        """
        return ListTraceViewConfigResource().request(**validated_request_data)


class ListApmSpanResource(Resource):
    """
    查询APM应用的Span列表
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        """
        查询APM应用的Span列表
        """
        return ListFlattenSpanResource().request(**validated_request_data)


class QueryApmTraceDetailResource(Resource):
    """
    查询APM应用的Trace详情
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return QueryTraceDetailResource().request(**validated_request_data)


class QueryApmSpanDetailResource(Resource):
    """
    查询APM应用的Span详情
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return QuerySpanDetailResource().request(**validated_request_data)
