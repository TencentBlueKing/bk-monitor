"""
分隔符特有分支测试
split_str, index mapping, 跳过索引
"""

from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import build_test_field_list, get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field


class TestDelimiterSplitStr(TestCase):
    """split_str 规则"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_split_str_rule_generated(self):
        """应生成 iter_string → bk_separator_object 的 split_str 规则"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)
        self.assertEqual(sep_rules[0]["operator"]["type"], "split_str")
        self.assertEqual(sep_rules[0]["operator"]["delimiter"], "|")
        self.assertIsNone(sep_rules[0]["operator"]["max_parts"])

    def test_comma_separator(self):
        """逗号分隔符"""
        etl_params = {"separator": ",", "retain_original_text": False}
        fields = [make_field("name", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(sep_rules[0]["operator"]["delimiter"], ",")


class TestDelimiterIndexMapping(TestCase):
    """字段 index 映射"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_field_index_mapping(self):
        """field_index 应转换为 0-based key_index"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [
            make_field("ip", field_index=1),
            make_field("method", field_index=2),
            make_field("cost", "double", field_index=3),
        ]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]

        ip_rules = find_rules_by_output(rules, "ip")
        self.assertEqual(ip_rules[0]["operator"]["key_index"], "0")
        method_rules = find_rules_by_output(rules, "method")
        self.assertEqual(method_rules[0]["operator"]["key_index"], "1")
        cost_rules = find_rules_by_output(rules, "cost")
        self.assertEqual(cost_rules[0]["operator"]["key_index"], "2")
        self.assertEqual(cost_rules[0]["operator"]["output_type"], "double")

    def test_skip_index(self):
        """跳过的索引不应生成规则"""
        etl_params = {"separator": ",", "retain_original_text": False}
        fields = [
            make_field("name", field_index=1),
            make_field("value", "int", field_index=5),
        ]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]

        name_rules = find_rules_by_output(rules, "name")
        self.assertEqual(name_rules[0]["operator"]["key_index"], "0")
        value_rules = find_rules_by_output(rules, "value")
        self.assertEqual(value_rules[0]["operator"]["key_index"], "4")

    def test_deleted_field_skipped(self):
        """is_delete=True 的字段不应生成 assign 规则"""
        etl_params = {"separator": ",", "retain_original_text": False}
        fields = [
            make_field("name", field_index=1),
            make_field("unused", field_index=3, is_delete=True),
            make_field("value", "int", field_index=5),
        ]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "unused")
        assert_rule_exists(self, rules, "name")
        assert_rule_exists(self, rules, "value")


class TestDelimiterLogField(TestCase):
    """log 字段按 retain_original_text / enable_retain_content 条件输出，与 JSON 对齐"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_log_not_generated_when_discard_original_and_failure(self):
        """丢弃原文且未保留失败日志时，不应生成 log assign"""
        etl_params = {"separator": "|", "retain_original_text": False}
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "log")
        # 切分链路仍需要 iter_string
        assert_rule_exists(self, rules, "iter_string", operator_type="get")

    def test_log_generated_when_retain_original_text(self):
        """retain_original_text=True 时应生成 log assign"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")

    def test_log_generated_when_enable_retain_content(self):
        """enable_retain_content=True 时应生成 log assign"""
        etl_params = {
            "separator": "|",
            "retain_original_text": False,
            "enable_retain_content": True,
        }
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")


class TestDelimiterStructure(TestCase):
    """分隔符清洗的结构性断言"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_first_rule_is_json_de(self):
        """第一条规则应为 json_de"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        self.assertEqual(rules[0]["operator"]["type"], "json_de")
        self.assertEqual(rules[0]["input_id"], "__raw_data")

    def test_user_assigns_from_separator_object(self):
        """用户字段从 bk_separator_object 提取"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [make_field("ip", field_index=1)]
        config = get_fresh_config()
        result = self.storage.build_log_v4_data_link(fields, etl_params, config, build_test_field_list(fields, config))
        rules = result["clean_rules"]
        ip_rules = find_rules_by_output(rules, "ip")
        self.assertEqual(ip_rules[0]["input_id"], "bk_separator_object")
