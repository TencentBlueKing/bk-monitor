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
from apm_web.profile.constants import DEFAULT_PROFILE_DATA_TYPE
from apm_web.profile.views import ProfileQueryViewSet
from apm_web.trace.resources import ListTraceViewConfigResource, ListFlattenSpanResource
from core.drf_resource import Resource
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer

logger = logging.getLogger(__name__)

# -------------------- APM MCP 相关服务接口 -------------------- #

"""
工作流:
1. 获取业务下的APM应用列表  - ListApmApplicationResource
2. 获取某个APM应用的搜索过滤条件 - GetApmSearchFiltersResource
3. 组装过滤条件,查询Trace / Span 列表 - ListApmSpanResource
4. 查询单个的Trace / Span 详情 - QueryApmTraceDetailResource / QueryApmSpanDetailResource
5. 查询应用/服务的 Profiling 性能剖析数据 - QueryApmProfilingResource
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


class QueryApmProfilingResource(Resource):
    """
    查询 APM 应用/服务的 Profiling 性能剖析数据

    复用 ProfileQueryViewSet 内部 samples() 的标准查询流程:
        get_query_params -> converter_query -> converter_to_data

    默认仅输出 table 视图（按函数聚合的耗时/采样表），避免 flamegraph 巨型 JSON
    将 LLM 上下文撑爆;调用方如需调用图/火焰图可显式指定 diagram_types

    精简策略 (slim=True, 默认):
      - 按 total 降序取 top_n 条 (默认 100, 经验上可覆盖 95%+ 累计占用)
      - 移除冗余的 items[].id 字段 (id ≈ name + file_path + name 拼接, 信息冗余)
      - 增加 self_pct / total_pct 百分比, 便于 LLM 快速识别热点占比
      - 增加 table_data.truncated / original_item_count / returned_item_count 元信息

    完全透传 (slim=False):
      - 等同于前端 samples() 接口的原始返回, 不做任何裁剪
    """

    DEFAULT_TOP_N = 100
    # 全局 sentinel 函数, 不参与 top_n 截断 (始终在 items[0])
    GLOBAL_TOTAL_NAME = "total"
    # 当 settings 中没有定义 APM_PROFILING_MCP_MAX_TIME_SPAN_SECONDS 时的兜底默认值
    # (Profiling 秒级采样数据量大, 收紧到 30 分钟避免数据爆炸/LLM 上下文超限/下游查询超时)
    DEFAULT_MAX_TIME_SPAN_SECONDS = 30 * 60

    @classmethod
    def get_max_time_span_seconds(cls) -> int:
        """读取 settings 中配置的最大查询跨度, 支持配置中心动态调整"""
        return getattr(
            settings,
            "APM_PROFILING_MCP_MAX_TIME_SPAN_SECONDS",
            cls.DEFAULT_MAX_TIME_SPAN_SECONDS,
        )

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=False, label="应用名称")
        service_name = serializers.CharField(required=False, label="服务名称")
        global_query = serializers.BooleanField(required=False, default=False, label="全局查询")
        data_type = serializers.CharField(
            required=False,
            default=DEFAULT_PROFILE_DATA_TYPE,
            label="采样类型(sample_type/data_type)",
            help_text="形如 cpu/nanoseconds、alloc_space/bytes、inuse_space/bytes 等",
        )
        agg_method = serializers.CharField(
            required=False,
            default="AVG",
            allow_null=True,
            label="聚合方法",
            help_text="AVG(平均) / SUM(求和) / LAST(只保留最后一个时间窗口的样本)",
        )
        # 时间二选一: 优先取 start/end (微秒), 否则使用 start_time/end_time (秒)
        start = serializers.IntegerField(required=False, label="开始时间(微秒)")
        end = serializers.IntegerField(required=False, label="结束时间(微秒)")
        start_time = serializers.IntegerField(required=False, label="开始时间(秒)")
        end_time = serializers.IntegerField(required=False, label="结束时间(秒)")
        # 默认仅取 table 视图,降低返回体积
        diagram_types = serializers.ListField(
            child=serializers.CharField(),
            required=False,
            default=["table"],
            label="视图类型: table/flamegraph/callgraph/tendency",
        )
        filter_labels = serializers.DictField(required=False, default=dict, label="标签过滤")
        # 是否对 table 视图做 LLM 友好精简 (去 id + 截断 top_n + 加百分比), False 时完全透传原始数据
        slim = serializers.BooleanField(
            required=False,
            default=True,
            label="是否精简 table 视图",
            help_text="True(默认): 精简返回(适合 LLM); False: 完全透传 samples 接口原始数据",
        )
        # 仅在 slim=True 时生效: 按 total 降序保留前 N 项, 传 0 表示不截断
        top_n = serializers.IntegerField(
            required=False,
            default=100,
            min_value=0,
            label="table 视图 top N (slim=True 时生效)",
            help_text="按 total 降序保留前 N 个函数, 默认 100 (经验上可覆盖 95%+ 累计占用), 传 0 表示返回全部",
        )

        def validate(self, attrs):
            attrs = super().validate(attrs)
            # 复用 ProfileQuerySerializer 的约束: 非全局查询时 app_name/service_name 必填
            if not attrs.get("global_query"):
                if not attrs.get("app_name") or not attrs.get("service_name"):
                    raise serializers.ValidationError("app_name and service_name is required")

            # 时间字段: start/end (微秒) 或 start_time/end_time (秒) 至少一组
            if not attrs.get("start") and not attrs.get("start_time"):
                raise serializers.ValidationError("start or start_time is required")
            if not attrs.get("end") and not attrs.get("end_time"):
                raise serializers.ValidationError("end or end_time is required")

            # 若只给了秒级, 内部统一补齐为微秒, 与 ProfileQuerySerializer.to_internal_value 行为一致
            if not attrs.get("start") and attrs.get("start_time"):
                attrs["start"] = int(attrs["start_time"]) * 1_000_000
            if not attrs.get("end") and attrs.get("end_time"):
                attrs["end"] = int(attrs["end_time"]) * 1_000_000

            # Profiling 数据密度高, 校验最大查询跨度 (从 settings 读取, 支持配置中心动态调整)
            max_span_seconds = QueryApmProfilingResource.get_max_time_span_seconds()
            max_span_us = max_span_seconds * 1_000_000
            actual_span_us = int(attrs["end"]) - int(attrs["start"])
            if actual_span_us > max_span_us:
                raise serializers.ValidationError(
                    f"Profiling 查询时间跨度过大 ({actual_span_us / 60_000_000:.1f} 分钟), "
                    f"为避免数据量爆炸/LLM 上下文超限/下游查询超时, "
                    f"请控制在 {max_span_seconds // 60} 分钟内"
                )
            if actual_span_us <= 0:
                raise serializers.ValidationError("end 必须大于 start")
            return attrs

    def perform_request(self, validated_request_data):
        """
        统一走 ProfileQueryViewSet 的标准查询/聚合流程, 屏蔽 ebpf/普通应用的差异
        """
        # 仅保留 ProfileQuerySerializer 接受的字段, 避免透传到下游报错
        allowed_keys = {
            "bk_biz_id",
            "app_name",
            "service_name",
            "global_query",
            "data_type",
            "agg_method",
            "start",
            "end",
            "start_time",
            "end_time",
            "diagram_types",
            "filter_labels",
        }
        request_data = {k: v for k, v in validated_request_data.items() if k in allowed_keys}
        slim = validated_request_data.get("slim", True)
        top_n = validated_request_data.get("top_n", self.DEFAULT_TOP_N)

        validate_data, essentials, extra_params = ProfileQueryViewSet.get_query_params(request_data)
        tree_converter = ProfileQueryViewSet.converter_query(essentials, validate_data, extra_params)

        if not tree_converter or (hasattr(tree_converter, "empty") and tree_converter.empty()):
            logger.info(
                "QueryApmProfilingResource: empty profiling result, bk_biz_id=%s app_name=%s service_name=%s",
                essentials.get("bk_biz_id"),
                essentials.get("app_name"),
                essentials.get("service_name"),
            )
            return {}

        data = ProfileQueryViewSet.converter_to_data(validate_data, tree_converter)
        # 不精简时, 完全透传 converter_to_data 输出, 与前端 samples 接口一致
        if not slim:
            return data
        return self._slim_table_data(data, top_n)

    @classmethod
    def _slim_table_data(cls, data: dict, top_n: int) -> dict:
        """
        裁剪 table_data, 降低返回体积:
          - 删除冗余 id 字段
          - 按 total 降序保留 top_n 条 (top_n=0 表示全量)
          - 补充 self_pct / total_pct 占比, 便于 LLM 快速分析热点
          - 保留 global total 哨兵项, 不参与截断
        """
        table_data = data.get("table_data")
        if not isinstance(table_data, dict):
            return data

        items = table_data.get("items") or []
        if not items:
            return data

        total_value = table_data.get("total") or 0

        global_item, function_items = None, []
        for item in items:
            if item.get("name") == cls.GLOBAL_TOTAL_NAME and global_item is None:
                global_item = item
            else:
                function_items.append(item)

        # converter_to_data 默认已按 total 降序, 这里兜底再排一次, 防止上游调整
        function_items.sort(key=lambda x: x.get("total", 0) or 0, reverse=True)

        original_count = len(function_items)
        if top_n and top_n > 0:
            function_items = function_items[:top_n]

        def _slim(item: dict) -> dict:
            self_v = item.get("self", 0) or 0
            total_v = item.get("total", 0) or 0
            slimmed = {
                "name": item.get("name"),
                "self": self_v,
                "total": total_v,
            }
            if total_value:
                slimmed["self_pct"] = round(self_v / total_value * 100, 2)
                slimmed["total_pct"] = round(total_v / total_value * 100, 2)
            return slimmed

        slimmed_items = []
        if global_item is not None:
            slimmed_items.append(_slim(global_item))
        slimmed_items.extend(_slim(item) for item in function_items)

        new_table_data = {
            "total": total_value,
            "items": slimmed_items,
            "original_item_count": original_count,
            "returned_item_count": len(function_items),
            "truncated": bool(top_n and original_count > top_n),
        }

        return {**data, "table_data": new_table_data}
