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
import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.exceptions import ValidationError
from apps.log_desensitize.constants import DesensitizeOperator, DesensitizeRuleTypeEnum
from apps.log_desensitize.handlers.desensitize_operator import OPERATOR_MAPPING
from apps.log_search.serializers import DesensitizeConfigsSerializer
from bkm_space.serializers import SpaceUIDField


class DesensitizeRuleListSerializer(serializers.Serializer):
    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=False, allow_null=True, allow_blank=True)
    rule_type = serializers.ChoiceField(label=_("规则类型"), choices=DesensitizeRuleTypeEnum.get_choices(), required=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs["rule_type"] != DesensitizeRuleTypeEnum.PUBLIC.value and not attrs.get("space_uid"):
            raise ValidationError(_("空间唯一标识不能为空"))

        return attrs


class DesensitizeRuleSerializer(serializers.Serializer):
    rule_name = serializers.CharField(label=_("脱敏规则名称"), required=True, max_length=64)
    match_fields = serializers.ListField(label=_("匹配字段名"), child=serializers.CharField(), required=False, default=list)
    match_pattern = serializers.CharField(
        label=_("匹配表达式"), required=False, allow_null=True, allow_blank=True, default=""
    )
    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=False)
    operator = serializers.ChoiceField(label=_("脱敏算子"), choices=DesensitizeOperator.get_choices(), required=True)
    operator_params = serializers.DictField(label=_("脱敏配置参数"), required=False)
    is_public = serializers.BooleanField(label=_("是否为全局规则"), required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs.get("is_public"):
            # 全局规则不关联业务属性
            attrs["space_uid"] = ""

        # 脱敏算子校验逻辑
        if not attrs.get("operator"):
            raise ValidationError(_("脱敏算子不能为空"))

        # 匹配字段名和正则不允许同时为空
        if not attrs.get("match_fields") and not attrs.get("match_pattern"):
            raise ValidationError(_("匹配字段名和正则表达式不能同时为空"))

        # 校验正则表达式的合法性
        match_pattern = attrs.get("match_pattern")
        if match_pattern:
            try:
                re.compile(match_pattern)
            except re.error:
                raise ValidationError(_("正则表达式 [{}] 不合法").format(match_pattern))

        desensitize_cls = OPERATOR_MAPPING.get(attrs.get("operator"))

        if not desensitize_cls:
            raise ValidationError(_("[{}] 脱敏算子类型暂未支持").format(attrs.get("operator")))

        if not attrs.get("operator_params"):
            return attrs

        desensitize_serializer = desensitize_cls.ParamsSerializer(data=attrs.get("operator_params"), many=False)

        # 脱敏参数校验
        desensitize_serializer.is_valid(raise_exception=True)

        data = desensitize_serializer.validated_data

        # 赋值
        attrs["operator_params"] = dict(data)

        return attrs


class DesensitizeRuleRegexDebugSerializer(serializers.Serializer):
    log_sample = serializers.CharField(label=_("日志样例"), required=True)
    match_pattern = serializers.CharField(label=_("正则表达式"), required=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # 校验正则表达式的合法性
        match_pattern = attrs.get("match_pattern")
        try:
            re.compile(match_pattern)
        except re.error:
            raise ValidationError(_("正则表达式 [{}] 不合法").format(match_pattern))

        return attrs


class DesensitizeRuleDebugSerializer(serializers.Serializer):
    log_sample = serializers.CharField(label=_("日志样例"), required=True)
    match_pattern = serializers.CharField(label=_("正则表达式"), required=True)
    operator = serializers.ChoiceField(label=_("脱敏算子"), choices=DesensitizeOperator.get_choices(), required=True)
    params = serializers.DictField(label=_("脱敏配置参数"), required=False, default=dict)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # 校验正则表达式的合法性
        match_pattern = attrs.get("match_pattern")
        try:
            re.compile(match_pattern)
        except re.error:
            raise ValidationError(_("正则表达式 [{}] 不合法").format(match_pattern))

        # 获取算子对象
        desensitize_cls = OPERATOR_MAPPING.get(attrs.get("operator"))

        if not desensitize_cls:
            raise ValidationError(_("{}脱敏算子类型暂未支持").format(attrs.get("operator")))

        if not attrs.get("params"):
            return attrs

        desensitize_serializer = desensitize_cls.ParamsSerializer(data=attrs.get("params"), many=False)

        # 脱敏参数校验
        desensitize_serializer.is_valid(raise_exception=True)

        data = desensitize_serializer.validated_data

        # 赋值
        attrs["params"] = dict(data)

        return attrs


class DesensitizeRuleMatchSerializer(serializers.Serializer):
    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    logs = serializers.ListField(label=_("日志原文列表"), child=serializers.DictField(), required=True, allow_empty=False)
    fields = serializers.ListField(label=_("匹配字段列表"), required=True, allow_empty=False)


class DesensitizeRulePreviewSerializer(serializers.Serializer):
    logs = serializers.ListField(label=_("日志原文列表"), child=serializers.DictField(), required=True, allow_empty=False)
    field_configs = serializers.ListField(child=DesensitizeConfigsSerializer(), required=True)
    text_fields = serializers.ListField(child=serializers.CharField(), required=False, default=list)
