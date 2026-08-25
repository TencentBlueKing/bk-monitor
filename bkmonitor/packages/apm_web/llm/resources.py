from rest_framework import serializers

from constants.apm import OtlpKey
from constants.otel_query import OperatorEnum
from core.drf_resource import Resource, api

from apm_web.llm.adapter import adapt_trace


class ListSpansResource(Resource):
    """查询指定 Trace 的 Span 列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        trace_id = serializers.CharField(required=True, label="trace_id")
        sdk_type = serializers.ChoiceField(
            required=False,
            choices=("agentlens", "bkaidev", "galileo"),
            label="SDK类型",
        )

    def perform_request(self, validated_request_data):
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "filters": [
                {
                    "key": OtlpKey.TRACE_ID,
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [validated_request_data["trace_id"]],
                }
            ],
            "limit": 10000,
            "exclude_field": ["bk_app_code"],
        }
        response = api.apm_api.query_span_list(params)
        raw_spans = response.get("data", [])
        trace = adapt_trace(
            raw_spans,
            trace_id=validated_request_data["trace_id"],
            app_name=validated_request_data["app_name"],
            sdk_type=validated_request_data.get("sdk_type"),
            include_content=True,
            partial=response.get("total", len(raw_spans)) > len(raw_spans),
        )
        spans = trace["spans"]
        return {
            "trace_id": validated_request_data["trace_id"],
            "total": len(spans),
            "spans": spans,
        }
