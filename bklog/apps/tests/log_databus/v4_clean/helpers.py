# -*- coding: utf-8 -*-
"""
V4 清洗规则测试 — 公共断言 helpers 和 ETL 类型列表
"""
import difflib
import json

from apps.log_databus.handlers.etl_storage.bk_log_text import BkLogTextEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage

ALL_ETL_CLASSES = [
    ("text", BkLogTextEtlStorage),
    ("json", BkLogJsonEtlStorage),
    ("delimiter", BkLogDelimiterEtlStorage),
    ("regexp", BkLogRegexpEtlStorage),
]


def rules_diff(actual, expected):
    """生成人类可读的规则差异"""
    actual_str = json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True)
    expected_str = json.dumps(expected, indent=2, ensure_ascii=False, sort_keys=True)
    diff = difflib.unified_diff(
        expected_str.splitlines(),
        actual_str.splitlines(),
        fromfile="expected",
        tofile="actual",
        lineterm="",
    )
    return "\n".join(diff)


def assert_v4_result_equal(test_case, actual, expected, scenario_name=""):
    """全量比对 V4 清洗结果，失败时逐条定位差异"""
    actual_rules = actual["clean_rules"]
    expected_rules = expected["clean_rules"]

    test_case.assertEqual(
        len(actual_rules), len(expected_rules),
        f"[{scenario_name}] 规则数量不匹配: actual={len(actual_rules)}, expected={len(expected_rules)}\n"
        f"{rules_diff(actual_rules, expected_rules)}"
    )

    for i, (a, e) in enumerate(zip(actual_rules, expected_rules)):
        test_case.assertEqual(
            a, e,
            f"[{scenario_name}] Rule[{i}] 不匹配:\n"
            f"  actual:   {json.dumps(a, ensure_ascii=False)}\n"
            f"  expected: {json.dumps(e, ensure_ascii=False)}"
        )

    test_case.assertEqual(actual.get("es_storage_config"), expected.get("es_storage_config"),
                          f"[{scenario_name}] es_storage_config 不匹配")
    test_case.assertEqual(actual.get("doris_storage_config"), expected.get("doris_storage_config"),
                          f"[{scenario_name}] doris_storage_config 不匹配")


def find_rules_by_output(rules, output_id):
    """查找所有 output_id 匹配的规则"""
    return [r for r in rules if r.get("output_id") == output_id]


def find_rules_by_input(rules, input_id):
    """查找所有 input_id 匹配的规则"""
    return [r for r in rules if r.get("input_id") == input_id]


def find_rules_by_type(rules, operator_type):
    """查找所有 operator.type 匹配的规则"""
    return [r for r in rules if r.get("operator", {}).get("type") == operator_type]


def get_output_ids(rules):
    """获取所有规则的 output_id 集合"""
    return {r.get("output_id") for r in rules}


def assert_rule_exists(tc, rules, output_id, operator_type=None):
    """断言存在指定 output_id 的规则，可选检查 operator.type"""
    matched = find_rules_by_output(rules, output_id)
    tc.assertTrue(len(matched) > 0, f"Expected rule with output_id={output_id!r} but not found")
    if operator_type is not None:
        types = [r["operator"]["type"] for r in matched]
        tc.assertIn(operator_type, types,
                     f"Expected operator type {operator_type!r} for output_id={output_id!r}, got {types}")
    return matched


def assert_rule_absent(tc, rules, output_id):
    """断言不存在指定 output_id 的规则"""
    matched = find_rules_by_output(rules, output_id)
    tc.assertEqual(len(matched), 0, f"Expected no rule with output_id={output_id!r} but found {len(matched)}")
