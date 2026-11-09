# -*- coding: utf-8 -*-
"""混挂索引组字段类型规范化纯函数的全覆盖测试。

覆盖类型判定、清洗规则、幂等性、补充映射表与原映射函数的隔离，
以及后端白名单与前端类型图标白名单的一致性。本文件不触碰数据库。
"""

from django.test import SimpleTestCase

from apps.log_search.constants import (
    DorisFieldTypeEnum,
    ES_FIELD_TYPES,
    MIXED_STORAGE_EXTRA_TYPE_MAP,
    MixedStorageFieldTypeNormalizer,
)


class TestDorisFieldTypeClassification(SimpleTestCase):
    """验证混挂索引组专用的类型判定与规范化纯函数。"""

    def test_is_sql_field_type_true_for_doris_types(self):
        """11 种 SQL 类型（含带长度与精度的写法）都被判定为需要规范化。"""
        test_cases = [
            "int",
            "bigint",
            "datetime",
            "varchar(32)",
            "varchar(512)",
            "char(10)",
            "string",
            "tinyint",
            "smallint",
            "variant",
            "char",
        ]
        self.assertEqual(len(test_cases), 11)
        for value in test_cases:
            with self.subTest(value=value):
                self.assertIs(MixedStorageFieldTypeNormalizer.is_sql_field_type(value), True)

    def test_clean_field_type_is_shared_and_stable(self):
        """清洗结果逐项精确可预期，复合类型按尖括号前缀判定。"""
        test_cases = [
            ("array<int>", "array"),
            ("Array(Int32)", "array"),
            ("decimal(10,2)", "decimal"),
            ("varchar(32)", "varchar"),
            (None, ""),
            ("  ", ""),
        ]
        self.assertEqual(len(test_cases), 6)
        for value, expected in test_cases:
            with self.subTest(value=value):
                self.assertEqual(MixedStorageFieldTypeNormalizer._clean_field_type(value), expected)
        self.assertIs(MixedStorageFieldTypeNormalizer.is_sql_field_type("array<int>"), True)

    def test_is_sql_field_type_false_for_es_types(self):
        """15 种页面已可识别的类型都不被改写。"""
        test_cases = [
            "date",
            "keyword",
            "long",
            "integer",
            "text",
            "object",
            "boolean",
            "float",
            "double",
            "date_nanos",
            "flattened",
            "conflict",
            "__virtual__",
            "any",
            "number",
        ]
        self.assertEqual(len(test_cases), 15)
        for value in test_cases:
            with self.subTest(value=value):
                self.assertIs(MixedStorageFieldTypeNormalizer.is_sql_field_type(value), False)

    def test_is_sql_field_type_false_for_empty_and_unknown(self):
        """空值、空白字符串与未知类型不触发规范化。"""
        test_cases = [None, "", "   ", "mystery(3)"]
        self.assertEqual(len(test_cases), 4)
        for value in test_cases:
            with self.subTest(value=value):
                self.assertIs(MixedStorageFieldTypeNormalizer.is_sql_field_type(value), False)

    def test_normalize_field_type_is_idempotent_for_es_types(self):
        """ES 原生类型原样返回，时间字段与 text 不被强制改写。"""
        test_cases = [
            {"field_name": "time", "field_type": "keyword"},
            {"field_name": "log", "field_type": "text"},
            {"field_name": "ts", "field_type": "date"},
            {"field_name": "n", "field_type": "long"},
        ]
        self.assertEqual(len(test_cases), 4)
        for field in test_cases:
            with self.subTest(field=field):
                self.assertEqual(
                    MixedStorageFieldTypeNormalizer.normalize_field_type(field),
                    field["field_type"],
                )

    def test_normalize_field_type_maps_all_declared_doris_types(self):
        """枚举中的全部 19 个类型按写死的期望表映射，带参数写法同样精确。"""
        expected = {
            "boolean": "boolean",
            "tinyint": "integer",
            "smallint": "integer",
            "int": "integer",
            "bigint": "long",
            "largeint": "long",
            "float": "float",
            "double": "double",
            "decimal": "double",
            "date": "date",
            "datetime": "date",
            "char": "keyword",
            "varchar": "keyword",
            "string": "keyword",
            "array": "object",
            "map": "object",
            "struct": "object",
            "json": "object",
            "variant": "object",
        }
        self.assertEqual(len(DorisFieldTypeEnum), 19)
        self.assertEqual(len(expected), 19)
        for item in DorisFieldTypeEnum:
            with self.subTest(value=item.value):
                self.assertEqual(
                    MixedStorageFieldTypeNormalizer.normalize_field_type({"field_type": item.value}),
                    expected[item.value],
                )
        self.assertEqual(
            MixedStorageFieldTypeNormalizer.normalize_field_type({"field_type": "varchar(32)"}),
            "keyword",
        )
        self.assertEqual(
            MixedStorageFieldTypeNormalizer.normalize_field_type({"field_type": "decimal(10,2)"}),
            "double",
        )

    def test_get_es_field_type_is_unchanged_for_extra_types(self):
        """补充映射表没有并入原生 Doris 与异步导出共用的映射函数。"""
        test_cases = ["largeint", "decimal", "array", "map", "struct", "json"]
        self.assertEqual(len(test_cases), 6)
        for value in test_cases:
            with self.subTest(value=value):
                self.assertEqual(DorisFieldTypeEnum.get_es_field_type({"field_type": value}), value)

    def test_get_es_field_type_keeps_original_special_rules(self):
        """原映射函数对特殊字段名、分词开关与 text 的处理保持不变。"""
        test_cases = [
            ({"field_name": "dtEventTimeStamp", "field_type": "bigint"}, "date"),
            ({"field_name": "dtEventTimeStampNanos", "field_type": "bigint"}, "date"),
            ({"field_type": "varchar(32)", "is_analyzed": True}, "text"),
            ({"field_type": "text"}, "keyword"),
        ]
        self.assertEqual(len(test_cases), 4)
        for field, expected in test_cases:
            with self.subTest(field=field):
                self.assertEqual(DorisFieldTypeEnum.get_es_field_type(field), expected)

    def test_normalize_field_type_skips_es_native_text(self):
        """新函数对 ES 原生 text 不做 text 到 keyword 的转换。"""
        test_cases = [
            {"field_type": "text"},
            {"field_name": "time", "field_type": "text"},
        ]
        self.assertEqual(len(test_cases), 2)
        for field in test_cases:
            with self.subTest(field=field):
                self.assertEqual(MixedStorageFieldTypeNormalizer.normalize_field_type(field), "text")

    def test_es_field_types_matches_frontend_whitelist(self):
        """后端白名单与前端字段类型图标映射的键集合严格相等。"""
        self.assertEqual(
            ES_FIELD_TYPES,
            frozenset({
                "any",
                "number",
                "integer",
                "double",
                "float",
                "keyword",
                "long",
                "text",
                "date",
                "date_nanos",
                "boolean",
                "conflict",
                "__virtual__",
                "object",
                "flattened",
            }),
        )

    def test_private_extra_map_does_not_leak(self):
        """补充映射表内容固定，且未并入原映射函数。"""
        self.assertEqual(
            MIXED_STORAGE_EXTRA_TYPE_MAP,
            {
                "largeint": "long",
                "decimal": "double",
                "array": "object",
                "map": "object",
                "struct": "object",
                "json": "object",
            },
        )
        self.assertEqual(DorisFieldTypeEnum.get_es_field_type({"field_type": "largeint"}), "largeint")
