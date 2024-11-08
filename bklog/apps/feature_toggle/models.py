# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _

from apps.feature_toggle.plugins.constants import LOG_DESENSITIZE
from apps.models import SoftDeleteModel


class FeatureToggle(SoftDeleteModel):
    """
    日志平台特性开关整合表
    """

    name = models.CharField(_("特性开关name"), max_length=64, unique=True)
    alias = models.CharField(_("特性开关别名"), max_length=64, null=True, blank=True)
    status = models.CharField(_("特性开关status"), max_length=32, default="off")
    description = models.TextField(_("特性开关描述"), null=True, blank=True)
    is_viewed = models.BooleanField(_("是否在前端展示"), default=True)
    feature_config = models.JSONField(_("特性开关配置"), null=True, blank=True)
    biz_id_white_list = models.JSONField(_("业务白名单"), null=True, blank=True)

    class Meta:
        verbose_name = _("日志平台特性开关")
        verbose_name_plural = _("41_日志平台特性开关")

    @classmethod
    def check_data_desensitize(cls, username: str, bk_biz_id: str) -> bool:
        """
        根据用户名和业务ID判断数据是否需要脱敏
        :param username: 用户名
        :param bk_biz_id: 业务ID
        """
        feature_toggle = cls.objects.filter(name=LOG_DESENSITIZE).first()
        if not feature_toggle or not isinstance(feature_toggle.feature_config, dict):
            return True
        user_white_list = feature_toggle.feature_config.get("user_white_list", {})
        if username in user_white_list.get(bk_biz_id, []):
            return False
        return True
