"""Frozen observation ownership and display semantics, without external services."""

import copy
import unittest

from bkmonitor.aiops.incident.graph_snapshot import snapshot_context, target_analysis


class TestSnapshotEvidence(unittest.TestCase):
    def content(self):
        evidence = []
        for ref, kind, status, data in (
            ("a", "metric", "OK", [{"time": 10, "value": 0}, {"time": 20, "value": None}]),
            ("b", "metric", "OK", [{"time": 10, "value": 17}]),
            ("a", "event", "OK", [{"time": 10, "name": "restart"}]),
            ("c", "metric", "NO_DATA", []),
            ("d", "event", "QUERY_FAILED", []),
        ):
            evidence.append(
                {
                    "evidence_id": ref + kind,
                    "evidence_type": kind,
                    "entity_ref": ref,
                    "response": {"meta": {"status": status}, "data": data},
                }
            )
        return {
            "snapshot_id": "frozen-a",
            "graph_analysis": {
                "protocol": "graph-rca-snapshot",
                "version": "1",
                "producer": {"engine": "graph_walk"},
                "analysis": {"window": {"start_time": 10, "end_time": 20}, "query_window": None},
                "capabilities": {"snapshot_metrics": True, "snapshot_events": True, "realtime_metrics": False},
                "evidence": evidence,
                "links": [],
            },
        }

    def test_two_positive_entities_are_independent_and_keep_zero_null(self):
        content = self.content()
        before = copy.deepcopy(content)
        a = target_analysis(content, entity_ref="a")
        b = target_analysis(content, entity_ref="b")
        self.assertEqual([e["evidence_id"] for e in a["evidence"]], ["ametric", "aevent"])
        self.assertEqual([e["evidence_id"] for e in b["evidence"]], ["bmetric"])
        self.assertEqual([p["value"] for p in a["evidence"][0]["response"]["data"]], [0, None])
        self.assertEqual(b["evidence"][0]["response"]["data"][0]["value"], 17)
        self.assertFalse(b["capabilities"]["snapshot_events"])
        a["evidence"].clear()
        self.assertEqual(content, before)

    def test_empty_failure_and_missing_are_distinct(self):
        content = self.content()
        self.assertEqual(target_analysis(content, entity_ref="c")["availability"]["metric"]["status"], "NO_DATA")
        event_only = target_analysis(content, entity_ref="d")
        self.assertEqual(event_only["availability"]["event"]["status"], "QUERY_FAILED")
        self.assertTrue(event_only["capabilities"]["snapshot_events"])
        self.assertFalse(event_only["capabilities"]["snapshot_metrics"])
        missing = target_analysis(content, entity_ref="missing")
        self.assertEqual(missing["availability"]["metric"]["status"], "NOT_PROVIDED")
        self.assertFalse(missing["capabilities"]["snapshot_metrics"])

    def test_conflicting_link_cannot_move_evidence_between_owners_or_from_edge(self):
        content = self.content()
        content["graph_analysis"]["evidence"].append(
            {
                "evidence_id": "edge",
                "evidence_type": "metric",
                "edge_ref": "calls",
                "response": {"meta": {"status": "OK"}, "data": [{"time": 10, "value": 8}]},
            }
        )
        content["graph_analysis"]["links"] = [
            {"entity_ref": "b", "evidence_ref": "ametric"},
            {"entity_ref": "b", "evidence_ref": "edge"},
        ]
        self.assertEqual([e["evidence_id"] for e in target_analysis(content, entity_ref="b")["evidence"]], ["bmetric"])
        self.assertEqual([e["evidence_id"] for e in target_analysis(content, edge_ref="calls")["evidence"]], ["edge"])

    def test_time_context_does_not_substitute_record_time_or_invent_query_window(self):
        content = self.content()
        content["create_time"] = 999
        context = snapshot_context(content)
        self.assertEqual(context["analysis_window"], {"start_time": 10, "end_time": 20})
        self.assertIsNone(context["query_window"])
        self.assertEqual(context["frame_evidence_mode"], "replace")
        self.assertEqual(context["aggregation_semantics"], "display_only")
        self.assertEqual(context["walk_rounds_semantics"], "traversal")

    def test_next_frame_without_evidence_clears_previous_capabilities(self):
        content = self.content()
        self.assertTrue(target_analysis(content, entity_ref="a")["capabilities"]["snapshot_metrics"])
        content["graph_analysis"]["evidence"] = []
        current = target_analysis(content, entity_ref="a")
        self.assertEqual(current["evidence"], [])
        self.assertFalse(current["capabilities"]["snapshot_metrics"])

    def test_link_owned_shared_evidence_stays_available_only_to_linked_entities(self):
        content = self.content()
        content["graph_analysis"]["evidence"] = [
            {
                "evidence_id": "shared",
                "evidence_type": "event",
                "response": {"meta": {"status": "OK"}, "data": [{"time": 10, "name": "shared-event"}]},
            }
        ]
        content["graph_analysis"]["links"] = [{"entity_ref": ref, "evidence_ref": "shared"} for ref in ("a", "b")]
        for ref in ("a", "b"):
            self.assertEqual(target_analysis(content, entity_ref=ref)["availability"]["event"]["record_count"], 1)
        self.assertEqual(target_analysis(content, entity_ref="c")["evidence"], [])

    def test_truncation_keeps_returned_points_and_reports_partial(self):
        content = self.content()
        content["graph_analysis"]["evidence"][0]["response"]["meta"]["has_more"] = True
        result = target_analysis(content, entity_ref="a")
        self.assertEqual(result["availability"]["metric"]["status"], "PARTIAL")
        self.assertEqual(result["availability"]["metric"]["record_count"], 2)


if __name__ == "__main__":
    unittest.main()
