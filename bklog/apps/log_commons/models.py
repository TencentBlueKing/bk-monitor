from datetime import datetime

import pytz
from apps.constants import ApiTokenAuthType
from apps.models import OperateRecordModel
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _


def get_random_string_16() -> str:
    """
    获取16位随机字符串
    :return:
    """
    return get_random_string(length=16)


class ApiAuthToken(OperateRecordModel):
    """API鉴权令牌"""

    space_uid = models.CharField(_("空间唯一标识"), blank=True, default="", max_length=256, db_index=True)
    token = models.CharField(_("鉴权令牌"), max_length=32, default=get_random_string_16)
    type = models.CharField(_("鉴权类型"), max_length=32, choices=ApiTokenAuthType.get_choices())
    params = models.JSONField(_("鉴权参数"), default=dict)
    expire_time = models.DateTimeField(_("过期时间"), null=True, default=None)

    class Meta:
        verbose_name = _("API鉴权令牌")
        verbose_name_plural = _("API鉴权令牌")

    def is_expired(self):
        """
        判断token是否过期
        """
        # 未设置过期时间，不判断是否过期
        if not self.expire_time:
            return False
        return self.expire_time < datetime.now(tz=pytz.utc)
