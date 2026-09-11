import unittest

from pydantic import ValidationError

from metadata.utils.graph_write_config import GraphSurrealDBWriteConfig


class GraphWriteConfigTests(unittest.TestCase):
    def test_protocol_and_destinations(self):
        config = GraphSurrealDBWriteConfig.model_validate(
            {
                "batch": {"max_events": 1000, "timeout_secs": 1},
                "request": {"concurrency": 16},
                "vertexDebounceSecs": 240,
                "heartbeatGapMs": 300000,
            }
        )
        self.assertEqual(
            config.databus_spec(),
            {
                "batch": {"max_events": 1000, "timeout_secs": 1},
                "request": {"concurrency": 16},
                "vertexDebounceSecs": 240,
            },
        )
        self.assertEqual(config.binding_spec(), {"heartbeatGapMs": 300000})

    def test_omitted_fields_preserve_downstream_defaults(self):
        config = GraphSurrealDBWriteConfig()
        self.assertEqual(config.databus_spec(), {})
        self.assertEqual(config.binding_spec(), {})

    def test_partial_batch_does_not_invent_defaults(self):
        config = GraphSurrealDBWriteConfig.model_validate({"batch": {"max_events": 500}})
        self.assertEqual(config.databus_spec(), {"batch": {"max_events": 500}})

    def test_empty_nested_objects_are_omitted(self):
        config = GraphSurrealDBWriteConfig.model_validate({"batch": {}, "request": {}})
        self.assertEqual(config.databus_spec(), {})

    def test_zero_debounce_is_preserved(self):
        config = GraphSurrealDBWriteConfig.model_validate({"vertexDebounceSecs": 0})
        self.assertEqual(config.databus_spec(), {"vertexDebounceSecs": 0})

    def test_positive_controls_reject_invalid_values(self):
        for path in [
            ("batch", "max_events"),
            ("batch", "timeout_secs"),
            ("request", "concurrency"),
            ("heartbeatGapMs",),
        ]:
            for value in [0, -1, True, False, "16", 1.5]:
                payload = {path[-1]: value}
                if len(path) == 2:
                    payload = {path[0]: payload}
                with self.subTest(path=path, value=value), self.assertRaises(ValidationError):
                    GraphSurrealDBWriteConfig.model_validate(payload)

    def test_debounce_rejects_negative_and_non_integer_values(self):
        for value in [-1, True, "240", 1.5]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                GraphSurrealDBWriteConfig.model_validate({"vertexDebounceSecs": value})

    def test_unknown_fields_fail_instead_of_silently_ignoring_tuning(self):
        for payload in [{"vertexDebounceSec": 240}, {"batch": {"maxEvents": 1000}}, {"request": {"threads": 16}}]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GraphSurrealDBWriteConfig.model_validate(payload)

    def test_option_round_trip_preserves_camel_case(self):
        config = GraphSurrealDBWriteConfig.model_validate({"vertexDebounceSecs": 240, "heartbeatGapMs": 300000})
        payload = config.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(payload, {"vertexDebounceSecs": 240, "heartbeatGapMs": 300000})
        self.assertEqual(GraphSurrealDBWriteConfig.model_validate(payload), config)

    def test_configuration_instances_are_independent(self):
        first = GraphSurrealDBWriteConfig.model_validate({"request": {"concurrency": 16}})
        second = GraphSurrealDBWriteConfig.model_validate({"request": {"concurrency": 4}})
        first.request.concurrency = 8
        self.assertEqual(second.databus_spec(), {"request": {"concurrency": 4}})
