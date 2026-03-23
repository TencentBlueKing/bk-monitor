# -*- coding: utf-8 -*-
"""
组件测试：_build_nanos_time_field_v4 + _build_built_in_fields_v4 nanos 相关
4 ETL × 5 nanos 格式 + 非 nanos 格式不生成
"""
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_nanos_config,
)

# FieldDateFormatEnum 中 es_format == "strict_date_optional_time_nanos" 的 5 种格式
NANOS_FORMATS = [
    "yyyy-MM-dd HH:mm:ss.SSSSSS",
    "basic_date_time_micros",
    "YYYY-MM-DDTHH:mm:ss.SSSSSSZ",
    "strict_date_time_micros",
    "epoch_micros",
]

# 非 nanos 格式
NON_NANOS_FORMATS = [
    "yyyy-MM-dd HH:mm:ss",
    "epoch_millis",
    "epoch_second",
    "yyyy-MM-ddTHH:mm:ss.SSSZ",
]


class TestCommonNanosTime(TestCase):
    """测试 nanos 时间字段在所有 ETL 类型下的行为"""

    def test_nanos_format_generates_nanos_rule(self):
        """5 种 nanos 格式 × 4 ETL 类型应生成 dtEventTimeStampNanos 规则"""
        for nanos_fmt in NANOS_FORMATS:
            for etl_name, etl_cls in ALL_ETL_CLASSES:
                with self.subTest(format=nanos_fmt, etl=etl_name):
                    storage = etl_cls()
                    config = make_nanos_config(nanos_fmt)
                    # 先调用 _build_built_in_fields_v4 设置 _nanos_time_field
                    storage._build_built_in_fields_v4(config)
                    # 再调用 _build_nanos_time_field_v4
                    rules = storage._build_nanos_time_field_v4(config)
                    self.assertEqual(len(rules), 1, f"[{etl_name}/{nanos_fmt}] should generate 1 nanos rule")
                    rule = rules[0]
                    self.assertEqual(rule["output_id"], "dtEventTimeStampNanos")
                    self.assertEqual(rule["input_id"], "bk_separator_object")
                    self.assertEqual(rule["operator"]["output_type"], "string")
                    itp = rule["operator"]["in_place_time_parsing"]
                    self.assertIsNotNone(itp)
                    self.assertEqual(itp["to"], "strict_date_optional_time_nanos")

    def test_non_nanos_format_no_nanos_rule(self):
        """非 nanos 格式不应生成 dtEventTimeStampNanos 规则"""
        for fmt in NON_NANOS_FORMATS:
            for etl_name, etl_cls in ALL_ETL_CLASSES:
                with self.subTest(format=fmt, etl=etl_name):
                    storage = etl_cls()
                    config = make_nanos_config(fmt)
                    storage._build_built_in_fields_v4(config)
                    rules = storage._build_nanos_time_field_v4(config)
                    self.assertEqual(len(rules), 0,
                                     f"[{etl_name}/{fmt}] should NOT generate nanos rule")

    def test_nanos_key_index_matches_time_alias(self):
        """nanos 规则的 key_index 应为 time_field 的 alias_name"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("yyyy-MM-dd HH:mm:ss.SSSSSS")
                storage._build_built_in_fields_v4(config)
                rules = storage._build_nanos_time_field_v4(config)
                self.assertEqual(rules[0]["operator"]["key_index"], "utctime")
