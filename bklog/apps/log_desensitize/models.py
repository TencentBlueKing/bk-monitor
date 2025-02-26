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
from django.db import models, transaction  # noqa
from django.utils.translation import gettext_lazy as _  # noqa

from apps.log_desensitize.constants import DesensitizeOperator
from apps.models import OperateRecordModel, SoftDeleteModel


class DesensitizeRule(SoftDeleteModel):
    """
    脱敏规则
    """

    rule_name = models.CharField(_("脱敏规则名称"), max_length=128)
    operator = models.CharField(_("脱敏算子"), max_length=64, choices=DesensitizeOperator.get_choices())
    params = models.JSONField(_("脱敏参数"), default=dict, null=True)
    match_pattern = models.TextField(_("匹配模式"), default="", null=True, blank=True)
    space_uid = models.CharField(_("空间唯一标识"), blank=True, default="", max_length=256)
    is_public = models.BooleanField(_("是否为公共规则"), default=False)
    match_fields = models.JSONField(_("匹配字段名"), null=True, default=list)
    is_active = models.BooleanField(_("是否启用"), default=True)

    class Meta:
        verbose_name = _("脱敏规则")
        verbose_name_plural = _("脱敏规则")
        ordering = ("-updated_at",)


class DesensitizeConfig(OperateRecordModel):
    """
    脱敏配置
    """

    index_set_id = models.IntegerField(_("索引集ID"), db_index=True)
    text_fields = models.JSONField(_("日志原文字段"), null=True, default=list)

    class Meta:
        verbose_name = _("脱敏配置")
        verbose_name_plural = _("脱敏配置")
        ordering = ("-updated_at",)


class DesensitizeFieldConfig(OperateRecordModel):
    """
    脱敏字段配置信息
    """

    index_set_id = models.IntegerField(_("索引集ID"), db_index=True)
    field_name = models.CharField(_("字段名称"), max_length=64, blank=True, default="")
    rule_id = models.IntegerField(_("脱敏规则ID"), default=0, db_index=True)
    match_pattern = models.TextField(_("匹配模式"), default="", null=True, blank=True)
    operator = models.CharField(_("脱敏算子"), max_length=64, choices=DesensitizeOperator.get_choices())
    params = models.JSONField(_("脱敏参数"), default=dict, null=True)
    sort_index = models.IntegerField(_("优先级"), null=True, default=0)

    class Meta:
        verbose_name = _("脱敏字段配置")
        verbose_name_plural = _("脱敏字段配置")
        ordering = ("-updated_at",)
