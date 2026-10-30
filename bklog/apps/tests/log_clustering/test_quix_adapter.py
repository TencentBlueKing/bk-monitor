from django.test import SimpleTestCase

from apps.log_clustering.exceptions import QuixClusteringParamsInvalidException
from apps.log_clustering.handlers.quix.adapter import (
    build_binding,
    build_clustering_config,
    build_index_names,
    convert_filter_rules,
)
from apps.log_clustering.models import LogClusteringRuntime

KAFKA_BINDING = {
    "cluster_ref": "quix-e2e",
    "input_topic": "lc-task-in",
    "output_topic": "lc-task-out",
    "consumer_group": "lc-task-worker",
    "result_group": "lc-task-result",
    "partitions": 2,
    "retention_ms": 604800000,
    "recovery_window_ms": 86400000,
    "source_namespace": "test-namespace",
    "mapping_revision": "log-v1",
}


class TestConvertFilterRules(SimpleTestCase):
    def test_converts_all_supported_ops_and_conditions(self):
        rules = [
            {"fields_name": "level", "op": "=", "value": ["ERROR", "WARN"], "logic_operator": "and"},
            {"fields_name": "level", "op": "!=", "value": ["DEBUG"], "logic_operator": "AND"},
            {"fields_name": "log", "op": "contains", "value": ["timeout"], "logic_operator": "or"},
            {"fields_name": "log", "op": "not contains", "value": "retry", "logic_operator": None},
        ]

        self.assertEqual(
            convert_filter_rules(rules),
            [
                {"key": "level", "method": "eq", "value": ["ERROR", "WARN"], "condition": ""},
                {"key": "level", "method": "neq", "value": ["DEBUG"], "condition": "and"},
                {"key": "log", "method": "include", "value": ["timeout"], "condition": "or"},
                {"key": "log", "method": "exclude", "value": ["retry"], "condition": "and"},
            ],
        )

    def test_like_patterns_map_to_all_eight_methods(self):
        for op, positive in (("LIKE", True), ("NOT LIKE", False)):
            for pattern, expected in (
                ("error", "eq" if positive else "neq"),
                ("%error%", "include" if positive else "exclude"),
                ("error%", "starts_with" if positive else "not_starts_with"),
                ("%error", "ends_with" if positive else "not_ends_with"),
            ):
                with self.subTest(op=op, pattern=pattern):
                    result = convert_filter_rules([{"fields_name": "log", "op": op, "value": [pattern]}])
                    self.assertEqual(result, [{"key": "log", "method": expected, "value": ["error"], "condition": ""}])

    def test_prefix_suffix_operators(self):
        for op in ("starts_with", "not_starts_with", "ends_with", "not_ends_with"):
            with self.subTest(op=op):
                self.assertEqual(
                    convert_filter_rules([{"fields_name": "log", "op": op, "value": "x"}])[0]["method"], op
                )

    def test_like_values_preserve_literal_content_and_grouping(self):
        rules = [
            {"fields_name": "log", "op": "LIKE", "value": ["% error %", "%warn'%"]},
            {"fields_name": "log", "op": "NOT LIKE", "value": ["debug%", "trace%"], "logic_operator": "or"},
        ]
        result = convert_filter_rules(rules)
        self.assertEqual(result[0]["value"], [" error ", "warn'"])
        self.assertEqual(
            result[1], {"key": "log", "method": "not_starts_with", "value": ["debug", "trace"], "condition": "or"}
        )
        self.assertEqual(rules[0]["value"], ["% error %", "%warn'%"])

    def test_unsupported_like_patterns_are_rejected_without_reinterpretation(self):
        for values in (["er%ror"], ["err_r"], [r"error\%"], ["%"], ["%%error"], ["error%", "%warn"]):
            for op in ("LIKE", "NOT LIKE"):
                with self.subTest(values=values, op=op), self.assertRaises(QuixClusteringParamsInvalidException):
                    convert_filter_rules([{"fields_name": "log", "op": op, "value": values}])

    def test_empty_rules_mean_all_logs(self):
        self.assertEqual(convert_filter_rules([]), [])
        self.assertEqual(convert_filter_rules(None), [])

    def test_unsupported_rules_are_rejected(self):
        invalid_rules = [
            [{"fields_name": "log", "op": "LIKE", "value": ["er%ror"]}],
            [{"fields_name": "", "op": "=", "value": ["ERROR"]}],
            [{"fields_name": "level", "op": "=", "value": []}],
            [
                {"fields_name": "level", "op": "=", "value": ["ERROR"]},
                {"fields_name": "level", "op": "=", "value": ["WARN"], "logic_operator": "xor"},
            ],
        ]
        for rules in invalid_rules:
            with self.subTest(rules=rules), self.assertRaises(QuixClusteringParamsInvalidException):
                convert_filter_rules(rules)


class TestBuildBinding(SimpleTestCase):
    def test_clustering_config_uses_fixed_threshold_and_ms_timestamp(self):
        config = build_clustering_config("log", [{"fields_name": "level", "op": "=", "value": ["ERROR"]}])

        self.assertEqual(config["distance_threshold"], "0.5")
        self.assertEqual(config["input_mapping"], {"log": "log", "timestamp": "dtEventTimeStamp"})
        self.assertEqual(config["log_filter"][0]["method"], "eq")

    def test_clustering_field_is_required(self):
        with self.assertRaises(QuixClusteringParamsInvalidException):
            build_clustering_config("", [])

    def test_binding_comes_from_runtime_facts(self):
        pattern_index, state_index = build_index_names(42)
        runtime = LogClusteringRuntime(
            index_set_id=42,
            bkfara_task_id="task-uuid",
            generation=1,
            input_revision=3,
            kafka_binding=KAFKA_BINDING,
            pattern_index=pattern_index,
            state_index=state_index,
        )
        config = build_clustering_config("log", [])

        binding = build_binding(runtime, config, max_message_bytes=1048576)

        self.assertEqual(
            binding,
            {
                "task_id": "task-uuid",
                "index_id": "42",
                "generation": 1,
                "config_revision": 3,
                "kafka": KAFKA_BINDING,
                "log_filter": [],
                "input_mapping": {"log": "log", "timestamp": "dtEventTimeStamp"},
                "distance_threshold": "0.5",
                "pattern_index": "log-clustering-42-pattern",
                "state_index": "log-clustering-42-state",
                "max_message_bytes": 1048576,
            },
        )

    def test_binding_omits_unset_message_limit(self):
        runtime = LogClusteringRuntime(index_set_id=1, kafka_binding=KAFKA_BINDING)

        self.assertNotIn("max_message_bytes", build_binding(runtime, build_clustering_config("log", [])))
