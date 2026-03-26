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

import unittest

from apps.log_databus.handlers.grok.base import Grok, get_builtin_patterns
from apps.log_databus.handlers.grok.patterns import ALL_PATTERNS


class TestBuiltinGrokPatternMatch(unittest.TestCase):
    """测试所有内置 Grok 模式能否正确匹配其 sample 样例"""

    @classmethod
    def setUpClass(cls):
        """加载内置模式，构建名称到模式信息的映射"""
        super().setUpClass()
        cls.builtin_patterns = get_builtin_patterns()
        cls.all_pattern_info = ALL_PATTERNS

    def test_builtin_patterns_loaded(self):
        """测试内置模式是否成功加载"""
        self.assertGreater(len(self.builtin_patterns), 0, "内置模式不应为空")
        self.assertGreater(len(self.all_pattern_info), 0, "ALL_PATTERNS 不应为空")

    def test_all_patterns_have_required_fields(self):
        """测试所有内置模式都包含必要字段"""
        for p in self.all_pattern_info:
            self.assertIn("name", p, f"模式缺少 name 字段: {p}")
            self.assertIn("pattern", p, f"模式缺少 pattern 字段: {p}")

    def test_all_patterns_with_sample_can_match(self):
        """
        遍历所有内置模式，对有 sample 字段的模式进行匹配测试。
        使用 %{PATTERN_NAME:value} 形式构造 Grok 表达式，
        验证 sample 能被成功匹配并提取到 value 字段。
        """
        failed_patterns = []

        for pattern_info in self.all_pattern_info:
            name = pattern_info["name"]
            sample = pattern_info.get("sample")

            # 跳过没有 sample 的模式
            if not sample:
                continue

            grok_expr = f"%{{{name}:value}}"
            try:
                grok = Grok(grok_expr)
                result = grok.match(sample)
            except Exception as e:
                failed_patterns.append({"name": name, "sample": sample, "error": str(e)})
                continue

            if result is None:
                failed_patterns.append({"name": name, "sample": sample, "error": "匹配返回 None"})
            elif "value" not in result:
                failed_patterns.append({"name": name, "sample": sample, "error": f"结果中缺少 value 字段: {result}"})

        if failed_patterns:
            msg_lines = ["以下内置模式无法匹配其 sample:"]
            for fp in failed_patterns:
                msg_lines.append(f"  - {fp['name']}: sample={fp['sample']!r}, error={fp['error']}")
            self.fail("\n".join(msg_lines))

    def test_common_patterns_match_detail(self):
        """测试常用模式的匹配细节，验证提取的值是否正确"""
        test_cases = [
            # (模式名, sample, 期望提取的值)
            ("IP", "192.168.1.1", "192.168.1.1"),
            ("IP", "::1", "::1"),
            ("WORD", "hello", "hello"),
            ("INT", "-42", "-42"),
            ("NUMBER", "3.14", "3.14"),
            ("POSINT", "42", "42"),
            ("EMAILADDRESS", "user.name@example.com", "user.name@example.com"),
            ("USERNAME", "john.doe-01", "john.doe-01"),
            ("NOTSPACE", "no-spaces-here", "no-spaces-here"),
            ("BASE16NUM", "0x1A3F", "0x1A3F"),
        ]

        for pattern_name, sample, expected_value in test_cases:
            with self.subTest(pattern=pattern_name, sample=sample):
                grok = Grok(f"%{{{pattern_name}:value}}")
                result = grok.match(sample)
                self.assertIsNotNone(result, f"模式 {pattern_name} 无法匹配 sample: {sample!r}")
                self.assertEqual(
                    result.get("value"),
                    expected_value,
                    f"模式 {pattern_name} 匹配结果不符: 期望 {expected_value!r}, 实际 {result.get('value')!r}",
                )

    def test_type_conversion(self):
        """测试类型转换功能"""
        # int 类型转换
        grok = Grok("%{NUMBER:port:int}")
        result = grok.match("8080")
        self.assertIsNotNone(result)
        self.assertEqual(result["port"], 8080)
        self.assertIsInstance(result["port"], int)

        # float 类型转换
        grok = Grok("%{NUMBER:ratio:float}")
        result = grok.match("3.14")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["ratio"], 3.14)
        self.assertIsInstance(result["ratio"], float)

    def test_composite_pattern(self):
        """测试组合模式匹配"""
        grok = Grok("%{IP:client} %{WORD:method} %{URIPATHPARAM:request} %{NUMBER:status:int}")
        result = grok.match("192.168.1.1 GET /api/v1/users?page=1 200")
        self.assertIsNotNone(result)
        self.assertEqual(result["client"], "192.168.1.1")
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["request"], "/api/v1/users?page=1")
        self.assertEqual(result["status"], 200)

    def test_no_match_returns_none(self):
        """测试不匹配时返回 None"""
        grok = Grok("%{IP:ip_address}")
        result = grok.match("not_an_ip_address")
        self.assertIsNone(result)

    def test_custom_patterns_override(self):
        """测试自定义模式可以覆盖或扩展内置模式"""
        custom = {"MY_STATUS": r"OK|FAIL|WARN"}
        grok = Grok("%{MY_STATUS:status}", custom_patterns=custom)

        result = grok.match("OK")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "OK")

        result = grok.match("FAIL")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "FAIL")

        result = grok.match("UNKNOWN")
        self.assertIsNone(result)

    def test_nested_custom_patterns(self):
        """测试嵌套自定义模式"""
        custom = {
            "INNER_NUM": r"\d{3}",
            "OUTER_CODE": r"CODE-%{INNER_NUM}",
        }
        grok = Grok("%{OUTER_CODE:code}", custom_patterns=custom)
        result = grok.match("CODE-123")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "CODE-123")

    def test_pattern_without_field_name(self):
        """测试不带字段名的模式（非捕获组）"""
        grok = Grok("%{WORD} %{NUMBER:num}")
        result = grok.match("hello 42")
        self.assertIsNotNone(result)
        # WORD 没有字段名，不应出现在结果中
        self.assertNotIn("WORD", result)
        self.assertEqual(result["num"], "42")

    def test_unknown_pattern_raises_error(self):
        """测试引用不存在的模式时抛出 KeyError"""
        with self.assertRaises(KeyError):
            Grok("%{NONEXISTENT_PATTERN:value}")


if __name__ == "__main__":
    unittest.main()
