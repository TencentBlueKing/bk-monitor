"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from bkmonitor.aiops.incident.graph_snapshot import target_analysis
from bkmonitor.aiops.incident.models import IncidentSnapshot
from monitor_web.incident.resources import IncidentTopologyMenuResource, IncidentTopologyResource


def build_snapshot_content(entities):
    return {
        "bk_biz_id": 2,
        "incident_alerts": [],
        "product_hierarchy_category": {
            "service": {
                "category_id": 1,
                "category_name": "service",
                "category_alias": "服务",
            }
        },
        "product_hierarchy_rank": {
            "rank_0": {
                "rank_id": 0,
                "rank_name": "rank_0",
                "rank_alias": "服务模块",
                "rank_category": "service",
            }
        },
        "incident_propagation_graph": {
            "entities": entities,
            "edges": [],
        },
    }


def build_bcs_pod(entity_id, workload_name, resource_version):
    return {
        "entity_id": entity_id,
        "entity_name": entity_id,
        "entity_type": "BcsPod",
        "is_anomaly": False,
        "anomaly_score": 0,
        "anomaly_type": "",
        "is_root": False,
        "is_on_alert": False,
        "bk_biz_id": 2,
        "rank_name": "rank_0",
        "dimensions": {
            "pod_name": entity_id,
        },
        "tags": {
            "BcsWorkload": {
                "name": workload_name,
                "namespace": "default",
            }
        },
        "properties": {"resource_version": resource_version} if resource_version is not None else {},
        "observe_time_rage": {},
        "rca_trace_info": {},
        "component_type": "primary",
    }


class TestIncidentTopologyAggregateVersion(SimpleTestCase):
    def test_aggregate_version_only_merges_same_workload_and_version(self):
        snapshot = IncidentSnapshot(
            build_snapshot_content(
                [
                    build_bcs_pod("pod-a", "workload-a", "v1"),
                    build_bcs_pod("pod-b", "workload-a", "v1"),
                    build_bcs_pod("pod-c", "workload-a", "v2"),
                    build_bcs_pod("pod-d", "workload-b", "v1"),
                    build_bcs_pod("pod-e", "workload-a", None),
                ]
            )
        )

        incident = SimpleNamespace(feedback=SimpleNamespace(incident_root=None))
        snapshot.aggregate_graph(incident, aggregate_dependency=False, aggregate_version=True)

        self.assertEqual(len(snapshot.incident_graph_entities), 4)

        aggregated_entity = snapshot.incident_graph_entities["pod-a"]
        self.assertEqual(aggregated_entity.entity_name, "pod-a")
        self.assertEqual(aggregated_entity.properties["aggregate_type"], "resource_version")
        self.assertEqual(aggregated_entity.properties["resource_version"], "v1")
        self.assertNotIn("original_entity_name", aggregated_entity.properties)
        self.assertEqual([entity.entity_id for entity in aggregated_entity.aggregated_entities], ["pod-b"])

        self.assertIn("pod-c", snapshot.incident_graph_entities)
        self.assertIn("pod-d", snapshot.incident_graph_entities)
        self.assertIn("pod-e", snapshot.incident_graph_entities)

    def test_menu_switches_expose_backend_protocol_for_version_aggregate(self):
        snapshot = IncidentSnapshot(
            build_snapshot_content(
                [
                    build_bcs_pod("pod-a", "workload-a", "v1"),
                ]
            )
        )

        aggregate_switches = IncidentTopologyMenuResource.generate_aggregate_switches(snapshot)

        self.assertEqual(
            aggregate_switches,
            [
                {
                    "key": "aggregate_version",
                    "name": "按部署版本聚合",
                    "default": False,
                    "entity_type": "BcsPod",
                    "field": "entity.properties.resource_version",
                    "description": "仅对 BcsPod 生效；resource_version 缺失时补 None，不参与聚合",
                }
            ],
        )


class TestTopologyGroupRoot(SimpleTestCase):
    def make_content(self, entity_type="BcsWorkload", is_root=True, on_alert=False):
        parent = build_bcs_pod("parent", "workload", None)
        parent.update(entity_type=entity_type, is_root=is_root, is_on_alert=on_alert, is_anomaly=is_root)
        parent["dimensions"] = {"namespace": "default", "workload_name": "workload"}
        content = build_snapshot_content(
            [build_bcs_pod("pod-a", "workload", None), parent, build_bcs_pod("pod-b", "workload", None)]
        )
        content["incident_propagation_graph"]["edges"] = [
            {"source_id": pod, "target_id": "parent", "edge_type": "dependency", "events": []}
            for pod in ("pod-a", "pod-b")
        ]
        return content

    def render(self, content, feedback=None, aggregate=False):
        original = copy.deepcopy(content)
        snapshot = IncidentSnapshot(copy.deepcopy(content))
        incident = SimpleNamespace(feedback=SimpleNamespace(incident_root=feedback))
        if aggregate:
            snapshot.aggregate_graph(incident, aggregate_dependency=True, aggregate_cluster=True)
        with patch(
            "monitor_web.incident.resources.resource.cc.get_app_by_id", return_value=SimpleNamespace(name="biz")
        ):
            result = IncidentTopologyResource().generate_topology_data_from_snapshot(incident, snapshot)
        self.assertEqual(content, original)
        return result

    def test_workload_and_service_roots_remain_nodes_with_their_edges(self):
        for entity_type in ("BcsWorkload", "BcsService"):
            for aggregate in (False, True):
                with self.subTest(entity_type=entity_type, aggregate=aggregate):
                    content = self.make_content(entity_type)
                    result = self.render(content, aggregate=aggregate)
                    nodes = {node["id"]: node for node in result["nodes"]}
                    self.assertIn("parent", nodes)
                    self.assertTrue(nodes["parent"]["entity"]["is_root"])
                    self.assertEqual(
                        nodes["parent"]["entity"]["dimensions"],
                        content["incident_propagation_graph"]["entities"][1]["dimensions"],
                    )
                    self.assertNotIn("parent", {combo["id"] for combo in result["sub_combos"]})
                    self.assertTrue(result["edges"])
                    for edge in result["edges"]:
                        self.assertIn(edge["source"], nodes)
                        self.assertEqual(edge["target"], "parent")

    def test_root_with_no_children_is_not_discarded(self):
        content = self.make_content()
        content["incident_propagation_graph"]["entities"] = content["incident_propagation_graph"]["entities"][1:2]
        content["incident_propagation_graph"]["edges"] = []
        result = self.render(content)
        self.assertEqual([node["id"] for node in result["nodes"]], ["parent"])

    def test_feedback_root_survives_without_changing_algorithm_root_flags(self):
        result = self.render(self.make_content(is_root=False), feedback="parent")
        parent = next(node for node in result["nodes"] if node["id"] == "parent")
        self.assertTrue(parent["is_feedback_root"])
        self.assertFalse(parent["entity"]["is_root"])
        self.assertEqual(len(result["edges"]), 2)

    def test_non_root_alert_parent_keeps_existing_group_presentation(self):
        result = self.render(self.make_content(is_root=False, on_alert=True))
        self.assertEqual({node["id"] for node in result["nodes"]}, {"pod-a", "pod-b"})
        self.assertEqual([combo["id"] for combo in result["sub_combos"]], ["parent"])
        self.assertEqual({node["subComboId"] for node in result["nodes"]}, {"parent"})
        self.assertEqual(result["edges"], [])

    def test_alerting_root_is_not_duplicated_as_a_group(self):
        result = self.render(self.make_content(on_alert=True))
        self.assertEqual(len(result["nodes"]), 3)
        self.assertEqual(result["sub_combos"], [])
        self.assertEqual(len(result["edges"]), 2)


class TestUnifiedGraphSnapshot(SimpleTestCase):
    def test_empty_graph_and_hierarchy_render_without_indexing_a_root(self):
        content = build_snapshot_content([])
        content["product_hierarchy_category"] = {}
        content["product_hierarchy_rank"] = {}
        snapshot = IncidentSnapshot(content)
        incident = SimpleNamespace(feedback=SimpleNamespace(incident_root=None))
        snapshot.aggregate_graph(incident, aggregate_dependency=True, aggregate_cluster=True)
        result = IncidentTopologyResource().generate_topology_data_from_snapshot(incident, snapshot)
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])
        self.assertEqual(result["combos"], [])

    @patch("monitor_web.incident.resources.IncidentSnapshotDocument")
    @patch("monitor_web.incident.resources.IncidentDocument")
    def test_empty_or_summary_only_timeline_returns_no_data(self, incident_model, snapshot_model):
        class Snapshot(SimpleNamespace):
            def __getitem__(self, key):
                return getattr(self, key)

        incident_model.get.return_value = SimpleNamespace(incident_id=1)
        for frames in ([], [{"fpp_snapshot_id": "fpp:None"}], [{"fpp_snapshot_id": "fpp:1:llm_summary"}]):
            snapshot_model.list_by_incident_id.return_value = [Snapshot(**frame, create_time=1) for frame in frames]
            result = IncidentTopologyResource().perform_request({"id": 1, "start_time": 1, "only_diff": True})
            self.assertEqual(result["status"], "NO_DATA")
            self.assertEqual(result["latest"]["nodes"], [])
            self.assertEqual(result["diff"], [])
            self.assertEqual(result["complete"]["edges"], [])

    def build_content(self):
        content = build_snapshot_content([build_bcs_pod(name, "workload", "v1") for name in ("a", "b", "c")])
        content["incident_propagation_graph"]["edges"] = [
            {
                "source_id": "a",
                "target_id": "c",
                "edge_type": "dependency",
                "properties": {"edge_id": "owns", "relation": "BELONG_TO"},
            },
            {
                "source_id": "a",
                "target_id": "c",
                "edge_type": "spread",
                "properties": {"edge_id": "calls", "relation": "SERVICE_CALL"},
            },
            {
                "source_id": "b",
                "target_id": "c",
                "edge_type": "spread",
                "properties": {"edge_id": "other-calls", "relation": "SERVICE_CALL"},
            },
        ]
        content["graph_analysis"] = {
            "protocol": "graph-rca-snapshot",
            "version": "1",
            "producer": {"engine": "graph_walk"},
            "capabilities": {"realtime_metrics": False, "context_expansion": False},
            "root_causes": [{"entity_ref": "a", "rank": 1, "scores": [{"kind": "ce", "value": 3.2}]}],
            "evidence": [
                {"evidence_id": "cpu-a", "entity_ref": "a"},
                {"evidence_id": "cpu-b", "entity_ref": "b"},
                {"evidence_id": "edge-errors", "edge_ref": "calls"},
            ],
            "links": [{"evidence_ref": "edge-errors", "edge_ref": "calls", "entity_ref": None}],
            "context_graphs": [],
        }
        return content

    def test_parallel_relations_survive_model_and_aggregation(self):
        content = self.build_content()
        original = copy.deepcopy(content)
        snapshot = IncidentSnapshot(content)
        self.assertEqual(len(snapshot.incident_graph_edges), 3)
        snapshot.merge_entities(["a", "b"])
        edges = [edge.to_src_dict() for edge in snapshot.incident_graph_edges.values()]
        self.assertEqual({edge["edge_type"] for edge in edges}, {"dependency", "spread"})
        self.assertEqual(len(edges), 2)
        self.assertEqual(len({edge["id"] for edge in edges}), 2)
        self.assertEqual(next(edge for edge in edges if edge["edge_type"] == "spread")["count"], 2)
        self.assertEqual(content, original)

    def test_static_evidence_and_scores_do_not_cross_entity_or_edge(self):
        content = self.build_content()
        original = copy.deepcopy(content)
        a = target_analysis(content, entity_ref="a")
        b = target_analysis(content, entity_ref="b")
        edge = target_analysis(content, edge_ref="calls")
        self.assertEqual([item["evidence_id"] for item in a["evidence"]], ["cpu-a"])
        self.assertEqual([item["evidence_id"] for item in b["evidence"]], ["cpu-b"])
        self.assertEqual([item["evidence_id"] for item in edge["evidence"]], ["edge-errors"])
        self.assertEqual(a["root_causes"][0]["scores"][0]["value"], 3.2)
        self.assertEqual(b["root_causes"], [])
        self.assertEqual(content, original)

    def test_aggregated_edge_detail_preserves_original_evidence_and_container_id(self):
        snapshot = IncidentSnapshot(self.build_content())
        snapshot.merge_entities(["a", "b"])
        rendered = [
            IncidentTopologyResource().generate_edge_info(snapshot, edge)
            for edge in snapshot.incident_graph_edges.values()
        ]
        call = next(edge for edge in rendered if edge["edge_type"] == "spread")
        self.assertEqual([item["evidence_id"] for item in call["graph_analysis"]["evidence"]], ["edge-errors"])
        child = call["aggregated_edges"][0]
        self.assertEqual(child["graph_analysis"]["evidence"], [])
        self.assertFalse(child["graph_analysis"]["capabilities"]["realtime_metrics"])
        self.assertEqual(child["properties"]["aggregated_by_id"], call["id"])

    def test_unknown_protocol_disables_live_queries_instead_of_assuming_legacy(self):
        content = self.build_content()
        content["graph_analysis"]["version"] = "future"
        value = target_analysis(content, entity_ref="a")
        self.assertEqual(value["version"], "unsupported")
        self.assertEqual(value["capabilities"], {})

    def test_repeated_aggregation_keeps_members_and_their_own_sidebars(self):
        content = self.build_content()
        content["incident_propagation_graph"]["entities"].append(build_bcs_pod("d", "workload", "v1"))
        content["incident_propagation_graph"]["edges"].append(
            {
                "source_id": "d",
                "target_id": "c",
                "edge_type": "spread",
                "properties": {"edge_id": "d-calls", "relation": "SERVICE_CALL"},
            }
        )
        snapshot = IncidentSnapshot(content)
        snapshot.merge_entities(["a", "b"])
        snapshot.merge_entities(["d", "a"])
        main = snapshot.incident_graph_entities["d"]
        self.assertEqual([member.entity_id for member in main.aggregated_entities], ["a", "b"])
        self.assertTrue(all(member.properties["aggregated_by"] == "d" for member in main.aggregated_entities))
        call = next(edge for edge in snapshot.incident_graph_edges.values() if edge.edge_type.value == "spread")
        result = IncidentTopologyResource().generate_edge_info(snapshot, call)
        a = result["aggregated_edges"][0]
        b = result["aggregated_edges"][1]
        self.assertEqual(result["count"], 3)
        self.assertEqual(a["id"], "calls")
        self.assertEqual(b["id"], "other-calls")
        self.assertEqual(a["properties"]["aggregated_by_id"], result["id"])
        self.assertEqual(b["properties"]["aggregated_by_id"], result["id"])
        self.assertEqual([e["evidence_id"] for e in a["graph_analysis"]["evidence"]], ["edge-errors"])
        self.assertEqual(b["graph_analysis"]["evidence"], [])

    @patch("bkmonitor.aiops.incident.models.api", new_callable=MagicMock, spec=["bkdata"])
    def test_unavailable_new_context_never_calls_legacy_producer(self, api):
        snapshot = IncidentSnapshot(copy.deepcopy(self.build_content()))
        self.assertIsNone(snapshot.generate_entity_sub_graph_from_api(1, "a", "snapshot"))
        api.bkdata.get_incident_topo_by_entity.assert_not_called()

    @patch("bkmonitor.aiops.incident.models.api", new_callable=MagicMock, spec=["bkdata"])
    def test_context_expansion_uses_frozen_snapshot(self, api):
        content = self.build_content()
        content["graph_analysis"]["capabilities"]["context_expansion"] = True
        content["graph_analysis"]["context_graphs"] = [
            {"kind": "one_hop", "entity_ref": "a", "graph": copy.deepcopy(content["incident_propagation_graph"])}
        ]
        snapshot = IncidentSnapshot(copy.deepcopy(content))
        expanded = snapshot.generate_entity_sub_graph_from_api(1, "a", "snapshot")
        self.assertEqual(len(expanded.incident_graph_edges), 3)
        self.assertIsNone(snapshot.generate_entity_sub_graph_from_api(1, "b", "snapshot"))
        api.bkdata.get_incident_topo_by_entity.assert_not_called()

    @patch("bkmonitor.aiops.incident.models.api", new_callable=MagicMock, spec=["bkdata"])
    def test_context_neighbor_can_expand_without_primary_membership(self, api):
        content = self.build_content()
        neighbor = build_bcs_pod("neighbor", "other-workload", "v1")
        child = build_bcs_pod("neighbor-child", "other-workload", "v1")
        content["graph_analysis"]["capabilities"]["context_expansion"] = True
        content["graph_analysis"]["context_graphs"] = [
            {
                "kind": "one_hop",
                "entity_ref": None,
                "graph": {"entities": [content["incident_propagation_graph"]["entities"][0], neighbor], "edges": []},
            },
            {"kind": "contains", "entity_ref": "neighbor", "graph": {"entities": [neighbor, child], "edges": []}},
        ]
        original = copy.deepcopy(content)
        snapshot = IncidentSnapshot(content)
        self.assertNotIn("neighbor", snapshot.incident_graph_entities)
        first = snapshot.generate_entity_sub_graph_from_api(1, "a", "snapshot")
        self.assertIn("neighbor", first.incident_graph_entities)
        second = snapshot.generate_entity_sub_graph_from_api(1, "neighbor", "snapshot")
        self.assertIn("neighbor-child", second.incident_graph_entities)
        self.assertIsNone(snapshot.generate_entity_sub_graph_from_api(1, "unknown", "snapshot"))
        self.assertEqual(content, original)
        api.bkdata.get_incident_topo_by_entity.assert_not_called()

    @patch("bkmonitor.aiops.incident.models.api", new_callable=MagicMock, spec=["bkdata"])
    def test_context_only_edge_keeps_its_own_frozen_metrics(self, api):
        content = self.build_content()
        context = copy.deepcopy(content["incident_propagation_graph"])
        context["entities"].append(build_bcs_pod("context-node", "other-workload", "v1"))
        context["edges"].append(
            {
                "source_id": "a",
                "target_id": "context-node",
                "edge_type": "spread",
                "properties": {"edge_id": "context-edge", "relation": "SERVICE_CALL"},
            }
        )
        content["graph_analysis"]["capabilities"]["context_expansion"] = True
        content["graph_analysis"]["context_graphs"] = [{"kind": "one_hop", "entity_ref": "a", "graph": context}]
        evidence = {
            "evidence_id": "context-errors",
            "edge_ref": "context-edge",
            "evidence_type": "metric",
            "evidence_descriptor": {"kind": "metric", "name": "errors"},
            "response": {"meta": {"status": "OK"}, "data": [{"time": 1700000000000, "value": 3}]},
        }
        content["graph_analysis"]["evidence"].append(evidence)
        snapshot = IncidentSnapshot(content)
        expanded = snapshot.generate_entity_sub_graph_from_api(1, "a", "snapshot")
        edge = next(
            edge for edge in expanded.incident_graph_edges.values() if edge.properties.get("edge_id") == "context-edge"
        )
        rendered = IncidentTopologyResource().generate_edge_info(expanded, edge)
        self.assertEqual(rendered["graph_analysis"]["evidence"], [evidence])
        self.assertEqual(target_analysis(content, edge_ref="calls")["evidence"][0]["evidence_id"], "edge-errors")
        self.assertFalse(rendered["graph_analysis"]["capabilities"]["realtime_metrics"])
        api.bkdata.get_incident_topo_by_entity.assert_not_called()

    @patch("bkmonitor.aiops.incident.models.api", new_callable=MagicMock, spec=["bkdata"])
    def test_legacy_snapshot_keeps_its_original_resource_query(self, api):
        content = self.build_content()
        content.pop("graph_analysis")
        response = copy.deepcopy(content)
        response["topo"] = response.pop("incident_propagation_graph")
        api.bkdata.get_incident_topo_by_entity.return_value = response
        snapshot = IncidentSnapshot(content)
        expanded = snapshot.generate_entity_sub_graph_from_api(1, "a", "legacy-snapshot")
        self.assertEqual(len(expanded.incident_graph_entities), 3)
        api.bkdata.get_incident_topo_by_entity.assert_called_once_with(
            incident_id=1, entity_id="a", snapshot_id="legacy-snapshot"
        )


class TestIncidentTopologyHistory(SimpleTestCase):
    def test_history_retains_categories_and_does_not_mutate_earlier_frames(self):
        resource = IncidentTopologyResource()
        first = {
            "nodes": [{"id": "service", "comboId": "0"}, {"id": "pod", "comboId": "1"}],
            "edges": [{"source": "service", "target": "pod", "edge_type": "dependency"}],
            "combos": [{"id": "0", "label": "Service"}, {"id": "1", "label": "Pod"}],
            "sub_combos": [],
        }
        second = {"nodes": [first["nodes"][0]], "edges": [], "combos": first["combos"][:1], "sub_combos": []}
        original = copy.deepcopy(first)
        complete = {"nodes": {}, "edges": {}, "sub_combos": {}, "combos": {}}
        with patch.object(resource, "generate_topology_data_from_snapshot", side_effect=[first, second, original]):
            previous, initial = resource.generate_topology_diff_from_snapshot(None, None, None, complete)
            previous, deletion = resource.generate_topology_diff_from_snapshot(None, None, previous, complete)
            self.assertEqual(first, original)
            self.assertNotIn("is_deleted", initial["nodes"][1])
            self.assertNotIn("is_deleted", initial["edges"][0])
            self.assertTrue(deletion["nodes"][0]["is_deleted"])
            self.assertEqual(set(complete["combos"]), {"0", "1"})
            _, restored = resource.generate_topology_diff_from_snapshot(None, None, previous, complete)
        self.assertEqual(restored["nodes"], [original["nodes"][1]])
        self.assertFalse(complete["nodes"]["pod"].get("is_deleted", False))
        self.assertTrue(deletion["nodes"][0]["is_deleted"])

    def test_complete_groups_are_returned_in_both_full_and_diff_modes(self):
        frames = [
            {"nodes": [{"id": "pod", "comboId": "1"}], "edges": [], "combos": [{"id": "1"}], "sub_combos": []},
            {"nodes": [{"id": "service", "comboId": "0"}], "edges": [], "combos": [{"id": "0"}], "sub_combos": []},
        ]
        snapshots = [
            SimpleNamespace(
                id=index,
                incident_id=1,
                fpp_snapshot_id=f"snapshot-{index}",
                create_time=index,
                content=SimpleNamespace(to_dict=lambda frame=frame: copy.deepcopy(frame)),
            )
            for index, frame in enumerate(frames)
        ]
        incident = SimpleNamespace(incident_id=1, snapshot=snapshots[-1])
        for only_diff in (True, False):
            with (
                self.subTest(only_diff=only_diff),
                patch("monitor_web.incident.resources.IncidentDocument.get", return_value=incident),
                patch(
                    "monitor_web.incident.resources.IncidentSnapshotDocument.list_by_incident_id",
                    return_value=snapshots,
                ),
                patch("monitor_web.incident.resources.IncidentSnapshot", side_effect=lambda content: content),
                patch.object(IncidentTopologyResource, "generate_entities_orders", return_value={}),
                patch.object(
                    IncidentTopologyResource,
                    "generate_topology_data_from_snapshot",
                    side_effect=lambda incident, snapshot: snapshot,
                ),
            ):
                # The document API exposes mapping access for sorting as well as attribute access.
                class Document(SimpleNamespace):
                    def __getitem__(self, key):
                        return getattr(self, key)

                snapshots[:] = [Document(**vars(snapshot)) for snapshot in snapshots]
                result = IncidentTopologyResource().perform_request({"id": 1, "start_time": 1, "only_diff": only_diff})
            self.assertEqual({combo["id"] for combo in result["complete"]["combos"]}, {"0", "1"})
            self.assertEqual(result["latest"]["combos"], [{"id": "0"}])
            self.assertEqual(len(result["complete"]["nodes"]), 2)
            self.assertNotIn("is_deleted", result["diff" if only_diff else "full"][0]["content"]["nodes"][0])
