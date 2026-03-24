# -*- coding: utf-8 -*-
"""
直接入库特有分支测试
无字段映射、log 始终输出
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_text import BkLogTextEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    find_rules_by_input,
    get_output_ids,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config


class TestTextBasic(TestCase):
    """直接入库基础行为"""

    def setUp(self):
        self.storage = BkLogTextEtlStorage()

    def test_log_always_generated(self):
        """直接入库始终生成 log assign 规则"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")
        self.assertEqual(log_rules[0]["operator"]["key_index"], "data")
        self.assertEqual(log_rules[0]["operator"]["output_type"], "string")

    def test_no_separator_object(self):
        """直接入库不应有 bk_separator_object 规则"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "bk_separator_object")

    def test_no_user_field_assigns(self):
        """直接入库不应有从 bk_separator_object 提取的用户字段"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        rules = result["clean_rules"]
        user_assigns = find_rules_by_input(rules, "bk_separator_object")
        self.assertEqual(len(user_assigns), 0)


class TestTextStructure(TestCase):
    """直接入库结构性断言"""

    def setUp(self):
        self.storage = BkLogTextEtlStorage()

    def test_first_rule_is_json_de(self):
        """第一条规则应为 json_de"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        rules = result["clean_rules"]
        self.assertEqual(rules[0]["operator"]["type"], "json_de")
        self.assertEqual(rules[0]["input_id"], "__raw_data")
        self.assertEqual(rules[0]["output_id"], "json_data")

    def test_iter_pipeline(self):
        """应包含 items get → iter 管道"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        rules = result["clean_rules"]
        items_rules = find_rules_by_output(rules, "items")
        self.assertEqual(len(items_rules), 1)
        iter_rules = find_rules_by_output(rules, "iter_item")
        self.assertEqual(len(iter_rules), 1)

    def test_es_storage_config(self):
        """应返回正确的 es_storage_config"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        self.assertIn("unique_field_list", result["es_storage_config"])
        self.assertEqual(result["es_storage_config"]["timezone"], 8)
        self.assertIsNone(result["doris_storage_config"])
