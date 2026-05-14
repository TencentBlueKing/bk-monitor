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

from django.conf import settings
from rest_framework import serializers

from apm.resources import ListApplicationResources, QueryTraceDetailResource, QuerySpanDetailResource
from apm_web.profile.resources import (
    GrafanaQueryProfileLabelResource,
    GrafanaQueryProfileResource,
    ListApplicationServicesResource,
    QueryServicesDetailResource,
)
from apm_web.trace.resources import ListTraceViewConfigResource, ListFlattenSpanResource
from core.drf_resource import Resource
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer

logger = logging.getLogger(__name__)

# -------------------- APM MCP 相关服务接口 -------------------- #

"""
Tracing 工作流:
1. 获取业务下的APM应用列表  - ListApmApplicationResource
2. 获取某个APM应用的搜索过滤条件 - GetApmSearchFiltersResource
3. 组装过滤条件,查询Trace / Span 列表 - ListApmSpanResource
4. 查询单个的Trace / Span 详情 - QueryApmTraceDetailResource / QueryApmSpanDetailResource

Profiling 工作流 (与前端 grafana 插件链路一致, 比 samples() 更轻量):
1. 获取业务下已有 profile 数据的应用/服务列表 - GetProfileApplicationServiceResource
2. 获取指定服务可用的 profile 数据类型 (data_type) - GetProfileTypeResource
3. 获取指定服务的 profile label keys (用于 filter_labels 过滤) - GetProfileLabelResource
4. 查询 profile 火焰图数据 (返回 grafana flame graph 格式) - QueryGraphProfileResource
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


# -------------------- APM Profiling MCP 子工作流 -------------------- #


class _ProfileQueryGraphSerializer(TimeSpanValidationPassThroughSerializer):
    """
    用于 query_graph_profile 的 MCP 透传序列化器:
        - 在通用 MCP 时间跨度校验 (MCP_MAX_TIME_SPAN_SECONDS) 之上,
          再叠加一层 Profile 专属的更严限制 (APM_PROFILING_MCP_MAX_TIME_SPAN_SECONDS)
        - 兼容微秒 (start/end) 与秒级 (start_time/end_time) 两种时间字段
        - 业务字段不做严格校验, 全部透传给下游 GrafanaQueryProfileResource
          (其内部使用 ProfileQuerySerializer 做完整校验)
    """

    DEFAULT_MAX_TIME_SPAN_SECONDS = 30 * 60

    @classmethod
    def _get_max_time_span_seconds(cls) -> int:
        return getattr(
            settings,
            "APM_PROFILING_MCP_MAX_TIME_SPAN_SECONDS",
            cls.DEFAULT_MAX_TIME_SPAN_SECONDS,
        )

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)

        start = validated.get("start")
        end = validated.get("end")
        if start is not None and end is not None:
            actual_seconds = (int(end) - int(start)) / 1_000_000
        else:
            start_time = validated.get("start_time")
            end_time = validated.get("end_time")
            if start_time is None or end_time is None:
                # 让下游 ProfileQuerySerializer 报缺失时间字段的错误
                return validated
            actual_seconds = int(end_time) - int(start_time)

        max_span_seconds = self._get_max_time_span_seconds()
        if actual_seconds > max_span_seconds:
            raise serializers.ValidationError(
                {
                    "time_span": (
                        f"Profiling 查询时间跨度过大 ({actual_seconds / 60:.1f} 分钟), "
                        f"为避免数据量爆炸/LLM 上下文超限/下游查询超时, "
                        f"请控制在 {max_span_seconds // 60} 分钟内"
                    )
                }
            )
        if actual_seconds <= 0:
            raise serializers.ValidationError({"time_span": "end 必须大于 start"})
        return validated


class GetProfileApplicationServiceResource(Resource):
    """
    Profiling 工作流-1: 获取业务下已有 profile 数据的 应用 + 服务 列表
    返回 {normal: [{app_name, services: [...]}], no_data: [...]}
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return ListApplicationServicesResource().request(**validated_request_data)


class GetProfileTypeResource(Resource):
    """
    Profiling 工作流-2: 获取指定 app+service 的可用 profile data_type
    返回 {data_types: [{key, name, default_agg_method}], last_check_time, last_report_time, ...}
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return QueryServicesDetailResource().request(**validated_request_data)


class GetProfileLabelResource(Resource):
    """
    Profiling 工作流-3: 获取指定 app+service 的 profile label keys (用于 filter_labels 过滤)
    返回 {label_keys: [...]}
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return GrafanaQueryProfileLabelResource().request(**validated_request_data)


class QueryGraphProfileResource(Resource):
    """
    Profiling 工作流-4: 查询 profile 火焰图数据 (返回 grafana flame graph 格式 frame_data)
    时间跨度受 settings.APM_PROFILING_MCP_MAX_TIME_SPAN_SECONDS 限制(默认 30 分钟)
    """

    RequestSerializer = _ProfileQueryGraphSerializer

    def perform_request(self, validated_request_data):
        return GrafanaQueryProfileResource().request(**validated_request_data)
