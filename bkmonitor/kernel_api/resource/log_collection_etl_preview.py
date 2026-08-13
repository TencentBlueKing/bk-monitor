"""日志清洗结果预览 MCP 资源。"""

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from api.log_search.default import EtlPreviewRequestSerializer
from constants.log_collection import (
    ETL_CONFIG_DELIMITER,
    ETL_CONFIG_TEXT,
    ETL_PREVIEW_MAX_FIELDS,
)
from core.drf_resource import Resource, api
from core.errors.api import BKAPIError

_VALIDATION_ERRORS_KEY = "_validation_errors"
BKLOG_ETL_VALIDATION_ERROR_CODES = {
    "3600001",
    "3600914",
    "3600916",
    "3631303",
}


def normalize_error_details(value: Any) -> Any:
    """把 DRF ErrorDetail 递归转换为 MCP 可序列化的普通值。"""
    if isinstance(value, Mapping):
        return {str(key): normalize_error_details(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [normalize_error_details(item) for item in value]
    return str(value)


class EtlPreviewFieldSerializer(serializers.Serializer):
    field_index = serializers.IntegerField(min_value=1)
    field_name = serializers.CharField(allow_blank=True)
    value = serializers.JSONField(allow_null=True)


class EtlPreviewErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(required=False, default=dict)


class PreviewLogEtlResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    etl_config = serializers.CharField(allow_blank=True)
    fields = EtlPreviewFieldSerializer(many=True, max_length=ETL_PREVIEW_MAX_FIELDS)
    field_count = serializers.IntegerField(min_value=0, max_value=ETL_PREVIEW_MAX_FIELDS)
    error = EtlPreviewErrorSerializer(allow_null=True)


class PreviewLogEtlResource(Resource):
    """预览文本、JSON、正则或分隔符清洗结果，不创建或修改任何持久化配置。"""

    RequestSerializer = EtlPreviewRequestSerializer
    ResponseSerializer = PreviewLogEtlResponseSerializer

    def validate_request_data(self, request_data):
        """把参数校验失败收敛为与 BKLOG 校验失败一致的 Tool 返回。"""
        request_serializer = self.RequestSerializer(data=request_data)
        self._request_serializer = request_serializer
        if request_serializer.is_valid():
            return request_serializer.validated_data

        etl_config = ""
        if isinstance(request_data, Mapping):
            raw_etl_config = request_data.get("etl_config")
            if isinstance(raw_etl_config, str):
                etl_config = raw_etl_config
        return {
            _VALIDATION_ERRORS_KEY: normalize_error_details(request_serializer.errors),
            "etl_config": etl_config,
        }

    @staticmethod
    def build_success(etl_config: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "success": True,
            "etl_config": etl_config,
            "fields": fields,
            "field_count": len(fields),
            "error": None,
        }

    @staticmethod
    def build_failure(
        etl_config: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "etl_config": etl_config,
            "fields": [],
            "field_count": 0,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        }

    @staticmethod
    def normalize_fields(etl_config: str, response: Any) -> list[dict[str, Any]]:
        if not isinstance(response, Mapping) or "fields" not in response:
            raise ValueError("BKLOG ETL Preview returned an invalid response.")

        raw_fields = response["fields"]
        if etl_config == ETL_CONFIG_TEXT:
            if not isinstance(raw_fields, str):
                raise ValueError("BKLOG text ETL Preview returned an invalid response.")
            return [{"field_index": 1, "field_name": "log", "value": raw_fields}]

        if not isinstance(raw_fields, list):
            raise ValueError("BKLOG structured ETL Preview returned an invalid response.")

        fields = []
        for index, field in enumerate(raw_fields, start=1):
            if not isinstance(field, Mapping):
                raise ValueError("BKLOG ETL Preview field is not an object.")
            fields.append(
                {
                    "field_index": index,
                    "field_name": str(field.get("field_name") or ""),
                    "value": field.get("value"),
                }
            )
        return fields

    def perform_request(self, validated_request_data):
        etl_config = validated_request_data.get("etl_config", "")
        if _VALIDATION_ERRORS_KEY in validated_request_data:
            return self.build_failure(
                etl_config=etl_config,
                code="invalid_request",
                message="ETL preview request validation failed.",
                details=validated_request_data[_VALIDATION_ERRORS_KEY],
            )

        if etl_config == ETL_CONFIG_DELIMITER:
            separator = validated_request_data["etl_params"]["separator"]
            field_count = validated_request_data["data"].count(separator) + 1
            if field_count > ETL_PREVIEW_MAX_FIELDS:
                return self.build_failure(
                    etl_config=etl_config,
                    code="too_many_fields",
                    message=f"ETL preview supports at most {ETL_PREVIEW_MAX_FIELDS} fields.",
                    details={"field_count": field_count},
                )

        try:
            response = api.log_search.log_etl_preview(**validated_request_data)
        except BKAPIError as error:
            error_data = error.data if isinstance(error.data, Mapping) else {}
            backend_code = str(error_data.get("code") or "")
            if backend_code not in BKLOG_ETL_VALIDATION_ERROR_CODES:
                raise
            return self.build_failure(
                etl_config=etl_config,
                code="invalid_etl_config",
                message=str(error_data.get("message") or "BKLOG rejected the ETL preview configuration."),
                details={"backend_code": backend_code},
            )

        fields = self.normalize_fields(etl_config, response)
        if len(fields) > ETL_PREVIEW_MAX_FIELDS:
            return self.build_failure(
                etl_config=etl_config,
                code="too_many_fields",
                message=f"ETL preview supports at most {ETL_PREVIEW_MAX_FIELDS} fields.",
                details={"field_count": len(fields)},
            )
        return self.build_success(etl_config, fields)
