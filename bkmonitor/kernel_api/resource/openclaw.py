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
from rest_framework.exceptions import PermissionDenied, ValidationError

from apm.resources import QueryTraceDetailResource
from apm_web.trace.serializers import FilterSerializer as TraceFilterSerializer
from apm_web.trace.resources import ListFlattenSpanResource
from bkmonitor.utils.request import get_request_username
from constants.apm import TraceWaterFallDisplayKey
from core.drf_resource import Resource
from kernel_api.resource.log_search import SearchLogResource
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer


class SearchOpenClawSpansResource(Resource):
    """
    查询 OpenClaw Span 列表。参数对齐通用 APM Span 查询，服务端固定 OpenClaw 业务与应用。
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        offset = serializers.IntegerField(required=False, default=0, label="偏移量")
        limit = serializers.IntegerField(required=False, default=10, label="每页数量")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        sort = serializers.ListSerializer(required=False, default=[], label="排序条件", child=serializers.CharField())
        query = serializers.CharField(required=False, default="", allow_blank=True, allow_null=True, label="查询语句")
        filters = serializers.ListSerializer(
            required=False, default=[], label="查询条件", child=TraceFilterSerializer()
        )

    def perform_request(self, validated_request_data):
        params = dict(validated_request_data)
        # 业务和应用只能来自服务端配置，避免 MCP 调用方通过参数扩大查询范围。
        params["bk_biz_id"] = settings.OPENCLAW_RECOVERING_BK_BIZ_ID
        params["app_name"] = settings.OPENCLAW_RECOVERING_APM_APP_NAME

        username = get_request_username()
        if not username:
            raise PermissionDenied("Cannot resolve request username.")

        if username not in settings.OPENCLAW_RECOVERING_ADMIN_USERS:
            # 普通用户只能看到 owner 字段等于自己的 span；管理员保留完整 OpenClaw 查询能力。
            params["filters"] = [
                *(params.get("filters") or []),
                {
                    "key": settings.OPENCLAW_RECOVERING_TRACE_OWNER_FIELD,
                    "operator": "equal",
                    "value": [username],
                },
            ]

        return ListFlattenSpanResource().request(**params)


class GetOpenClawTraceDetailResource(Resource):
    """
    查询 OpenClaw Trace 详情。参数对齐通用 APM Trace 详情查询，普通用户会先校验 Trace 归属。
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        trace_id = serializers.CharField(required=True, label="trace_id")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        displays = serializers.ListField(
            child=serializers.ChoiceField(
                choices=TraceWaterFallDisplayKey.choices(),
                default=TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY,
            ),
            default=list,
            allow_empty=True,
            required=False,
        )
        query_trace_relation_app = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_request_data):
        username = get_request_username()
        if not username:
            raise PermissionDenied("Cannot resolve request username.")

        if username not in settings.OPENCLAW_RECOVERING_ADMIN_USERS:
            # Trace 详情接口本身无法按 owner 过滤，先用 Span 查询证明该 trace 属于当前用户。
            spans = ListFlattenSpanResource().request(
                bk_biz_id=settings.OPENCLAW_RECOVERING_BK_BIZ_ID,
                app_name=settings.OPENCLAW_RECOVERING_APM_APP_NAME,
                start_time=validated_request_data["start_time"],
                end_time=validated_request_data["end_time"],
                offset=0,
                limit=1,
                query="",
                filters=[
                    {"key": "trace_id", "operator": "equal", "value": [validated_request_data["trace_id"]]},
                    {
                        "key": settings.OPENCLAW_RECOVERING_TRACE_OWNER_FIELD,
                        "operator": "equal",
                        "value": [username],
                    },
                ],
                sort=["-start_time"],
            )
            if not spans.get("data"):
                raise PermissionDenied("Trace is not accessible for the current OpenClaw recovering request.")

        return QueryTraceDetailResource().request(
            bk_biz_id=settings.OPENCLAW_RECOVERING_BK_BIZ_ID,
            app_name=settings.OPENCLAW_RECOVERING_APM_APP_NAME,
            trace_id=validated_request_data["trace_id"],
            displays=validated_request_data.get("displays") or [],
            query_trace_relation_app=validated_request_data.get("query_trace_relation_app", False),
        )


class SearchOpenClawLogsResource(SearchLogResource):
    """
    查询 OpenClaw 日志。参数对齐通用日志查询，服务端固定业务并校验 OpenClaw 索引集。
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")
        query_string = serializers.CharField(required=False, default="*", allow_blank=True, label="查询字符串")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")
        limit = serializers.IntegerField(required=False, default=10, label="返回条数")

    def perform_request(self, validated_request_data):
        params = dict(validated_request_data)
        # 日志业务固定为 OpenClaw 业务，index_set 仍需限制在 OpenClaw 日志配置内。
        params["bk_biz_id"] = settings.OPENCLAW_RECOVERING_BK_BIZ_ID

        index_set_ids = {int(value) for value in settings.OPENCLAW_RECOVERING_LOG_INDEX_SET_MAP.values()}
        if int(params["index_set_id"]) not in index_set_ids:
            raise ValidationError({"index_set_id": "index_set_id is not in OpenClaw log index set config."})

        username = get_request_username()
        if not username:
            raise PermissionDenied("Cannot resolve request username.")

        if username not in settings.OPENCLAW_RECOVERING_ADMIN_USERS:
            # 在用户原始 query 外层追加 owner 条件，避免绕过身份范围。
            field = settings.OPENCLAW_RECOVERING_LOG_OWNER_FIELD
            query_string = (params.get("query_string") or "*").strip() or "*"
            owner_query = f'({field}: "{username}")'
            params["query_string"] = owner_query if query_string == "*" else f"{owner_query} AND ({query_string})"

        return super().perform_request(params)
