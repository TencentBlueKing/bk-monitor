"""
错误/边界用例测试 (E1-E10)
"""

from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    find_rules_by_input,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    build_test_field_list,
    get_fresh_config,
    make_no_time_field_config,
    make_no_iteration_index_config,
    make_empty_fields_config,
)
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field


class TestE1EmptyFieldsJson(TestCase):
    """E1: JSON 空 fields — 仅内置字段，无用户 assign"""

    def test_empty_fields(self):
        storage = BkLogJsonEtlStorage()
        config = get_fresh_config()
        result = storage.build_log_v4_data_link(
            [], {"retain_original_text": False}, config, build_test_field_list([], config)
        )
        rules = result["clean_rules"]
        user_assigns = [
            r for r in find_rules_by_input(rules, "bk_separator_object") if r["operator"]["type"] == "assign"
        ]
        self.assertEqual(len(user_assigns), 0, "Empty fields should produce no user assigns")
        # 但 bk_separator_object 的 json_de 本身应存在
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)


class TestE2EmptyFieldsDelimiter(TestCase):
    """E2: Delimiter 空 fields — 仅内置 + split_str，无字段 assign"""

    def test_empty_fields(self):
        storage = BkLogDelimiterEtlStorage()
        config = get_fresh_config()
        result = storage.build_log_v4_data_link(
            [], {"separator": "|", "retain_original_text": True}, config, build_test_field_list([], config)
        )
        rules = result["clean_rules"]
        user_assigns = [
            r for r in find_rules_by_input(rules, "bk_separator_object") if r["operator"]["type"] == "assign"
        ]
        self.assertEqual(len(user_assigns), 0)
        # split_str 规则应存在
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)
        self.assertEqual(sep_rules[0]["operator"]["type"], "split_str")


class TestE3NoTimeField(TestCase):
    """E3: 无 time_field — 不报错，无时间规则"""

    def test_no_time_field(self):
        storage = BkLogJsonEtlStorage()
        config = make_no_time_field_config()
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "dtEventTimeStamp")
        assert_rule_absent(self, rules, "dtEventTimeStampNanos")


class TestE4UnknownTimeFormat(TestCase):
    """E4: 未知时间格式 — 回退默认"""

    def test_unknown_format_fallback(self):
        storage = BkLogJsonEtlStorage()
        config = get_fresh_config()
        config["time_field"]["option"]["time_format"] = "xyz_unknown"
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        time_rules = find_rules_by_output(rules, "dtEventTimeStamp")
        self.assertEqual(len(time_rules), 1)
        itp = time_rules[0]["operator"]["in_place_time_parsing"]
        self.assertEqual(itp["from"]["format"], "%Y-%m-%d %H:%M:%S")


class TestE5EmptySeparatorConfigs(TestCase):
    """E5: separator_configs=[] — 无 path 规则"""

    def test_empty_separator_configs(self):
        storage = BkLogJsonEtlStorage()
        config = get_fresh_config()
        config["option"]["separator_configs"] = []
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        # 不应有 path get 规则（注意 built-in 中有 output_id="path" 的 assign 规则）
        path_get_rules = [r for r in find_rules_by_output(rules, "path") if r["operator"]["type"] == "get"]
        self.assertEqual(len(path_get_rules), 0)
        assert_rule_absent(self, rules, "bk_separator_object_path")


class TestE6EmptySeparatorRegexp(TestCase):
    """E6: separator_regexp="" — 无 path 规则"""

    def test_empty_regexp(self):
        storage = BkLogJsonEtlStorage()
        config = get_fresh_config()
        config["option"]["separator_configs"] = [{"separator_regexp": ""}]
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "bk_separator_object_path")


class TestE7AllFieldsDeleted(TestCase):
    """E7: 全部 is_delete=True — 无用户字段 assign"""

    def test_all_deleted(self):
        storage = BkLogJsonEtlStorage()
        fields = [make_field("debug", is_delete=True), make_field("trace", is_delete=True)]
        config = get_fresh_config()
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        user_assigns = [
            r for r in find_rules_by_input(rules, "bk_separator_object") if r["operator"]["type"] == "assign"
        ]
        self.assertEqual(len(user_assigns), 0)


class TestE8NoFieldIndexDelimiter(TestCase):
    """E8: delimiter 无 field_index — 跳过该字段"""

    def test_no_field_index(self):
        storage = BkLogDelimiterEtlStorage()
        fields = [
            make_field("ip", field_index=1),
            make_field("no_index"),  # 无 field_index
        ]
        config = get_fresh_config()
        result = storage.build_log_v4_data_link(
            fields, {"separator": "|", "retain_original_text": True}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        # ip 应存在
        ip_rules = find_rules_by_output(rules, "ip")
        self.assertEqual(len(ip_rules), 1)
        # no_index 应被跳过
        no_idx_rules = find_rules_by_output(rules, "no_index")
        self.assertEqual(len(no_idx_rules), 0)


class TestE9IterationIndexFlatFieldFalse(TestCase):
    """E9: iterationIndex flat_field=False — 不生成 iterationIndex 规则"""

    def test_no_iteration_index(self):
        storage = BkLogJsonEtlStorage()
        config = make_no_iteration_index_config()
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        # iter_item 中不应有 iterationIndex
        iter_assigns = [r for r in find_rules_by_input(rules, "iter_item") if r["output_id"] == "iterationIndex"]
        self.assertEqual(len(iter_assigns), 0)


class TestE10EmptyBuiltInFields(TestCase):
    """E10: built_in_config fields=[] — 仅时间字段规则"""

    def test_empty_built_in_fields(self):
        storage = BkLogJsonEtlStorage()
        config = make_empty_fields_config()
        fields = [make_field("level")]
        result = storage.build_log_v4_data_link(
            fields, {"retain_original_text": False}, config, build_test_field_list(fields, config)
        )
        rules = result["clean_rules"]
        # dtEventTimeStamp 应存在
        time_rules = find_rules_by_output(rules, "dtEventTimeStamp")
        self.assertEqual(len(time_rules), 1)
        # 普通内置字段不应存在
        assert_rule_absent(self, rules, "bk_host_id")
        assert_rule_absent(self, rules, "cloudId")
