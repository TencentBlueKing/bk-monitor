import copy
from unittest import TestCase

from alarm_backends.core.control.item import gen_condition_matcher


class TestConditionMatcher(TestCase):
    def test_log_operator_conversion(self):
        """日志操作符转换后，后台二次过滤仍保留原来的等于/不等于语义。"""
        for method, origin_method, expected in [
            ("is one of", "eq", {"worker-1": False, "worker-3": True, "other": False}),
            ("is not one of", "neq", {"worker-1": True, "worker-3": False, "other": False}),
        ]:
            conditions = [
                {"key": "workload", "method": "reg", "value": [r"worker-\d+"]},
                {
                    "key": "workload",
                    "method": method,
                    "_origin_method": origin_method,
                    "value": ["worker-3"],
                    "condition": "and",
                },
            ]
            original = copy.deepcopy(conditions)
            matcher = gen_condition_matcher(conditions)
            for workload, matches in expected.items():
                with self.subTest(method=method, workload=workload):
                    self.assertEqual(matcher.is_match({"workload": workload}), matches)
            self.assertEqual(conditions, original)

    def test_native_operators(self):
        for method, expected in [("eq", False), ("neq", True)]:
            with self.subTest(method=method):
                matcher = gen_condition_matcher([{"key": "workload", "method": method, "value": ["worker-3"]}])
                self.assertEqual(matcher.is_match({"workload": "worker-1"}), expected)

    def test_log_operator_in_or_group(self):
        matcher = gen_condition_matcher(
            [
                {"key": "workload", "method": "reg", "value": [r"worker-\d+"]},
                {
                    "key": "workload",
                    "method": "is not one of",
                    "_origin_method": "neq",
                    "value": ["worker-3"],
                    "condition": "and",
                },
                {"key": "workload", "method": "eq", "value": ["fallback"], "condition": "or"},
            ]
        )
        for workload, expected in [("worker-1", True), ("worker-3", False), ("fallback", True), ("other", False)]:
            with self.subTest(workload=workload):
                self.assertEqual(matcher.is_match({"workload": workload}), expected)
