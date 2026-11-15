"""监控 SaaS 的降噪只读入口，业务和租户来自当前登录态及空间服务。"""

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from bkm_space.api import SpaceApi
from bkmonitor.iam import Permission
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.resource import ResourceEnum
from bkmonitor.utils.request import get_request
from core.drf_resource import api
from core.drf_resource.base import Resource


class DenoiseScopeSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField()

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate_bk_biz_id(self, value):
        if value in {0, -1, -2}:
            raise serializers.ValidationError("必须指定单个真实业务空间")
        return value


class DenoiseQuerySerializer(DenoiseScopeSerializer):
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    alert_id = serializers.CharField(max_length=255, required=False)
    alert_ids = serializers.ListField(
        child=serializers.CharField(max_length=255), min_length=1, max_length=200, required=False
    )
    alert_name = serializers.CharField(max_length=1024, required=False)
    strategy_id = serializers.CharField(max_length=255, required=False)
    severity = serializers.CharField(max_length=32, required=False)
    rule_source = serializers.ChoiceField(choices=["builtin", "custom", "default"], required=False)
    outcome = serializers.ChoiceField(
        choices=["filtered", "aggregated", "retained", "occurrence_suppressed", "unknown"], required=False
    )
    stage = serializers.ChoiceField(
        choices=["filter", "denoise", "arbitrate", "complete", "post_incident"], required=False
    )
    reason_code = serializers.CharField(max_length=64, required=False)
    rule_id = serializers.CharField(max_length=128, required=False)
    cluster_id = serializers.CharField(required=False)
    run_id = serializers.UUIDField(required=False)
    view_mode = serializers.ChoiceField(choices=["latest", "history"], default="latest")
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=50, min_value=1, max_value=200)

    def validate(self, attrs):
        from datetime import timedelta

        duration = attrs["end_time"] - attrs["start_time"]
        if not timedelta(0) < duration <= timedelta(days=31):
            raise serializers.ValidationError("查询时间范围必须大于 0 且不超过 31 天")
        return attrs


class AlertDenoiseQuerySerializer(DenoiseQuerySerializer):
    alert_ids = serializers.ListField(child=serializers.CharField(max_length=255), min_length=1, max_length=200)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        restricted = {
            "outcome",
            "stage",
            "reason_code",
            "rule_id",
            "alert_id",
            "alert_name",
            "strategy_id",
            "severity",
            "rule_source",
            "cluster_id",
            "run_id",
        }
        if restricted.intersection(attrs) or attrs.get("view_mode") == "history":
            raise serializers.ValidationError("批量查询只返回告警最新结果")
        attrs["alert_ids"] = list(dict.fromkeys(attrs["alert_ids"]))
        return attrs


def authorize_scope(data, request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "username", ""):
        raise PermissionDenied("需要已登录用户")
    tenant = getattr(user, "tenant_id", None) if settings.ENABLE_MULTI_TENANT_MODE else "system"
    if not tenant:
        raise PermissionDenied("无法确定当前用户租户")
    biz_id = data["bk_biz_id"]
    if biz_id in {0, -1, -2}:
        raise PermissionDenied("必须指定单个真实业务空间")
    request_biz = getattr(request, "biz_id", None)
    if request_biz is not None and str(request_biz) != str(biz_id):
        raise PermissionDenied("请求业务与鉴权上下文不一致")
    space = SpaceApi.get_space_detail(bk_biz_id=biz_id)
    if (
        not space
        or space.bk_tenant_id != tenant
        or space.bk_biz_id != biz_id
        or not space.space_type_id
        or not space.space_id
    ):
        raise PermissionDenied("业务空间不属于当前租户")
    if not Permission().is_allowed(
        action=ActionEnum.VIEW_BUSINESS, resources=[ResourceEnum.BUSINESS.create_instance(biz_id)], raise_exception=True
    ):
        raise PermissionDenied("无业务查看权限")
    return {
        "bk_tenant_id": tenant,
        "scope_type": space.space_type_id,
        "scope_value": str(space.space_id),
        "scope_id": f"{space.space_type_id}_{space.space_id}",
    }


class DenoiseReadPermission(BasePermission):
    def has_permission(self, request, view):
        serializer_class = (
            DenoiseScopeSerializer
            if view.action == "denoise_policy"
            else (AlertDenoiseQuerySerializer if view.action == "alert_denoise_decisions" else DenoiseQuerySerializer)
        )
        serializer = serializer_class(data=request.query_params if request.method == "GET" else request.data)
        serializer.is_valid(raise_exception=True)
        authorize_scope(serializer.validated_data, request)
        return True


def forward(data, operation, *, query=True):
    scope = authorize_scope(data, get_request(peaceful=True))
    payload = {key: value for key, value in data.items() if key != "bk_biz_id"}
    payload.update(scope)
    if query:
        payload["alert_source"] = "bk_monitor"
    return operation(payload)


class ListDenoiseDecisionsResource(Resource):
    RequestSerializer = DenoiseQuerySerializer

    def perform_request(self, validated_request_data):
        return forward(validated_request_data, api.bk_incident.list_denoise_decisions)


class GetAlertDenoiseDecisionsResource(Resource):
    RequestSerializer = AlertDenoiseQuerySerializer

    def perform_request(self, validated_request_data):
        return forward(validated_request_data, api.bk_incident.get_alert_denoise_decisions)


class GetDenoisePolicyResource(Resource):
    RequestSerializer = DenoiseScopeSerializer

    def perform_request(self, validated_request_data):
        return forward(validated_request_data, api.bk_incident.get_denoise_policy, query=False)
