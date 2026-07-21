"""
正则特有分支测试
regex operator, named group mapping
"""

from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import build_test_field_list, get_fresh_config
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
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
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
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
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
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        assert_rule_exists(self, rules, "ip")
        assert_rule_absent(self, rules, "debug")


class TestRegexpLogField(TestCase):
    """log 字段按 retain_original_text / enable_retain_content 条件输出，与 JSON 对齐"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_log_not_generated_when_discard_original_and_failure(self):
        """丢弃原文且未保留失败日志时，不应生成 log assign"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)",
            "retain_original_text": False,
        }
        fields = [make_field("ip")]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "log")
        assert_rule_exists(self, rules, "iter_string", operator_type="get")

    def test_log_generated_when_retain_original_text(self):
        """retain_original_text=True 时应生成 log assign"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)",
            "retain_original_text": True,
        }
        fields = [make_field("ip")]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")

    def test_log_generated_when_enable_retain_content(self):
        """enable_retain_content=True 时应生成 log assign"""
        etl_params = {
            "separator_regexp": r"(?P<ip>[\d\.]+)",
            "retain_original_text": False,
            "enable_retain_content": True,
        }
        fields = [make_field("ip")]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
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
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]

        # json_de 是第一条
        self.assertEqual(rules[0]["operator"]["type"], "json_de")

        # 找到 regex 规则在 rules 中的位置
        regex_idx = next(
            i
            for i, r in enumerate(rules)
            if r.get("operator", {}).get("type") == "regex" and r["output_id"] == "bk_separator_object"
        )
        # regex 之后应有 ip assign
        ip_idx = next(i for i, r in enumerate(rules) if r["output_id"] == "ip")
        self.assertGreater(ip_idx, regex_idx)
