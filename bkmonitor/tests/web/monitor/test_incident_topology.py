"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from bkmonitor.aiops.incident.models import IncidentSnapshot
from monitor_web.incident.resources import IncidentTopologyMenuResource


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
        self.assertEqual(aggregated_entity.entity_name, "部署版本: v1")
        self.assertEqual(aggregated_entity.properties["aggregate_type"], "resource_version")
        self.assertEqual(aggregated_entity.properties["resource_version"], "v1")
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
