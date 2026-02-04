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

from apps.log_databus.exceptions import (
    GrokCircularReferenceException,
    GrokPatternNotFoundException,
)
from apps.log_databus.handlers.grok import GrokHandler
from apps.log_databus.models import GrokInfo


# 测试常量
BK_BIZ_ID = 100


class TestGrokHandler(TestCase):
    def setUp(self):
        """测试前准备"""
        self.handler = GrokHandler(bk_biz_id=BK_BIZ_ID)
        # 清理测试数据
        GrokInfo.objects.filter(bk_biz_id=BK_BIZ_ID).delete()

    def tearDown(self):
        """测试后清理"""
        GrokInfo.objects.filter(bk_biz_id=BK_BIZ_ID).delete()

    def test_extract_pattern_references(self):
        """测试提取引用"""
        # 单个引用
        refs = GrokHandler._extract_pattern_references("%{WORD}")
        self.assertEqual(refs, {"WORD"})
        # 带字段名的引用
        refs = GrokHandler._extract_pattern_references("%{IP:client_ip}")
        self.assertEqual(refs, {"IP"})
        # 带类型转换的引用
        refs = GrokHandler._extract_pattern_references("%{NUMBER:port:int}")
        self.assertEqual(refs, {"NUMBER"})
        # 多个引用
        pattern = "%{WORD:method} %{URIPATHPARAM:request} %{NUMBER:status:int}"
        refs = GrokHandler._extract_pattern_references(pattern)
        self.assertEqual(refs, {"WORD", "URIPATHPARAM", "NUMBER"})

    def test_detect_circular_reference(self):
        """测试循环引用"""
        patterns_map = {
            "A": "%{B}",
            "B": "%{C}",
            "C": "simple pattern",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)
        self.assertEqual(cycle_path, [])

        # 引用自己
        patterns_map = {
            "A": "%{A}",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)
        self.assertEqual(cycle_path, ["A", "A"])

        # 循环引用
        patterns_map = {
            "A": "%{B}",
            "B": "%{C}",
            "C": "%{A}",  # C 引用 A，形成循环
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)
        self.assertIn("A", cycle_path)
        self.assertIn("B", cycle_path)
        self.assertIn("C", cycle_path)

        # 引用了不存在的模式
        patterns_map = {}
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("NONEXISTENT", patterns_map)
        self.assertFalse(has_cycle)

    def test_validate_references_exist(self):
        """测试引用的模式是否存在"""
        GrokInfo.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name="EXISTING_PATTERN",
            pattern=r"\d+",
            is_builtin=False,
        )
        self.handler.validate_references_exist("%{EXISTING_PATTERN:field}")
        # 引用不存在的模式
        with self.assertRaises(GrokPatternNotFoundException):
            self.handler.validate_references_exist("%{NONEXISTENT_PATTERN:field}")

    def test_validate_circular_reference(self):
        """测试校验循环引用"""
        GrokInfo.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name="BASE_PATTERN",
            pattern=r"\d+",
            is_builtin=False,
        )
        self.handler.validate_circular_reference("NEW_PATTERN", "%{BASE_PATTERN}")
        # 循环引用
        GrokInfo.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name="PATTERN_A",
            pattern="%{PATTERN_B}",
            is_builtin=False,
        )
        with self.assertRaises(GrokCircularReferenceException):
            self.handler.validate_circular_reference("PATTERN_B", "%{PATTERN_A}")

    def test_debug(self):
        """测试调试方法"""
        params = {
            "pattern": "%{NONEXISTENT_PATTERN:field}",
            "sample": "test",
        }
        with self.assertRaises(GrokPatternNotFoundException):
            self.handler.debug(params)

    def test_replace_custom_patterns(self):
        """测试替换自定义模式"""
        GrokInfo.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name="INNER_PATTERN",
            pattern=r"\d+",
            is_builtin=False,
        )
        GrokInfo.objects.create(
            bk_biz_id=BK_BIZ_ID,
            name="OUTER_PATTERN",
            pattern=r"prefix-%{INNER_PATTERN}-suffix",
            is_builtin=False,
        )
        # 正常替换
        pattern = "%{OUTER_PATTERN:value}"
        result = self.handler.replace_custom_patterns(pattern)
        self.assertIn(r"\d+", result)
        self.assertNotIn("INNER_PATTERN", result)

        # 引用不存在的模式
        pattern = "%{NONEXISTENT:field}"
        with self.assertRaises(GrokPatternNotFoundException):
            self.handler.replace_custom_patterns(pattern)
