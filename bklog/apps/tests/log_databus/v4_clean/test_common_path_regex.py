# -*- coding: utf-8 -*-
"""
组件测试：path regex 提取
4 ETL 类型 × path regex 配置
"""
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    find_rules_by_type,
    get_output_ids,
    assert_rule_exists,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_path_regex_config,
)
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import SINGLE_STRING_FIELD, DELIMITER_FIELDS
from apps.tests.log_databus.v4_clean.testdata.etl_params_fixtures import (
    EMPTY_PARAMS,
    JSON_NO_RETAIN,
    DELIMITER_BASIC,
    REGEXP_BASIC,
)


def _get_etl_params(etl_name):
    """根据 ETL 类型返回所需的最小 etl_params"""
    if etl_name == "text":
        return EMPTY_PARAMS
    elif etl_name == "json":
        return JSON_NO_RETAIN
    elif etl_name == "delimiter":
        return DELIMITER_BASIC
    elif etl_name == "regexp":
        return REGEXP_BASIC
    return EMPTY_PARAMS


def _get_fields(etl_name):
    """根据 ETL 类型返回所需的字段列表"""
    if etl_name == "delimiter":
        return DELIMITER_FIELDS
    elif etl_name == "text":
        return []
    return SINGLE_STRING_FIELD


class TestCommonPathRegex(TestCase):
    """测试 path regex 在所有 ETL 类型的 build_log_v4_data_link 中的行为"""

    PATH_REGEXP = r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log"

    def test_path_regex_generates_rules(self):
        """配置 path regex 时应生成 path get + regex + assign 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_path_regex_config(self.PATH_REGEXP)
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]

                # path get 规则（注意：built-in 中也有 output_id="path" 的 assign 规则）
                path_get_rules = [r for r in find_rules_by_output(rules, "path")
                                  if r["operator"]["type"] == "get"]
                self.assertEqual(len(path_get_rules), 1)
                self.assertEqual(path_get_rules[0]["input_id"], "json_data")

                # regex 规则
                regex_rules = find_rules_by_output(rules, "bk_separator_object_path")
                self.assertEqual(len(regex_rules), 1)
                self.assertEqual(regex_rules[0]["operator"]["type"], "regex")
                self.assertEqual(regex_rules[0]["operator"]["regex"], self.PATH_REGEXP)

                # 提取的命名组字段
                output_ids = get_output_ids(rules)
                self.assertIn("app_name", output_ids)
                self.assertIn("log_type", output_ids)

    def test_no_path_regex_no_path_rules(self):
        """未配置 path regex 时不应生成 path 相关规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]
                assert_rule_absent(self, rules, "bk_separator_object_path")

    def test_empty_separator_regexp_no_path_rules(self):
        """separator_regexp 为空字符串时不应生成 path 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                config["option"]["separator_configs"] = [{"separator_regexp": ""}]
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]
                assert_rule_absent(self, rules, "bk_separator_object_path")

    def test_path_field_assigns_have_correct_types(self):
        """path 提取的字段 assign 规则应有正确的 output_type"""
        storage = ALL_ETL_CLASSES[1][1]()  # JSON
        config = make_path_regex_config(self.PATH_REGEXP)
        result = storage.build_log_v4_data_link(SINGLE_STRING_FIELD, JSON_NO_RETAIN, config)
        rules = result["clean_rules"]
        for field_name in ["app_name", "log_type"]:
            matched = find_rules_by_output(rules, field_name)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["operator"]["output_type"], "string")
            self.assertEqual(matched[0]["input_id"], "bk_separator_object_path")
