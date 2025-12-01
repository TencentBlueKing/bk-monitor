from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.constants import OperateEnum, ViewTypeEnum, ApiTokenAuthType
from apps.exceptions import ValidationError


class BkIpSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(label=_("主机ID"), required=False)
    ip = serializers.IPAddressField(label=_("业务机器ip"), required=False, allow_null=True, allow_blank=True)
    bk_cloud_id = serializers.IntegerField(label=_("业务机器云区域id"), required=False)

    def validate(self, attrs):
        if "bk_host_id" in attrs or ("ip" in attrs and "bk_cloud_id" in attrs):
            return attrs
        raise ValidationError(_("bk_host_id 和 ip+bk_cloud_id 至少提供一项"))


class GetAuthorizerSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间ID")


class ListMaintainersSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=True, label="空间ID")


class CreateORUpdateMaintainersSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=True, label="空间ID")
    maintainer = serializers.CharField(required=True, label="维护人")


class ListExternalPermissionSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间ID")
    view_type = serializers.CharField(required=False, label="视角类型", default=ViewTypeEnum.USER.value)


class CreateORUpdateExternalPermissionSLZ(serializers.Serializer):
    authorized_users = serializers.ListField(required=True, label="被授权人", child=serializers.CharField())
    view_type = serializers.CharField(required=False, label="视角类型", default=ViewTypeEnum.USER.value)
    operate_type = serializers.CharField(required=False, label="操作类型", default=OperateEnum.CREATE.value)
    space_uid = serializers.CharField(required=True, label="空间ID")
    action_id = serializers.CharField(required=True, label="操作类型")
    resources = serializers.ListField(required=True, label="资源列表", allow_empty=False)
    expire_time = serializers.DateTimeField(required=False, default=None, label="过期时间", allow_null=True)


class GetResourceByActionSLZ(serializers.Serializer):
    action_id = serializers.CharField(required=True, label="操作类型")
    space_uid = serializers.CharField(required=False, label="空间ID", default="")


class GetApplyRecordSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间ID", default="")


class DestroyExternalPermissionSLZ(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间ID", default="")
    action_id = serializers.CharField(required=True, label="操作类型")
    resources = serializers.ListField(required=True, label="资源列表")
    authorized_users = serializers.ListField(required=True, label="被授权人")
    view_type = serializers.CharField(required=False, label="视角类型", default=ViewTypeEnum.USER.value)


class FrontendEventSerializer(serializers.Serializer):
    dimensions = serializers.DictField(label="维度信息", required=False, default={})
    event_name = serializers.CharField(label="事件名称", required=True)
    event_content = serializers.CharField(label="事件内容", allow_blank=True, default="")
    target = serializers.CharField(label="事件目标", required=True)
    timestamp = serializers.IntegerField(label="事件时间戳(ms)", required=False)


class CreateOrUpdateTokenSerializer(serializers.Serializer):
    space_uid = serializers.CharField(required=True, label="空间ID")
    type = serializers.CharField(required=True, label="鉴权类型")
    expire_time = serializers.IntegerField(required=True, label="过期时间")
    expire_period = serializers.CharField(required=True, label="有效期")
    token = serializers.CharField(required=False, label="鉴权令牌")
    lock_search = serializers.BooleanField(required=False, default=False, label="是否锁定查询时间")
    default_time_range = serializers.ListField(required=False, default=[], label="默认时间范围")
    start_time = serializers.IntegerField(required=False, default=None, label="开始时间")
    end_time = serializers.IntegerField(required=False, default=None, label="结束时间")
    data = serializers.DictField(required=False, default={}, label="鉴权参数")


class GetShareParamsSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, label="鉴权令牌")


class GetApiTokenSerializer(serializers.Serializer):
    space_uid = serializers.CharField(required=True, label="空间ID")
    type = serializers.ChoiceField(
        choices=ApiTokenAuthType.get_choices(), default=ApiTokenAuthType.CODECC.value, required=False, label="令牌类型"
    )
