import json
import unittest

from pydantic import ValidationError

from metadata.utils.graph_write_config import GraphSurrealDBWriteConfig


class GraphWriteConfigTests(unittest.TestCase):
    def test_binding_protocol(self):
        config = GraphSurrealDBWriteConfig.model_validate(
            {
                "timeout": 300,
                "window": 240,
                "concurrency": 32,
            }
        )
        self.assertEqual(config.model_dump(exclude_none=True), {"timeout": 300, "window": 240, "concurrency": 32})

    def test_omitted_fields_preserve_downstream_defaults(self):
        config = GraphSurrealDBWriteConfig()
        self.assertEqual(config.model_dump(exclude_none=True), {})

    def test_partial_config_does_not_invent_defaults(self):
        config = GraphSurrealDBWriteConfig.model_validate({"timeout": 300})
        self.assertEqual(config.model_dump(exclude_none=True), {"timeout": 300})

    def test_positive_controls_reject_invalid_values(self):
        for field in ["timeout", "window", "concurrency"]:
            for value in [0, -1, True, False, "16", 1.5]:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    payload = {field: value}
                    GraphSurrealDBWriteConfig.model_validate(payload)

    def test_unknown_fields_fail_instead_of_silently_ignoring_tuning(self):
        for payload in [
            {"timeout_secs": 300},
            {"heartbeatGapMs": 300000},
            {"request": {"concurrency": 32}},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GraphSurrealDBWriteConfig.model_validate(payload)

    def test_option_round_trip_preserves_binding_fields(self):
        payload = {"timeout": 300, "window": 240, "concurrency": 32}
        config = GraphSurrealDBWriteConfig.from_option_value(payload)
        self.assertEqual(config.model_dump(exclude_none=True), payload)
        self.assertEqual(GraphSurrealDBWriteConfig.from_option_value(json.dumps(payload)), config)

    def test_option_requires_an_object(self):
        for value in [None, [], 300, "[]", "null"]:
            with self.subTest(value=value), self.assertRaises(TypeError):
                GraphSurrealDBWriteConfig.from_option_value(value)
