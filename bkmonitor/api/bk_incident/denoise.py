"""每次调用使用当前用户 OAuth 凭证，禁止复用 Resource 单例上的用户状态。"""

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from bkapi_client_core.exceptions import ResponseError
from bkoauth.client import oauth_client
from django.conf import settings
from django.utils import translation
from requests.exceptions import RequestException
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from api.bk_incident.client import BKFaraClient
from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource
from core.errors.api import BKAPIError


class DenoiseTransportSerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=256)
    scope_id = serializers.CharField(max_length=193)
    scope_type = serializers.CharField(max_length=64)
    scope_value = serializers.CharField(max_length=128)

    def to_internal_value(self, data):
        allowed = set(self.fields) | {
            "start_time",
            "end_time",
            "alert_id",
            "alert_ids",
            "alert_source",
            "alert_name",
            "strategy_id",
            "severity",
            "rule_source",
            "outcome",
            "stage",
            "reason_code",
            "rule_id",
            "cluster_id",
            "run_id",
            "view_mode",
            "page",
            "page_size",
        }
        if set(data) - allowed:
            raise serializers.ValidationError("Unexpected query fields")
        return {**data, **super().to_internal_value(data)}


class DenoiseReadBaseResource(APIResource):
    module_name = "bkfara"
    INSERT_BK_USERNAME_TO_REQUEST_DATA = False
    RequestSerializer = DenoiseTransportSerializer

    @property
    def base_url(self):
        return settings.BKFARA_APIGW_BASE_URL

    def perform_request(self, validated_request_data):
        request = get_request(peaceful=True)
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise PermissionDenied("Verified user required")
        tenant = getattr(user, "tenant_id", None) if settings.ENABLE_MULTI_TENANT_MODE else "system"
        if not tenant or validated_request_data["bk_tenant_id"] != tenant:
            raise PermissionDenied("Tenant mismatch")
        endpoint = self.base_url
        if not endpoint or not endpoint.strip():
            raise BKAPIError(
                system_name=self.module_name,
                url=self.action,
                result={"message": "BKFARA_APIGW_BASE_URL is not configured"},
            )
        ca_bundle = getattr(settings, "BKFARA_CA_BUNDLE", "")
        if ca_bundle and (not isinstance(ca_bundle, str) or not Path(ca_bundle).is_file()):
            raise BKAPIError(
                system_name=self.module_name,
                url=self.action,
                result={"message": "BKFARA_CA_BUNDLE must reference a trusted CA file"},
            )
        token = oauth_client.get_access_token(request)
        if not getattr(token, "access_token", None):
            raise PermissionDenied("User access token required")
        client = BKFaraClient(endpoint=endpoint, stage="")
        client.update_bkapi_authorization(
            bk_app_code=settings.APP_CODE, bk_app_secret=settings.SECRET_KEY, access_token=token.access_token
        )
        # 支持内部 CA；没有专用 CA 时沿用 requests 的默认信任链和环境 CA 配置。
        client.session.verify = ca_bundle or True
        headers = {"X-Bk-Tenant-Id": tenant}
        language = translation.get_language()
        if language:
            headers["blueking-language"] = language
        client.update_headers(headers)
        payload = {
            key: value.isoformat()
            if isinstance(value, date | datetime)
            else str(value)
            if isinstance(value, UUID)
            else value
            for key, value in validated_request_data.items()
        }
        operation = getattr(client.denoise, self.client_operation)
        try:
            response = operation(**{"params" if self.method == "GET" else "data": payload}, timeout=self.TIMEOUT)
        except (ResponseError, RequestException) as error:
            raise BKAPIError(
                system_name=self.module_name,
                url=self.action,
                result={"code": getattr(error, "response_status_code", None), "message": "BKFara denoise query failed"},
            ) from error
        if (
            not isinstance(response, dict)
            or response.get("result") is not True
            or not isinstance(response.get("data"), dict)
        ):
            raise BKAPIError(
                system_name=self.module_name, url=self.action, result={"message": "Invalid BKFara denoise response"}
            )
        return response["data"]
