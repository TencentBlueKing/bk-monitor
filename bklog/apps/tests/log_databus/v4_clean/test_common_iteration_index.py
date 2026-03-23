# -*- coding: utf-8 -*-
"""
组件测试：_build_iteration_index_field_v4
4 ETL × flat_field True/False
"""
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_no_iteration_index_config,
)


class TestCommonIterationIndex(TestCase):
    """测试 _build_iteration_index_field_v4 在所有 ETL 类型下的行为"""

    def test_flat_field_true_generates_rule(self):
        """flat_field=True 时应生成 iterationIndex 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                rules = storage._build_iteration_index_field_v4(get_fresh_config())
                self.assertEqual(len(rules), 1)
                rule = rules[0]
                self.assertEqual(rule["input_id"], "iter_item")
                self.assertEqual(rule["output_id"], "iterationIndex")
                self.assertEqual(rule["operator"]["type"], "assign")
                self.assertEqual(rule["operator"]["key_index"], "iterationindex")
                self.assertEqual(rule["operator"]["alias"], "iterationIndex")
                # es_type=integer → output_type=long
                self.assertEqual(rule["operator"]["output_type"], "long")

    def test_flat_field_false_no_rule(self):
        """flat_field=False 时不应生成 iterationIndex 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_no_iteration_index_config()
                rules = storage._build_iteration_index_field_v4(config)
                self.assertEqual(len(rules), 0)

    def test_no_iteration_index_field_in_config(self):
        """built_in_config.fields 中无 iterationIndex 字段时不生成规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                config["fields"] = [f for f in config["fields"] if f["field_name"] != "iterationIndex"]
                rules = storage._build_iteration_index_field_v4(config)
                self.assertEqual(len(rules), 0)
