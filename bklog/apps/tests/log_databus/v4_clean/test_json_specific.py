# -*- coding: utf-8 -*-
"""
JSON 特有分支全覆盖测试
retain_original_text, enable_retain_content, retain_extra_json, alias, delete, object/bool 类型
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.tests.log_databus.v4_clean.helpers import (
    find_rules_by_output,
    find_rules_by_input,
    find_rules_by_type,
    get_output_ids,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field


class TestJsonRetainOriginalText(TestCase):
    """retain_original_text 分支"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_retain_original_text_true(self):
        """retain_original_text=True 时应生成 log assign 规则"""
        etl_params = {"retain_original_text": True}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)
        self.assertEqual(log_rules[0]["input_id"], "iter_item")
        self.assertEqual(log_rules[0]["operator"]["key_index"], "data")

    def test_retain_original_text_false_no_retain_content(self):
        """retain_original_text=False 且 enable_retain_content 未设置时不应生成 log 规则"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "log")


class TestJsonEnableRetainContent(TestCase):
    """enable_retain_content 分支"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_enable_retain_content_generates_log(self):
        """enable_retain_content=True 时应生成 log assign 规则"""
        etl_params = {"retain_original_text": False, "enable_retain_content": True}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        log_rules = find_rules_by_output(rules, "log")
        self.assertEqual(len(log_rules), 1)

    def test_enable_retain_content_json_de_null_strategy(self):
        """enable_retain_content=True 时 bk_separator_object 的 json_de 应使用 null 策略"""
        etl_params = {"enable_retain_content": True}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)
        self.assertEqual(sep_rules[0]["operator"]["error_strategy"], "null")

    def test_no_enable_retain_content_json_de_drop_strategy(self):
        """enable_retain_content 未设置时 json_de 应使用 drop 策略"""
        etl_params = {"retain_original_text": True}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        sep_rules = find_rules_by_output(rules, "bk_separator_object")
        self.assertEqual(len(sep_rules), 1)
        self.assertEqual(sep_rules[0]["operator"]["error_strategy"], "drop")


class TestJsonRetainExtraJson(TestCase):
    """retain_extra_json 分支"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_retain_extra_json_generates_ext_json(self):
        """retain_extra_json=True 时应生成 delete + __ext_json assign 规则"""
        etl_params = {"retain_original_text": False, "retain_extra_json": True}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]

        # delete 规则
        delete_rules = find_rules_by_type(rules, "delete")
        self.assertEqual(len(delete_rules), 1)
        self.assertEqual(delete_rules[0]["input_id"], "bk_separator_object")
        # 应排除 level 字段
        exclude_keys = delete_rules[0]["operator"]["key_index"]
        exclude_values = [k["value"] for k in exclude_keys]
        self.assertIn("level", exclude_values)

        # __ext_json assign 规则
        ext_rules = find_rules_by_output(rules, "__ext_json")
        self.assertEqual(len(ext_rules), 1)
        self.assertEqual(ext_rules[0]["operator"]["output_type"], "dict")

    def test_no_retain_extra_json_no_ext_json(self):
        """retain_extra_json=False 时不应生成 __ext_json"""
        etl_params = {"retain_original_text": False, "retain_extra_json": False}
        fields = [make_field("level")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "__ext_json")

    def test_extra_json_excludes_alias_fields(self):
        """有 alias 的字段应使用 alias 作为 exclude key"""
        etl_params = {"retain_original_text": False, "retain_extra_json": True}
        fields = [make_field("src_ip", alias="client_ip")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        delete_rules = find_rules_by_type(rules, "delete")
        exclude_values = [k["value"] for k in delete_rules[0]["operator"]["key_index"]]
        self.assertIn("client_ip", exclude_values)
        self.assertNotIn("src_ip", exclude_values)

    def test_extra_json_excludes_skip_deleted_fields(self):
        """is_delete=True 的字段不应出现在 exclude keys 中"""
        etl_params = {"retain_original_text": False, "retain_extra_json": True}
        fields = [make_field("level"), make_field("debug", is_delete=True)]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        delete_rules = find_rules_by_type(rules, "delete")
        exclude_values = [k["value"] for k in delete_rules[0]["operator"]["key_index"]]
        self.assertIn("level", exclude_values)
        self.assertNotIn("debug", exclude_values)


class TestJsonAliasAndDelete(TestCase):
    """alias_name 和 is_delete 分支"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_alias_field(self):
        """有 alias 的字段应使用 alias 作为 output_id 和 alias"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("src_ip", alias="client_ip")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        matched = find_rules_by_output(rules, "client_ip")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["operator"]["key_index"], "src_ip")
        self.assertEqual(matched[0]["operator"]["alias"], "client_ip")

    def test_deleted_field_not_in_rules(self):
        """is_delete=True 的字段不应生成 assign 规则"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("level"), make_field("debug", is_delete=True)]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        assert_rule_absent(self, rules, "debug")
        assert_rule_exists(self, rules, "level")


class TestJsonFieldTypes(TestCase):
    """object/bool 等字段类型"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_object_field_type(self):
        """object 类型字段 output_type 应为 dict"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("meta", "object")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        matched = find_rules_by_output(rules, "meta")
        self.assertEqual(matched[0]["operator"]["output_type"], "dict")

    def test_bool_field_type(self):
        """bool 类型字段 output_type 应为 boolean"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("active", "bool")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        matched = find_rules_by_output(rules, "active")
        self.assertEqual(matched[0]["operator"]["output_type"], "boolean")

    def test_int_field_type(self):
        """int 类型字段 output_type 应为 long"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("count", "int")]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        matched = find_rules_by_output(rules, "count")
        self.assertEqual(matched[0]["operator"]["output_type"], "long")


class TestJsonTimeField(TestCase):
    """时间字段相关测试"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_nanos_built_in_time_generates_nanos_rule(self):
        """built_in_config 中 nanos 格式的时间字段应生成 dtEventTimeStampNanos 规则"""
        from apps.tests.log_databus.v4_clean.testdata.built_in_configs import make_nanos_config
        etl_params = {"retain_original_text": False}
        fields = [make_field("level")]
        config = make_nanos_config("yyyy-MM-dd HH:mm:ss.SSSSSS")
        result = self.storage.build_log_v4_data_link(fields, etl_params, config)
        rules = result["clean_rules"]
        nanos_rules = find_rules_by_output(rules, "dtEventTimeStampNanos")
        self.assertEqual(len(nanos_rules), 1)
        self.assertEqual(nanos_rules[0]["input_id"], "bk_separator_object")

    def test_user_time_field_does_not_trigger_nanos(self):
        """用户 is_time 字段不在 build_log_v4_data_link 层触发 nanos（nanos 由 built_in_config 决定）"""
        etl_params = {"retain_original_text": False}
        fields = [
            make_field("log_time", is_time=True,
                       option={"time_zone": 8, "time_format": "yyyy-MM-dd HH:mm:ss.SSSSSS"}),
        ]
        config = get_fresh_config()  # 标准 built_in: yyyy-MM-dd HH:mm:ss (非 nanos)
        result = self.storage.build_log_v4_data_link(fields, etl_params, config)
        rules = result["clean_rules"]
        nanos_rules = find_rules_by_output(rules, "dtEventTimeStampNanos")
        self.assertEqual(len(nanos_rules), 0)


class TestJsonStructure(TestCase):
    """JSON 清洗的结构性断言"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_first_rule_is_json_de(self):
        """第一条规则应为 __raw_data → json_data 的 json_de"""
        result = self.storage.build_log_v4_data_link(
            [make_field("level")], {"retain_original_text": False}, get_fresh_config()
        )
        rules = result["clean_rules"]
        self.assertEqual(rules[0]["input_id"], "__raw_data")
        self.assertEqual(rules[0]["output_id"], "json_data")
        self.assertEqual(rules[0]["operator"]["type"], "json_de")

    def test_iter_pipeline(self):
        """应包含 items get → iter → iter_string get 管道"""
        result = self.storage.build_log_v4_data_link(
            [make_field("level")], {"retain_original_text": False}, get_fresh_config()
        )
        rules = result["clean_rules"]
        items_rules = find_rules_by_output(rules, "items")
        self.assertEqual(len(items_rules), 1)
        self.assertEqual(items_rules[0]["operator"]["type"], "get")

        iter_rules = find_rules_by_output(rules, "iter_item")
        self.assertEqual(len(iter_rules), 1)
        self.assertEqual(iter_rules[0]["operator"]["type"], "iter")

        iter_string_rules = find_rules_by_output(rules, "iter_string")
        self.assertEqual(len(iter_string_rules), 1)

    def test_user_field_assigns_from_separator_object(self):
        """用户字段 assign 规则的 input_id 应为 bk_separator_object"""
        fields = [make_field("level"), make_field("count", "int")]
        result = self.storage.build_log_v4_data_link(fields, {"retain_original_text": False}, get_fresh_config())
        rules = result["clean_rules"]
        for field_name in ["level", "count"]:
            matched = find_rules_by_output(rules, field_name)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["input_id"], "bk_separator_object")

    def test_es_storage_config(self):
        """es_storage_config 应包含 unique_field_list 和 timezone"""
        result = self.storage.build_log_v4_data_link([], {"retain_original_text": False}, get_fresh_config())
        es_config = result["es_storage_config"]
        self.assertIn("unique_field_list", es_config)
        self.assertEqual(es_config["timezone"], 8)
        self.assertIsNone(result["doris_storage_config"])
