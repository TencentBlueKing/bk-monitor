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

    def test_doris_nanos_rule_uses_flat_time_format(self):
        """
        doris 同样产出 dtEventTimeStampNanos 规则，但用扁平 time_format 承载。

        to 是 in_place_time_parsing 的专有键，doris 的扁平结构只认 format/zone，
        带上 to 会被 bkbase 判为非法。
        """
        for nanos_fmt in NANOS_FORMATS:
            for etl_name, etl_cls in ALL_ETL_CLASSES:
                with self.subTest(format=nanos_fmt, etl=etl_name):
                    storage = etl_cls()
                    config = make_nanos_config(nanos_fmt)
                    storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)
                    rules = storage._build_nanos_time_field_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)

                    self.assertEqual(len(rules), 1, f"[{etl_name}/{nanos_fmt}] should generate 1 nanos rule")
                    operator = rules[0]["operator"]
                    self.assertEqual(rules[0]["output_id"], "dtEventTimeStampNanos")
                    self.assertEqual(operator["output_type"], "string")
                    self.assertIsNone(operator["is_time_field"])
                    self.assertIsNone(operator["in_place_time_parsing"])
                    self.assertEqual(set(operator["time_format"]), {"format", "zone"},
                                     f"[{etl_name}/{nanos_fmt}] doris time_format 只能有 format/zone")

    def test_doris_nanos_rule_matches_verified_payload(self):
        """
        与 bkop 采集项 3748 实测下发通过的 clean_rules 逐键对齐。

        该形态已验证：数据正常入库，dtEventTimeStampNanos 保留完整微秒，
        经别名查 dtEventTimeStamp 与直查物理列均能命中。
        """
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("YYYY-MM-DDTHH:mm:ss.SSSSSSZ")
                storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)
                rules = storage._build_nanos_time_field_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)

                operator = rules[0]["operator"]
                self.assertEqual(operator["alias"], "dtEventTimeStampNanos")
                self.assertEqual(operator["type"], "assign")
                # 映射表 zone=0 被时间字段配置的 time_zone=8 覆盖
                self.assertEqual(
                    operator["time_format"], {"format": "%Y-%m-%dT%H:%M:%S.%6fZ", "zone": 8}
                )
                self.assertEqual(
                    operator["time_fallback"],
                    {
                        "fallback_fields": [
                            {"field": "utctime", "time_format": {"format": "%Y-%m-%d %H:%M:%S", "zone": 0}}
                        ],
                        "now_if_parse_failed": True,
                    },
                )

    def test_doris_time_field_rule_carries_nanos_format(self):
        """doris 的时间字段规则用扁平 time_format 承载纳秒格式，并以 is_time_field 声明时间字段"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("yyyy-MM-dd HH:mm:ss.SSSSSS")
                rules = storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)

                # dtEventTimeStamp 由 bkbase 依据 is_time_field 的规则自动生成，清洗侧不显式声明；
                # 显式声明会被 bkbase 判为保留字段冲突而整体拒绝
                assert_rule_absent(self, rules, "dtEventTimeStamp")

                time_rules = find_rules_by_output(rules, "time")
                self.assertEqual(len(time_rules), 1, f"[{etl_name}] expect exactly one time rule")
                operator = time_rules[0]["operator"]
                self.assertTrue(operator["is_time_field"])
                self.assertEqual(operator["output_type"], "string")
                self.assertIsNone(operator["in_place_time_parsing"])
                # 该 config 的 time_field 无 real_path，时间取采集器上报的 utctime，
                # 本就是 UTC，不套用用户配置的 time_zone
                self.assertEqual(operator["time_format"], {"format": "%Y-%m-%d %H:%M:%S.%6f", "zone": 0})

    def test_doris_user_time_field_rule_matches_verified_payload(self):
        """
        用户自定义时间字段场景下，time 规则与 bkop 采集项 3748 实测通过的形态一致。

        real_path 表示时间来自用户指定字段而非采集器 utctime，此时必须套用用户配置的
        time_zone，否则日志正文的本地时间会被当成 UTC，整体偏移 8 小时。
        """
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_nanos_config("YYYY-MM-DDTHH:mm:ss.SSSSSSZ")
                config["time_field"]["option"]["real_path"] = "bk_separator_object.log_time"
                storage._build_built_in_fields_v4(config, storage_cluster_type=DORIS_CLUSTER_TYPE)
                rules = storage._build_user_dt_event_time_field_v4(
                    config, storage_cluster_type=DORIS_CLUSTER_TYPE
                )

                # dtEventTimeStamp 由 bkbase 依据 is_time_field 自动生成，doris 侧不显式声明
                assert_rule_absent(self, rules, "dtEventTimeStamp")

                time_rules = find_rules_by_output(rules, "time")
                self.assertEqual(len(time_rules), 1, f"[{etl_name}] expect exactly one time rule")
                operator = time_rules[0]["operator"]
                self.assertTrue(operator["is_time_field"])
                self.assertEqual(operator["output_type"], "string")
                self.assertIsNone(operator["in_place_time_parsing"])
                self.assertEqual(
                    operator["time_format"], {"format": "%Y-%m-%dT%H:%M:%S.%6fZ", "zone": 8}
                )

    def test_result_table_declares_nanos_field_for_both_storages(self):
        """
        ES 与 doris 都声明 dtEventTimeStampNanos 字段。

        doris 上 dtEventTimeStamp 是 long 列、按 millis 截断存不住亚秒，
        nanos 字段落成 string 列原样保留微秒，是微秒精度的唯一载体。
        """
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
                self.assertIn(
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
