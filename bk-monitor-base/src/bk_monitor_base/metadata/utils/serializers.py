from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from bk_monitor_base.metadata.utils.request import get_request_tenant_id


class TenantIdField(serializers.CharField):
    """
    租户ID字段
    如果传入的值为空，则使用当前请求的租户ID
    """

    def __init__(self, *args, prefer_request_tenant=True, **kwargs):
        kwargs["required"] = False

        super().__init__(*args, **kwargs)
        self._allow_blank = kwargs.get("allow_blank", False)
        self.allow_blank = True
        self.prefer_request_tenant = prefer_request_tenant

    def run_validation(self, data=empty):
        # 如果传入的值为空，则使用当前请求的租户ID
        if self.prefer_request_tenant or not data or data is empty:
            request_tenant_id = get_request_tenant_id(peaceful=True)
            if request_tenant_id:
                data = request_tenant_id

        # 如果租户ID为空，则抛出异常
        if (not data or data is empty) and not self._allow_blank:
            raise ValidationError(_("tenant_id is required"))

        return super().run_validation(data)
