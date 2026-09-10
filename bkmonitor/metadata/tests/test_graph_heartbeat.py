import unittest

from metadata.utils.graph_heartbeat import resolve_graph_heartbeat_gap_ms as resolve


class GraphHeartbeatGapTests(unittest.TestCase):
    def test_default_omits_field(self):
        self.assertIsNone(resolve(None, {}, "tenant-a", 123))

    def test_default_five_minutes(self):
        self.assertEqual(resolve(300000, {}, "tenant-a", 123), 300000)

    def test_business_override_and_tenant_isolation(self):
        overrides = {"tenant-a": {"123": 600000}}
        self.assertEqual(resolve(300000, overrides, "tenant-a", 123), 600000)
        self.assertEqual(resolve(300000, overrides, "tenant-b", 123), 300000)
        self.assertEqual(resolve(300000, overrides, "tenant-a", 456), 300000)

    def test_explicit_none_disables_override(self):
        self.assertIsNone(resolve(300000, {"tenant-a": {"123": None}}, "tenant-a", 123))

    def test_invalid_values_are_rejected(self):
        for value in [0, -1, True, False, "300000", 1.5, 86400001]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve(value, {}, "tenant-a", 123)
                with self.assertRaises(ValueError):
                    resolve(None, {"tenant-a": {"123": value}}, "tenant-a", 123)

    def test_invalid_mapping_is_rejected(self):
        for overrides in [None, [], {"tenant-a": []}, {"tenant-a": {123: 300000}}, {"": {}}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                resolve(None, overrides, "tenant-a", 123)

    def test_changes_are_resolved_on_every_composition(self):
        overrides = {"tenant-a": {"123": 300000}}
        self.assertEqual(resolve(None, overrides, "tenant-a", 123), 300000)
        overrides["tenant-a"]["123"] = 600000
        self.assertEqual(resolve(None, overrides, "tenant-a", 123), 600000)

    def test_bounds(self):
        for value in [1, 86400000]:
            self.assertEqual(resolve(value, {}, "tenant-a", 123), value)
