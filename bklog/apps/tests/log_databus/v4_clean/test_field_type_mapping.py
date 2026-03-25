# -*- coding: utf-8 -*-
"""
纯函数单元测试：EtlStorage._get_output_type
覆盖所有 9 种类型映射 + unknown 回退。
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.base import EtlStorage


class TestGetOutputType(TestCase):
    """测试 _get_output_type 类型映射"""

    TYPE_CASES = [
        ("string", "string"),
        ("int", "long"),
        ("integer", "long"),
        ("long", "long"),
        ("float", "double"),
        ("double", "double"),
        ("object", "dict"),
        ("bool", "boolean"),
        ("boolean", "boolean"),
    ]

    def test_all_known_types(self):
        """subTest 覆盖所有已定义的字段类型"""
        for field_type, expected in self.TYPE_CASES:
            with self.subTest(field_type=field_type):
                self.assertEqual(EtlStorage._get_output_type(field_type), expected)

    def test_unknown_type_fallback(self):
        """未知类型应回退为 string"""
        self.assertEqual(EtlStorage._get_output_type("unknown_type"), "string")

    def test_empty_string_fallback(self):
        """空字符串应回退为 string"""
        self.assertEqual(EtlStorage._get_output_type(""), "string")
