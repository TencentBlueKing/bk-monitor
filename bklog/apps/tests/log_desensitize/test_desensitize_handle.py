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

from apps.log_desensitize.constants import DesensitizeOperator
from apps.log_desensitize.handlers.desensitize import DesensitizeHandler
from apps.log_desensitize.handlers.entity.desensitize_config_entity import DesensitizeConfigEntity


class TestDesensitizeOperator(TestCase):
    """
    脱敏工厂单元测试
    """

    def test_transform_text(self):
        entity_test1 = DesensitizeConfigEntity(
            operator=DesensitizeOperator.MASK_SHIELD.value,
            params={
                "preserve_head": 3,
                "preserve_tail": 3,
            }
        )
        text = "13234345678"
        desensitize_config_list = [entity_test1]

        self.assertEqual(
            DesensitizeHandler(
                desensitize_config_list=desensitize_config_list
            ).transform_text(text), "132*****678")

    def test_transform_dict(self):
        entity_param_1 = DesensitizeConfigEntity(
            field_name="test_field_1",
            operator=DesensitizeOperator.MASK_SHIELD.value,
            params={
                "preserve_head": 3,
                "preserve_tail": 3,
            }
        )
        entity_param_2 = DesensitizeConfigEntity(
            field_name="test_field_2",
            operator=DesensitizeOperator.TEXT_REPLACE.value,
            params={
                "template_string": "abc${partNum}defg",
            },
            match_pattern=r"\d{3}(?P<partNum>\d{4})\d{4}"
        )

        text = {"test_field_1": "13234345678", "test_field_2": "13234345678"}
        desensitize_config_list = [entity_param_1, entity_param_2]

        result = DesensitizeHandler(desensitize_config_list=desensitize_config_list).transform_dict(text)

        self.assertEqual(result.get("test_field_1"), "132*****678")
        self.assertEqual(result.get("test_field_2"), "abc3434defg")
