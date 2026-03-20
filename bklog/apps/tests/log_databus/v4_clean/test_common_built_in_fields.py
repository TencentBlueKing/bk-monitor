# -*- coding: utf-8 -*-
"""
组件测试：_build_built_in_fields_v4
4 ETL 类型 × 标准配置 + 无时间字段边界
"""
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    get_output_ids,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_no_time_field_config,
    make_empty_fields_config,
)


class TestCommonBuiltInFields(TestCase):
    """测试 _build_built_in_fields_v4 在所有 ETL 类型下的行为"""

    # 标准配置下应生成的内置字段 output_id（排除 log 和 iterationIndex）
    EXPECTED_BUILT_IN_IDS = {"bk_host_id", "__ext", "cloudId", "serverIp", "path", "gseIndex", "dtEventTimeStamp"}

    def test_standard_config_all_etl_types(self):
        """4 ETL 类型 × 标准配置：应生成 7 个内置字段规则（6 普通 + 1 时间）"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                rules = storage._build_built_in_fields_v4(config)

                output_ids = get_output_ids(rules)
                self.assertEqual(output_ids, self.EXPECTED_BUILT_IN_IDS,
                                 f"[{etl_name}] built-in output_ids mismatch")

    def test_all_rules_input_from_json_data(self):
        """所有内置字段规则的 input_id 应为 json_data"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                rules = storage._build_built_in_fields_v4(get_fresh_config())
                for rule in rules:
                    self.assertEqual(rule["input_id"], "json_data")

    def test_time_field_has_in_place_time_parsing(self):
        """dtEventTimeStamp 规则应包含 in_place_time_parsing"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                rules = storage._build_built_in_fields_v4(get_fresh_config())
                time_rules = find_rules_by_output(rules, "dtEventTimeStamp")
                self.assertEqual(len(time_rules), 1)
                itp = time_rules[0]["operator"]["in_place_time_parsing"]
                self.assertIsNotNone(itp)
                self.assertEqual(itp["to"], "millis")
                self.assertEqual(itp["from"]["format"], "%Y-%m-%d %H:%M:%S")

    def test_non_time_fields_no_time_parsing(self):
        """非时间字段不应有 in_place_time_parsing"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                rules = storage._build_built_in_fields_v4(get_fresh_config())
                for rule in rules:
                    if rule["output_id"] != "dtEventTimeStamp":
                        self.assertIsNone(rule["operator"]["in_place_time_parsing"],
                                          f"[{etl_name}] {rule['output_id']} should not have time parsing")

    def test_field_output_types(self):
        """验证各内置字段的 output_type 映射"""
        expected_types = {
            "bk_host_id": "double",   # field_type=float → double
            "__ext": "dict",           # field_type=object → dict
            "cloudId": "double",       # field_type=float → double
            "serverIp": "string",      # field_type=string → string
            "path": "string",          # field_type=string → string
            "gseIndex": "double",      # field_type=float → double
        }
        storage = ALL_ETL_CLASSES[0][1]()
        rules = storage._build_built_in_fields_v4(get_fresh_config())
        for rule in rules:
            oid = rule["output_id"]
            if oid in expected_types:
                self.assertEqual(rule["operator"]["output_type"], expected_types[oid],
                                 f"output_type mismatch for {oid}")

    def test_no_time_field_config(self):
        """无 time_field 配置时不应报错，且不生成时间规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_no_time_field_config()
                rules = storage._build_built_in_fields_v4(config)
                assert_rule_absent(self, rules, "dtEventTimeStamp")

    def test_empty_fields_config(self):
        """fields 为空列表时仅生成时间字段规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_empty_fields_config()
                rules = storage._build_built_in_fields_v4(config)
                output_ids = get_output_ids(rules)
                self.assertEqual(output_ids, {"dtEventTimeStamp"})
