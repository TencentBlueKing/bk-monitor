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
from django.utils.translation import gettext_lazy as _
from jinja2 import Template
from rest_framework import serializers

from apps.exceptions import ValidationError
from apps.log_desensitize.handlers.desensitize_operator.base import (
    DesensitizeMethodBase,
)


class DesensitizeTextReplace(DesensitizeMethodBase):
    """
    文本替换算子
    """

    class ParamsSerializer(serializers.Serializer):
        """
        脱敏配置参数序列化器
        """

        template_string = serializers.CharField(label=_("替换模板格式"), required=False)

        def validate(self, attrs):
            attrs = super().validate(attrs)
            try:
                Template(variable_start_string="${", variable_end_string="}", source=attrs.get("template_string"))
            except Exception as e:
                raise ValidationError(_("替换模板格式不正确: {}").format(e))

            return attrs

    def __init__(self, template_string: str, **kwargs):
        """
        params {String} template_string  替换格式 参数示例: "abc${partNum}defg"
        """
        self.template_string = template_string
        self.template = Template(variable_start_string="${", variable_end_string="}", source=self.template_string)

    def transform(self, target_text: str = None, context: dict = None):
        """
        通过正则匹配到字符后替换字符 场景示例: 13234345678 -> abc3434defg
        params: target_text  13234345678
        params: context 由上层工厂通过正则提取出来的 k:v 键值对 为空的情况下默认返回原字符串
        """
        # 参数校验逻辑
        if not target_text:
            return ""

        context = context or {}

        # 模板渲染
        result = self.template.render(**context)

        return result
