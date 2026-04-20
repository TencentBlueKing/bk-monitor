# -*- coding: utf-8 -*-
"""
组件测试：path regex 提取
验证 path_regexp 从 etl_params 传入时（真实调用链），4 ETL 类型均正确生成规则
"""
import copy
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
    find_rules_by_output,
    get_output_ids,
    assert_rule_absent,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import SINGLE_STRING_FIELD, DELIMITER_FIELDS
from apps.tests.log_databus.v4_clean.testdata.etl_params_fixtures import (
    EMPTY_PARAMS,
    JSON_NO_RETAIN,
    DELIMITER_BASIC,
    REGEXP_BASIC,
)


def _get_etl_params(etl_name, path_regexp=""):
    """根据 ETL 类型返回 etl_params，可选注入 path_regexp"""
    base = {
        "text": EMPTY_PARAMS,
        "json": JSON_NO_RETAIN,
        "delimiter": DELIMITER_BASIC,
        "regexp": REGEXP_BASIC,
    }.get(etl_name, EMPTY_PARAMS)
    params = copy.deepcopy(base)
    if path_regexp:
        params["path_regexp"] = path_regexp
    return params


def _get_fields(etl_name):
    """根据 ETL 类型返回所需的字段列表"""
    if etl_name == "delimiter":
        return DELIMITER_FIELDS
    elif etl_name == "text":
        return []
    return SINGLE_STRING_FIELD


class TestCommonPathRegex(TestCase):
    """测试 path regex 从 etl_params["path_regexp"] 传入时在所有 ETL 类型中的行为"""

    PATH_REGEXP = r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log"

    def test_path_regex_generates_rules(self):
        """etl_params 含 path_regexp 时应生成 path get + regex + assign 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name, path_regexp=self.PATH_REGEXP)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]

                path_get_rules = [r for r in find_rules_by_output(rules, "path")
                                  if r["operator"]["type"] == "get"]
                self.assertEqual(len(path_get_rules), 1)
                self.assertEqual(path_get_rules[0]["input_id"], "json_data")

                regex_rules = find_rules_by_output(rules, "bk_separator_object_path")
                self.assertEqual(len(regex_rules), 1)
                self.assertEqual(regex_rules[0]["operator"]["type"], "regex")
                self.assertEqual(regex_rules[0]["operator"]["regex"], self.PATH_REGEXP)

                output_ids = get_output_ids(rules)
                self.assertIn("app_name", output_ids)
                self.assertIn("log_type", output_ids)

    def test_no_path_regex_no_path_rules(self):
        """etl_params 无 path_regexp 且 built_in_config 无 separator_configs 时不应生成规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]
                assert_rule_absent(self, rules, "bk_separator_object_path")

    def test_empty_path_regexp_no_rules(self):
        """etl_params["path_regexp"] 为空字符串时不应生成 path 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name, path_regexp="")
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]
                assert_rule_absent(self, rules, "bk_separator_object_path")

    def test_fallback_to_built_in_config(self):
        """etl_params 无 path_regexp 时应 fallback 到 built_in_config["option"]["separator_configs"]"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                config["option"]["separator_configs"] = [
                    {"separator_regexp": self.PATH_REGEXP}
                ]
                fields = _get_fields(etl_name)
                etl_params = _get_etl_params(etl_name)
                result = storage.build_log_v4_data_link(fields, etl_params, config)
                rules = result["clean_rules"]
                regex_rules = find_rules_by_output(rules, "bk_separator_object_path")
                self.assertEqual(len(regex_rules), 1)

    def test_etl_params_takes_priority(self):
        """etl_params["path_regexp"] 应优先于 built_in_config separator_configs"""
        other_regexp = r"/var/log/(?P<service>[^/]+)/app\.log"
        storage = ALL_ETL_CLASSES[1][1]()  # JSON
        config = get_fresh_config()
        config["option"]["separator_configs"] = [
            {"separator_regexp": other_regexp}
        ]
        etl_params = _get_etl_params("json", path_regexp=self.PATH_REGEXP)
        result = storage.build_log_v4_data_link(SINGLE_STRING_FIELD, etl_params, config)
        rules = result["clean_rules"]
        regex_rules = find_rules_by_output(rules, "bk_separator_object_path")
        self.assertEqual(regex_rules[0]["operator"]["regex"], self.PATH_REGEXP)

    def test_path_field_assigns_have_correct_types(self):
        """path 提取的字段 assign 规则应有正确的 output_type"""
        storage = ALL_ETL_CLASSES[1][1]()  # JSON
        etl_params = _get_etl_params("json", path_regexp=self.PATH_REGEXP)
        result = storage.build_log_v4_data_link(SINGLE_STRING_FIELD, etl_params, get_fresh_config())
        rules = result["clean_rules"]
        for field_name in ["app_name", "log_type"]:
            matched = find_rules_by_output(rules, field_name)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["operator"]["output_type"], "string")
            self.assertEqual(matched[0]["input_id"], "bk_separator_object_path")
