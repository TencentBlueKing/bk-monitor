from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apps.exceptions import ValidationError


class BkIpSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(label=_("主机ID"), required=False)
    ip = serializers.IPAddressField(label=_("业务机器ip"), required=False, allow_null=True, allow_blank=True)
    bk_cloud_id = serializers.IntegerField(label=_("业务机器云区域id"), required=False)

    def validate(self, attrs):
        if "bk_host_id" in attrs or ("ip" in attrs and "bk_cloud_id" in attrs):
            return attrs
        raise ValidationError(_("bk_host_id 和 ip+bk_cloud_id 至少提供一项"))


class FrontendEventSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    dimensions = serializers.DictField(label="维度信息", required=False, default={})
    event_name = serializers.CharField(label="事件名称", required=True)
    event_content = serializers.CharField(label="事件内容", allow_blank=True, default="")
    target = serializers.CharField(label="事件目标", required=True)
    timestamp = serializers.IntegerField(label="事件时间戳(ms)", required=False)
