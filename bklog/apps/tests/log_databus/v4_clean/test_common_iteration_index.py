# -*- coding: utf-8 -*-
"""
组件测试：_build_flat_built_in_fields_v4
4 ETL × flat_field True/False × 多字段类型（integer/object/keyword）
"""
from unittest import TestCase

from apps.tests.log_databus.v4_clean.helpers import (
    ALL_ETL_CLASSES,
)
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import (
    get_fresh_config,
    make_no_iteration_index_config,
    make_no_flat_fields_config,
    make_multi_flat_fields_config,
)


class TestCommonFlatBuiltInFields(TestCase):
    """测试 _build_flat_built_in_fields_v4 在所有 ETL 类型下的行为"""

    def test_flat_field_true_generates_rule(self):
        """flat_field=True 时应生成 iterationIndex 规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                rules = storage._build_flat_built_in_fields_v4(get_fresh_config())
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
                rules = storage._build_flat_built_in_fields_v4(config)
                self.assertEqual(len(rules), 0)

    def test_no_iteration_index_field_in_config(self):
        """built_in_config.fields 中无 iterationIndex 字段时不生成规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = get_fresh_config()
                config["fields"] = [f for f in config["fields"] if f["field_name"] != "iterationIndex"]
                rules = storage._build_flat_built_in_fields_v4(config)
                self.assertEqual(len(rules), 0)

    def test_no_flat_fields_generates_empty(self):
        """所有字段 flat_field=False 时不应生成任何规则"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_no_flat_fields_config()
                rules = storage._build_flat_built_in_fields_v4(config)
                self.assertEqual(len(rules), 0)

    def test_multi_flat_fields_all_from_iter_item(self):
        """多个 flat_field=True 字段都应从 iter_item 提取"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_multi_flat_fields_config()
                rules = storage._build_flat_built_in_fields_v4(config)

                # 应包含 iterationIndex + syslogSource + syslogLabel + winEventProviderName + winEventRecordId = 5 个
                self.assertEqual(len(rules), 5)

                # 所有规则的 input_id 都应为 iter_item
                for rule in rules:
                    self.assertEqual(rule["input_id"], "iter_item")

                # 验证各字段的 output_id 存在
                output_ids = {r["output_id"] for r in rules}
                expected_ids = {"iterationIndex", "syslogSource", "syslogLabel", "winEventProviderName", "winEventRecordId"}
                self.assertEqual(output_ids, expected_ids)

    def test_multi_flat_fields_type_mapping(self):
        """多个 flat_field=True 字段的类型映射应正确"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_multi_flat_fields_config()
                rules = storage._build_flat_built_in_fields_v4(config)

                rules_by_output = {r["output_id"]: r for r in rules}

                # iterationIndex: es_type=integer → output_type=long
                self.assertEqual(rules_by_output["iterationIndex"]["operator"]["output_type"], "long")

                # syslogSource: es_type=object → output_type=dict
                self.assertEqual(rules_by_output["syslogSource"]["operator"]["output_type"], "dict")

                # syslogLabel: es_type=object → output_type=dict
                self.assertEqual(rules_by_output["syslogLabel"]["operator"]["output_type"], "dict")

                # winEventProviderName: field_type=string, es_type=keyword → output_type=string
                self.assertEqual(rules_by_output["winEventProviderName"]["operator"]["output_type"], "string")

                # winEventRecordId: field_type=string, es_type=keyword → output_type=string
                self.assertEqual(rules_by_output["winEventRecordId"]["operator"]["output_type"], "string")

    def test_multi_flat_fields_alias_mapping(self):
        """多个 flat_field=True 字段的 alias_name 应正确映射为 key_index"""
        for etl_name, etl_cls in ALL_ETL_CLASSES:
            with self.subTest(etl=etl_name):
                storage = etl_cls()
                config = make_multi_flat_fields_config()
                rules = storage._build_flat_built_in_fields_v4(config)

                rules_by_output = {r["output_id"]: r for r in rules}

                # iterationIndex: alias_name=iterationindex
                self.assertEqual(rules_by_output["iterationIndex"]["operator"]["key_index"], "iterationindex")

                # syslogSource: alias_name=log
                self.assertEqual(rules_by_output["syslogSource"]["operator"]["key_index"], "log")

                # syslogLabel: alias_name=syslog
                self.assertEqual(rules_by_output["syslogLabel"]["operator"]["key_index"], "syslog")

                # winEventProviderName: alias_name=provider_name
                self.assertEqual(rules_by_output["winEventProviderName"]["operator"]["key_index"], "provider_name")

                # winEventRecordId: alias_name=record_id
                self.assertEqual(rules_by_output["winEventRecordId"]["operator"]["key_index"], "record_id")