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
from django.test import TestCase
from apps.log_desensitize.handlers.desensitize_operator.mask_shield import DesensitizeMaskShield
from apps.log_desensitize.handlers.desensitize_operator.text_replace import DesensitizeTextReplace


class TestDesensitizeOperator(TestCase):

    def test_mask_shield_transform(self):
        # 掩码屏蔽场景测试一 前3后2不屏蔽
        preserve_head = 3
        preserve_tail = 2
        replace_mark = "*"
        target_text_mask_shield = "13234345678"
        mask_shield_result = "132******78"
        self.assertEqual(
            DesensitizeMaskShield(
                preserve_head=preserve_head,
                preserve_tail=preserve_tail,
                replace_mark=replace_mark
            ).transform(target_text_mask_shield), mask_shield_result)

        # 掩码屏蔽场景测试二 全屏蔽
        preserve_head = 0
        preserve_tail = 0
        replace_mark = "*"
        target_text_mask_shield = "13234345678"
        mask_shield_result = "***********"
        self.assertEqual(
            DesensitizeMaskShield(
                preserve_head=preserve_head,
                preserve_tail=preserve_tail,
                replace_mark=replace_mark
            ).transform(target_text_mask_shield), mask_shield_result)

        # 掩码屏蔽场景测试三 全不屏蔽
        preserve_head = 5
        preserve_tail = 7
        replace_mark = "*"
        target_text_mask_shield = "13234345678"
        mask_shield_result = "13234345678"
        self.assertEqual(
            DesensitizeMaskShield(
                preserve_head=preserve_head,
                preserve_tail=preserve_tail,
                replace_mark=replace_mark
            ).transform(target_text_mask_shield), mask_shield_result)

        # 掩码屏蔽场景测试四 保护后三位
        preserve_head = 0
        preserve_tail = 3
        replace_mark = "*"
        target_text_mask_shield = "13234345678"
        mask_shield_result = "********678"
        self.assertEqual(
            DesensitizeMaskShield(
                preserve_head=preserve_head,
                preserve_tail=preserve_tail,
                replace_mark=replace_mark
            ).transform(target_text_mask_shield), mask_shield_result)

        # 掩码屏蔽场景测试五 保护前三位
        preserve_head = 3
        preserve_tail = 0
        replace_mark = "*"
        target_text_mask_shield = "13234345678"
        mask_shield_result = "132********"
        self.assertEqual(
            DesensitizeMaskShield(
                preserve_head=preserve_head,
                preserve_tail=preserve_tail,
                replace_mark=replace_mark
            ).transform(target_text_mask_shield), mask_shield_result)

    def test_text_replace_transform(self):
        # 文本替换算子场景一
        template_string = "abc${partNum}defg"
        context = {"partNum": "3434"}
        target_text_text_replace = "13234345678"
        text_replace_result = "abc3434defg"

        self.assertEqual(
            DesensitizeTextReplace(
                template_string=template_string
            ).transform(target_text_text_replace, context=context), text_replace_result)

        # 文本替换算子场景二
        template_string = "abc${partNum}defg"
        target_text_text_replace = "13234345678"
        text_replace_result = "abcdefg"

        self.assertEqual(
            DesensitizeTextReplace(
                template_string=template_string
            ).transform(target_text_text_replace), text_replace_result)
