"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from apm.core.discover.node import NodeDiscover
from apm.models import ApmTopoDiscoverRule
from constants.apm import TelemetryDataType

BK_BIZ_ID = 2
APP_NAME = "demo_app"
SERVICE_NAME = "demo-service"
BCS_CLUSTER_ID = "BCS-K8S-DEMO"
NAMESPACE = "demo-namespace"
POD_NAME = "demo-service-0"
WORKLOAD_TYPE = "StatefulSet"
WORKLOAD_NAME = "demo-service"


class FakeQuerySet:
    def __init__(self, items):
        self.items = items

    def values(self, *fields):
        return [{field: item[field] for field in fields} for item in self.items]

    def count(self):
        return len(self.items)

    def delete(self):
        self.items.clear()

    def order_by(self, *_fields):
        return self

    def values_list(self, field, flat=False):
        values = [item[field] for item in self.items]
        return values if flat else [(value,) for value in values]


class FakeTopoNode:
    EXPIRED_DAYS = NodeDiscover.model.EXPIRED_DAYS
    objects = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeTopoNodeManager:
    def __init__(self, nodes):
        self.nodes = {node["topo_key"]: node for node in nodes}

    def filter(self, **kwargs):
        if any(key.endswith("__lte") for key in kwargs):
            return FakeQuerySet([])

        matched_nodes = []
        for node in self.nodes.values():
            if all(node.get(key) == value for key, value in kwargs.items()):
                matched_nodes.append(node)
        return FakeQuerySet(matched_nodes)

    def bulk_update(self, instances, fields, batch_size=None):
        for instance in instances:
            node = self.nodes[instance.topo_key]
            for field in fields:
                node[field] = getattr(instance, field)

    def bulk_create(self, instances, batch_size=None):
        for instance in instances:
            node = instance.__dict__.copy()
            node.setdefault("id", len(self.nodes) + 1)
            self.nodes[node["topo_key"]] = node


class FakeBCSPod:
    objects = None


class FakeBCSPodManager:
    def __init__(self, pods):
        self.pods = pods
        self.filter_calls = []

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        matched_pods = [
            pod
            for pod in self.pods
            if pod["bk_biz_id"] == kwargs["bk_biz_id"]
            and pod["bcs_cluster_id"] in kwargs["bcs_cluster_id__in"]
            and pod["namespace"] in kwargs["namespace__in"]
            and pod["name"] in kwargs["name__in"]
        ]
        return FakeQuerySet(matched_pods)


class OneSpanPerBatchNodeDiscover(NodeDiscover):
    HANDLE_SPANS_BATCH_SIZE = 1


def build_rules():
    return [ApmTopoDiscoverRule(bk_biz_id=0, app_name="", **rule) for rule in ApmTopoDiscoverRule.COMMON_RULE]


def build_topo_node(extra_data, platform=None, source=None):
    return {
        "id": 1,
        "bk_biz_id": BK_BIZ_ID,
        "app_name": APP_NAME,
        "topo_key": SERVICE_NAME,
        "extra_data": extra_data,
        "platform": platform or {},
        "system": [],
        "sdk": [],
        "source": source or [TelemetryDataType.TRACE.value],
    }


def build_bcs_pod():
    return {
        "bk_biz_id": BK_BIZ_ID,
        "bcs_cluster_id": BCS_CLUSTER_ID,
        "namespace": NAMESPACE,
        "name": POD_NAME,
        "workload_type": WORKLOAD_TYPE,
        "workload_name": WORKLOAD_NAME,
    }


def build_k8s_other_span():
    return {
        "attributes": {
            "apdex_type": "satisfied",
            "rpc.namespace": NAMESPACE,
            "rpc.env_name": "demo_env",
            "tableName": "DemoTable",
        },
        "elapsed_time": 18342,
        "end_time": 1782385804631576,
        "kind": 3,
        "links": [],
        "parent_span_id": "",
        "resource": {
            "bk.instance.id": f"java:{SERVICE_NAME}:",
            "k8s.bcs.cluster.id": BCS_CLUSTER_ID,
            "k8s.namespace.name": NAMESPACE,
            "k8s.pod.ip": "127.0.0.1",
            "k8s.pod.name": POD_NAME,
            "net.host.ip": "127.0.0.1",
            "net.host.name": SERVICE_NAME,
            "net.host.port": "0",
            "service.name": SERVICE_NAME,
            "telemetry.sdk.language": "java",
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.version": "1.24.0",
        },
        "span_id": "a7f15b24146d8c1c",
        "span_name": "tcaplus",
        "start_time": 1782385804613234,
        "status": {"code": 2, "message": ""},
        "time": "1782385808000",
        "trace_id": "4bc0c0a20ea0cd49a8ce239c9684553c",
        "trace_state": "",
    }


def build_other_span_without_platform():
    span = build_k8s_other_span()
    for key in ["k8s.bcs.cluster.id", "k8s.namespace.name", "k8s.pod.ip", "k8s.pod.name", "net.host.ip"]:
        span["resource"].pop(key)
    return span


def run_discover(existing_node, spans, pods=None, discover_cls=NodeDiscover):
    if isinstance(spans, dict):
        spans = [spans]

    topo_manager = FakeTopoNodeManager([existing_node])
    pod_manager = FakeBCSPodManager(pods or [build_bcs_pod()])
    FakeTopoNode.objects = topo_manager
    FakeBCSPod.objects = pod_manager

    with (
        mock.patch("apm.core.discover.node.TopoNode", FakeTopoNode),
        mock.patch("apm.core.discover.node.BCSPod", FakeBCSPod),
        mock.patch.object(discover_cls, "model", FakeTopoNode),
        mock.patch.object(discover_cls, "_validate_bk_biz_id", return_value=BK_BIZ_ID),
        mock.patch.object(ApmTopoDiscoverRule, "get_application_rule", return_value=build_rules()),
    ):
        discover_cls(BK_BIZ_ID, APP_NAME).discover(spans)

    return topo_manager.nodes[SERVICE_NAME], pod_manager


def assert_k8s_workload(platform):
    workload = platform["workloads"][0]
    assert platform["name"] == ApmTopoDiscoverRule.APM_TOPO_PLATFORM_K8S
    assert workload["bcs_cluster_id"] == BCS_CLUSTER_ID
    assert workload["namespace"] == NAMESPACE
    assert workload["kind"] == WORKLOAD_TYPE
    assert workload["name"] == WORKLOAD_NAME
    assert isinstance(workload["updated_at"], int)


def test_existing_other_topo_node_updates_k8s_workloads():
    existing_node = build_topo_node(
        {
            "category": ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER,
            "kind": ApmTopoDiscoverRule.TOPO_SERVICE,
            "predicate_value": None,
            "service_language": "java",
        }
    )

    topo_node, pod_manager = run_discover(existing_node, build_k8s_other_span())

    assert pod_manager.filter_calls[-1]["name__in"] == {POD_NAME}
    assert topo_node["extra_data"]["category"] == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER
    assert topo_node["source"] == [TelemetryDataType.TRACE.value]
    assert topo_node["sdk"] == [
        {"name": "opentelemetry", "extra_data": {"resource.telemetry.sdk.name": "opentelemetry"}}
    ]
    assert_k8s_workload(topo_node["platform"])


def test_pending_other_topo_node_update_merges_later_k8s_platform():
    existing_node = build_topo_node(
        {
            "category": ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER,
            "kind": ApmTopoDiscoverRule.TOPO_SERVICE,
            "predicate_value": None,
            "service_language": "java",
        }
    )

    topo_node, _ = run_discover(
        existing_node,
        [build_other_span_without_platform(), build_k8s_other_span()],
        discover_cls=OneSpanPerBatchNodeDiscover,
    )

    assert_k8s_workload(topo_node["platform"])


def test_existing_non_other_topo_node_is_not_downgraded_by_other_span():
    rpc_extra_data = {
        "category": ApmTopoDiscoverRule.APM_TOPO_CATEGORY_RPC,
        "kind": ApmTopoDiscoverRule.TOPO_SERVICE,
        "predicate_value": "grpc",
        "service_language": "java",
    }
    existing_node = build_topo_node(rpc_extra_data, source=[TelemetryDataType.METRIC.value])

    topo_node, _ = run_discover(existing_node, build_k8s_other_span())

    assert topo_node["extra_data"] == rpc_extra_data
    assert topo_node["source"] == [TelemetryDataType.METRIC.value, TelemetryDataType.TRACE.value]
    assert_k8s_workload(topo_node["platform"])


def test_existing_non_other_topo_node_is_not_downgraded_by_incomplete_other_span():
    rpc_extra_data = {
        "category": ApmTopoDiscoverRule.APM_TOPO_CATEGORY_RPC,
        "kind": ApmTopoDiscoverRule.TOPO_SERVICE,
        "predicate_value": "grpc",
        "service_language": "java",
    }
    existing_platform = {
        "name": ApmTopoDiscoverRule.APM_TOPO_PLATFORM_K8S,
        "extra_data": {},
        "workloads": [
            {
                "bcs_cluster_id": BCS_CLUSTER_ID,
                "namespace": NAMESPACE,
                "kind": WORKLOAD_TYPE,
                "name": WORKLOAD_NAME,
                "updated_at": 1782385800,
            }
        ],
    }
    existing_node = build_topo_node(rpc_extra_data, platform=existing_platform, source=[TelemetryDataType.METRIC.value])

    topo_node, _ = run_discover(existing_node, build_other_span_without_platform())

    assert topo_node["extra_data"] == rpc_extra_data
    assert topo_node["source"] == [TelemetryDataType.METRIC.value, TelemetryDataType.TRACE.value]
    assert topo_node["platform"] == existing_platform


def test_existing_other_topo_node_keeps_platform_when_span_has_no_platform_fields():
    existing_platform = {
        "name": ApmTopoDiscoverRule.APM_TOPO_PLATFORM_K8S,
        "extra_data": {},
        "workloads": [
            {
                "bcs_cluster_id": BCS_CLUSTER_ID,
                "namespace": NAMESPACE,
                "kind": WORKLOAD_TYPE,
                "name": WORKLOAD_NAME,
                "updated_at": 1782385800,
            }
        ],
    }
    existing_node = build_topo_node(
        {
            "category": ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER,
            "kind": ApmTopoDiscoverRule.TOPO_SERVICE,
            "predicate_value": None,
            "service_language": "java",
        },
        platform=existing_platform,
    )

    topo_node, _ = run_discover(existing_node, build_other_span_without_platform())

    assert topo_node["platform"] == existing_platform
