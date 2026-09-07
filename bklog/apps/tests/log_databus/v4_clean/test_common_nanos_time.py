# -*- coding: utf-8 -*-
"""
组件测试：_build_nanos_time_field_v4 + _build_built_in_fields_v4 nanos 相关
4 ETL × 5 nanos 格式 + 非 nanos 格式不生成
"""
import copy
from unittest import TestCase

from apps.log_databus.constants import DORIS_CLUSTER_TYPE
from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_nanos_config,
)
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field

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
                    self.assertIsNone(rule["operator"]["time_format"])
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

    def test_doris_generates_no_nanos_rule(self):
        """doris 不产出 dtEventTimeStampNanos 规则，纳秒精度由 dtEventTimeStamp 自己承载"""
        for nanos_fmt in NANOS_FORMATS:
            for etl_name, etl_cls in ALL_ETL_CLASSES:
                with self.subTest(format=nanos_fmt, etl=etl_name):
                    storage = etl_cls()
                    config = make_nanos_config(nanos_fmt)
                    storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)
                    rules = storage._build_nanos_time_field_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)
                    self.assertEqual(rules, [], f"[{etl_name}/{nanos_fmt}] doris should generate no nanos rule")

    def test_doris_time_field_rule_carries_nanos_format(self):
        """doris 的时间字段规则用扁平 time_format 承载纳秒格式，并以 is_time_field 声明时间字段"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("yyyy-MM-dd HH:mm:ss.SSSSSS")
                rules = storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)

                assert_rule_absent(self, rules, "dtEventTimeStampNanos")
                # dtEventTimeStamp 由 bkbase 依据 is_time_field 的规则自动生成，清洗侧不显式声明
                assert_rule_absent(self, rules, "dtEventTimeStamp")

                time_rules = find_rules_by_output(rules, "time")
                self.assertEqual(len(time_rules), 1, f"[{etl_name}] expect exactly one time rule")
                operator = time_rules[0]["operator"]
                self.assertTrue(operator["is_time_field"])
                self.assertEqual(operator["output_type"], "string")
                self.assertIsNone(operator["in_place_time_parsing"])
                self.assertEqual(operator["time_format"], {"format": "%Y-%m-%d %H:%M:%S.%6f", "zone": 0})

    def test_doris_result_table_declares_no_nanos_field(self):
        """doris 结果表不声明 dtEventTimeStampNanos 字段，ES 仍需声明"""
        time_field = make_field(
            "log_time",
            is_time=True,
            option={"time_zone": 8, "time_format": "yyyy-MM-dd HH:mm:ss.SSSSSS"},
        )
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                es_result = etl_cls().get_result_table_fields(
                    [copy.deepcopy(time_field)], {}, get_fresh_config()
                )
                self.assertIn("dtEventTimeStampNanos", [f["field_name"] for f in es_result["fields"]])

                doris_result = etl_cls().get_result_table_fields(
                    [copy.deepcopy(time_field)],
                    {},
                    get_fresh_config(),
                    storage_cluster_type=DORIS_CLUSTER_TYPE,
                )
                self.assertNotIn(
                    "dtEventTimeStampNanos", [f["field_name"] for f in doris_result["fields"]]
                )

    def test_nanos_key_index_matches_time_alias(self):
        """nanos 规则的 key_index 应为 time_field 的 alias_name"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("yyyy-MM-dd HH:mm:ss.SSSSSS")
                storage._build_built_in_fields_v4(config)
                rules = storage._build_nanos_time_field_v4(config)
                self.assertEqual(rules[0]["operator"]["key_index"], "utctime")
