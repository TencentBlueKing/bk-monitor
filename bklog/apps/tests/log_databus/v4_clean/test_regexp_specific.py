# -*- coding: utf-8 -*-
"""
正则特有分支测试
regex operator, named group mapping
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    find_rules_by_type,
    get_output_ids,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field


class TestRegexpRegexOperator(TestCase):
    """regex 规则"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_regex_rule_generated(self):
        """应生成 iter_string → bk_separator_object 的 regex 规则"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)\s+(?P<method>\w+)",
            "retain_original_text": True,
        }
        fields = [make_field("ip"), make_field("method")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)
        self.assertEqual(sep_rules[0]["operator"]["type"], "regex")
        self.assertEqual(sep_rules[0]["operator"]["regex"], etl_params["separator_regexp"])
        self.assertEqual(sep_rules[0]["input_id"], "iter_string")


class TestRegexpNamedGroups(TestCase):
    """命名组字段映射"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_field_mapping(self):
        """字段应从 bk_separator_object 提取，key_index=field_name"""
        etl_params = {
            "separator_regexp": r"(?P<request_ip>[\d\.]+)\s+-\s+-\s+\[(?P<request_time>[^\]]+)\]\s+\"(?P<method>\w+)",
            "retain_original_text": True,
        }
        fields = [
            make_field("request_ip"),
            make_field("request_time"),
            make_field("method"),
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]

        for field_name in ["request_ip", "request_time", "method"]:
            matched = find_rules_by_output(rules, field_name)
            self.assertEqual(len(matched), 1, f"{field_name} should have exactly 1 rule")
            self.assertEqual(matched[0]["input_id"], "bk_separator_object")
            self.assertEqual(matched[0]["operator"]["key_index"], field_name)
            self.assertEqual(matched[0]["operator"]["alias"], field_name)

    def test_deleted_field_not_mapped(self):
        """is_delete=True 字段不应生成 assign"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)\s+(?P<debug>\w+)",
            "retain_original_text": True,
        }
        fields = [make_field("ip"), make_field("debug", is_delete=True)]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        assert_rule_exists(self, rules, "ip")
        assert_rule_absent(self, rules, "debug")


class TestRegexpLogField(TestCase):
    """log 字段"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_log_always_generated(self):
        """正则类型 log assign 规则始终生成"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)",
            "retain_original_text": False,
        }
        fields = [make_field("ip")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")


class TestRegexpStructure(TestCase):
    """正则清洗结构性断言"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_pipeline_order(self):
        """验证管道顺序：json_de → built-in → items → iter → log → iter_string → regex → fields"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)",
            "retain_original_text": True,
        }
        fields = [make_field("ip")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]

        # json_de 是第一条
        self.assertEqual(rules[0]["operator"]["type"], "json_de")

        # 找到 regex 规则在 rules 中的位置
        regex_idx = next(i for i, r in enumerate(rules) if r.get("operator", {}).get("type") == "regex"
                         and r["output_id"] == "bk_separator_object")
        # regex 之后应有 ip assign
        ip_idx = next(i for i, r in enumerate(rules) if r["output_id"] == "ip")
        self.assertGreater(ip_idx, regex_idx)
