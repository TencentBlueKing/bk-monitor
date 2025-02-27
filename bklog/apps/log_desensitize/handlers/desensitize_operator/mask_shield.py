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
from rest_framework import serializers

from apps.log_desensitize.handlers.desensitize_operator.base import (
    DesensitizeMethodBase,
)


class DesensitizeMaskShield(DesensitizeMethodBase):
    """
    掩码屏蔽算子
    """

    class ParamsSerializer(serializers.Serializer):
        """
        脱敏配置参数
        """

        preserve_head = serializers.IntegerField(label=_("保留前几位"), required=False, min_value=0)
        preserve_tail = serializers.IntegerField(label=_("保留后几位"), required=False, min_value=0)
        replace_mark = serializers.CharField(label=_("替换符号"), required=False)

    def __init__(self, preserve_head: int = 0, preserve_tail: int = 0, replace_mark: str = "*", **kwargs):
        """
        params: preserve_head 保留前 preserve_head 位
        params: preserve_tail 保留后 preserve_tail 位
        params: replace_mark 替换符号
        """
        self.preserve_head = preserve_head
        self.preserve_tail = preserve_tail
        self.replace_mark = replace_mark

    def transform(self, target_text: str = "", context: dict = None):
        """
        场景示例: 13234345678 -> 132******78
        params: target_text

        """
        # 参数校验逻辑
        if not target_text:
            return ""
        if self.preserve_head == self.preserve_tail == 0:
            # 替换所有字符
            return self.replace_mark * len(target_text)

        if self.preserve_head + self.preserve_tail >= len(target_text):
            # 不进行掩码屏蔽
            return target_text

        tail_text = target_text[-self.preserve_tail :] if self.preserve_tail > 0 else ''

        return (
            target_text[: self.preserve_head]
            + self.replace_mark * (len(target_text) - self.preserve_head - self.preserve_tail)
            + tail_text
        )  # noqa
