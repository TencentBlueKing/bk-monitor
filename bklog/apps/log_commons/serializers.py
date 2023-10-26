from apps.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class BkIpSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(label=_("主机ID"), required=False)
    ip = serializers.IPAddressField(label=_("业务机器ip"), required=False, allow_null=True, allow_blank=True)
    bk_cloud_id = serializers.IntegerField(label=_("业务机器云区域id"), required=False)

    def validate(self, attrs):
        if "bk_host_id" in attrs or ("ip" in attrs and "bk_cloud_id" in attrs):
            return attrs
        raise ValidationError(_("bk_host_id 和 ip+bk_cloud_id 至少提供一项"))
