"""Focused contract tests without booting the unrelated monitoring Django apps."""

import ast
import copy
import fnmatch
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INCIDENT_ID = 1001
BIZ_ID = 2
DOC_ID = "17800000001001"


def load_classes(path, namespace, selected=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = [
        node for node in tree.body if isinstance(node, ast.ClassDef) and (selected is None or node.name in selected)
    ]
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *classes],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)


class Document(SimpleNamespace):
    def to_dict(self):
        return copy.deepcopy(vars(self))


class Search:
    def __init__(self, documents, calls):
        self.documents = [copy.deepcopy(item) for item in documents]
        self.calls = calls
        self.limit = 10

    def filter(self, kind, **kwargs):
        self = copy.copy(self)
        self.calls.append(("filter", kind, kwargs))
        for key, expected in kwargs.items():
            if kind == "term":
                self.documents = [
                    item
                    for item in self.documents
                    if str(expected)
                    in [str(value) for value in (item.get(key) if isinstance(item.get(key), list) else [item.get(key)])]
                ]
            elif kind == "range":
                self.documents = [item for item in self.documents if item.get(key, 0) >= expected["gte"]]
            else:
                raise AssertionError(kind)
        return self

    def exclude(self, kind, **kwargs):
        self = copy.copy(self)
        self.calls.append(("exclude", kind, kwargs))
        for key, expected in kwargs.items():
            self.documents = [
                item
                for item in self.documents
                if not (
                    str(expected)
                    in [str(value) for value in (item.get(key) if isinstance(item.get(key), list) else [item.get(key)])]
                    if kind == "term"
                    else fnmatch.fnmatch(item.get(key, ""), expected)
                )
            ]
        return self

    def source(self, fields):
        self.calls.append(("source", fields))
        return self

    def sort(self, *fields):
        for name in reversed(fields):
            self.documents.sort(key=lambda item: item.get(name.lstrip("-"), 0), reverse=name.startswith("-"))
        return self

    def params(self, **kwargs):
        self.calls.append(("params", kwargs))
        self.limit = kwargs.get("size", self.limit)
        return self

    def execute(self):
        return SimpleNamespace(hits=[Document(**item) for item in self.documents[: self.limit]])


def snapshot_content(entity_type="BcsPod", entities=True):
    entity = {
        "entity_id": "pod-1",
        "entity_name": "pod-1",
        "entity_type": entity_type,
        "is_anomaly": False,
        "anomaly_score": 0,
        "anomaly_type": "",
        "is_root": True,
        "is_on_alert": False,
        "bk_biz_id": BIZ_ID,
        "rank_name": "rank_0",
        "dimensions": {},
        "tags": {},
        "properties": {},
        "observe_time_rage": {},
        "rca_trace_info": {},
        "component_type": "primary",
    }
    return {
        "bk_biz_id": BIZ_ID,
        "incident_alerts": [],
        "product_hierarchy_category": {
            "service": {"category_id": 1, "category_name": "service", "category_alias": "服务"}
        },
        "product_hierarchy_rank": {
            "rank_0": {"rank_id": 0, "rank_name": "rank_0", "rank_alias": "服务", "rank_category": "service"}
        },
        "incident_propagation_graph": {"entities": [entity] if entities else [], "edges": []},
    }


def incident_doc(**kwargs):
    return {
        "id": DOC_ID,
        "incident_id": str(INCIDENT_ID),
        "bk_biz_id": str(BIZ_ID),
        "extra_info": {"notice_source": "bkfara"},
        "create_time": 1780000000,
        "update_time": 1780000001,
        "feedback": SimpleNamespace(),
        **kwargs,
    }


def snapshot_doc(**kwargs):
    return {
        "id": "snapshot-1",
        "incident_id": str(INCIDENT_ID),
        "bk_biz_ids": [BIZ_ID],
        "fpp_snapshot_id": "fpp:graph-1",
        "create_time": 1780000001,
        "update_time": 1780000001,
        "content": snapshot_content(),
        **kwargs,
    }


@pytest.fixture
def context():
    state = SimpleNamespace(
        incidents=[incident_doc()],
        snapshots=[snapshot_doc()],
        calls=[],
        api_calls=[],
        panel={"enabled": True, "status": "finished"},
        tenant="tenant-a",
        tenant_allowed=True,
    )

    class IncidentDocument(Document):
        @classmethod
        def search(cls, **kwargs):
            state.calls.append(("incident_search", kwargs))
            return Search(state.incidents, state.calls)

    class IncidentSnapshotDocument:
        @classmethod
        def search(cls, **kwargs):
            state.calls.append(("snapshot_search", kwargs))
            return Search(state.snapshots, state.calls)

    class DiagnosisAPI:
        def request(self, **kwargs):
            state.api_calls.append((kwargs, self.TIMEOUT))
            if isinstance(state.panel, Exception):
                raise state.panel
            return {"incident_topology": state.panel}

    class Field:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    namespace = {
        "copy": copy,
        "defaultdict": defaultdict,
        "dataclass": dataclass,
        "asdict": asdict,
        "field": field,
        "CustomEnum": Enum,
        "IncidentDocument": IncidentDocument,
        "IncidentEntityNotFoundError": ValueError,
        "Resource": object,
        "serializers": SimpleNamespace(Serializer=object, IntegerField=Field),
        "logger": logging.getLogger(__name__),
        "get_request_tenant_id": lambda **kwargs: state.tenant,
        "is_biz_in_tenant": lambda biz, tenant: state.tenant_allowed,
        "IncidentSnapshotDocument": IncidentSnapshotDocument,
        "GetIncidentDiagnosisResource": DiagnosisAPI,
        "EventStatus": SimpleNamespace(RECOVERED="RECOVERED", CLOSED="CLOSED"),
    }
    load_classes(
        PROJECT_ROOT / "constants/incident.py",
        namespace,
        {
            "IncidentGraphEdgeType",
            "IncidentGraphEdgeEventType",
            "IncidentGraphEdgeEventDirection",
            "IncidentGraphComponentType",
        },
    )
    load_classes(PROJECT_ROOT / "bkmonitor/aiops/incident/models.py", namespace)
    load_classes(
        PROJECT_ROOT / "packages/monitor_web/incident/resources.py",
        namespace,
        {"IncidentBaseResource", "IncidentTopologyAvailabilityResource"},
    )
    state.resource = namespace["IncidentTopologyAvailabilityResource"]()
    state.run = lambda: state.resource.perform_request({"incident_id": INCIDENT_ID, "bk_biz_id": BIZ_ID})
    return state


def test_single_node_without_edges_is_available(context):
    assert context.run() == {
        "incident_id": INCIDENT_ID,
        "bk_biz_id": BIZ_ID,
        "incident_doc_id": DOC_ID,
        "has_incident_topology": True,
        "topology_status": "available",
    }
    assert context.api_calls == [({"incident_id": INCIDENT_ID, "bk_biz_id": BIZ_ID}, 3)]
    assert ("filter", "term", {"bk_biz_id": str(BIZ_ID)}) in context.calls
    assert ("filter", "term", {"bk_biz_ids": str(BIZ_ID)}) in context.calls


@pytest.mark.parametrize(
    "content", [snapshot_content(entities=False), snapshot_content("BcsService"), snapshot_content("BcsWorkload")]
)
def test_non_renderable_graph_is_empty_without_remote_call(context, content):
    context.snapshots[0]["content"] = content
    assert context.run()["topology_status"] == "empty"
    assert not context.api_calls


@pytest.mark.parametrize(
    "panel,status",
    [
        ({"enabled": False, "status": "finished"}, "unavailable"),
        ({"enabled": True, "status": "running"}, "unavailable"),
        ({"enabled": True, "status": "failed"}, "unavailable"),
        ({"enabled": "true", "status": "finished"}, "unknown"),
        ({}, "unknown"),
        (None, "unknown"),
        (TimeoutError(), "unknown"),
    ],
)
def test_graph_alone_does_not_override_target_panel_gate(context, panel, status):
    context.panel = panel
    result = context.run()
    assert result["has_incident_topology"] is False
    assert result["topology_status"] == status


def test_filtered_newer_snapshots_do_not_hide_latest_graph(context):
    context.snapshots.extend(
        [
            snapshot_doc(fpp_snapshot_id="fpp:None", create_time=1780000003, content={}),
            snapshot_doc(fpp_snapshot_id="fpp:graph:llm_summary", create_time=1780000004, content={}),
        ]
    )
    assert context.run()["has_incident_topology"] is True


def test_latest_empty_graph_does_not_reuse_older_result(context):
    context.snapshots.append(snapshot_doc(create_time=1780000005, content=snapshot_content(entities=False)))
    assert context.run()["topology_status"] == "empty"
    assert not context.api_calls


@pytest.mark.parametrize("tenant,allowed", [(None, True), ("tenant-b", False)])
def test_untrusted_or_wrong_tenant_cannot_query_documents(context, tenant, allowed):
    context.tenant, context.tenant_allowed = tenant, allowed
    assert context.run()["topology_status"] == "unavailable"
    assert not context.calls


def test_other_incident_or_business_documents_are_not_used(context):
    context.incidents = [incident_doc(incident_id="999"), incident_doc(bk_biz_id="3")]
    assert context.run()["topology_status"] == "empty"
    assert not context.api_calls


def test_legacy_source_is_not_a_bkfara_topology(context):
    context.incidents[0]["extra_info"] = {"notice_source": "bkdata"}
    assert context.run()["topology_status"] == "empty"
    assert not context.api_calls


def test_same_number_from_two_sources_has_no_proven_snapshot_ownership(context):
    context.incidents.append(incident_doc(extra_info={"notice_source": "bkdata"}))
    assert context.run()["topology_status"] == "unknown"
    assert not context.api_calls


def test_bounded_source_lookup_does_not_claim_empty(context):
    context.incidents = [incident_doc() for _ in range(21)]
    assert context.run()["topology_status"] == "unknown"


@pytest.mark.parametrize("doc_id", ["1001", "17800000001002", "bad-id"])
def test_invalid_document_identity_is_rejected(context, doc_id):
    context.incidents[0]["id"] = doc_id
    result = context.run()
    assert result["topology_status"] == "unknown"
    assert result["incident_doc_id"] == ""


@pytest.mark.parametrize("changes", [{"incident_id": "999"}])
def test_snapshot_must_belong_to_incident_and_business(context, changes):
    context.snapshots[0].update(changes)
    assert context.run()["topology_status"] == "empty"


def test_same_day_snapshot_predating_incident_is_unknown(context):
    context.snapshots[0]["create_time"] = 1779999999
    assert context.run()["topology_status"] == "unknown"


def test_same_incident_number_from_other_business_is_unknown(context):
    context.snapshots.append(snapshot_doc(bk_biz_ids=[3], create_time=1780000005))
    result = context.run()
    assert result["topology_status"] == "unknown"
    assert result["has_incident_topology"] is False
    assert not context.api_calls


@pytest.mark.parametrize(
    "reason",
    [
        "feature_disabled",
        "insufficient_data",
        "not_scheduled",
        "execution_failed",
        "running",
        "no_result",
    ],
)
def test_page_reason_takes_precedence_over_finished_gate(context, reason):
    context.panel["reason"] = reason
    assert context.run()["topology_status"] == "unavailable"


def test_snapshot_content_wrong_business_is_unknown(context):
    context.snapshots[0]["content"]["bk_biz_id"] = 3
    assert context.run()["topology_status"] == "unknown"


def test_malformed_graph_is_unknown(context):
    context.snapshots[0]["content"]["product_hierarchy_rank"] = {}
    assert context.run()["topology_status"] == "unknown"


def test_query_error_is_unknown(context):
    context.resource._find_incident = lambda *args: (_ for _ in ()).throw(TimeoutError())
    assert context.run()["topology_status"] == "unknown"


def test_positive_short_id_request_contract(context):
    serializer = context.resource.RequestSerializer
    assert serializer.incident_id.kwargs["min_value"] == 1
    assert serializer.incident_id.kwargs["max_value"] == 9999999999
    assert serializer.bk_biz_id.kwargs["min_value"] == 1


def test_internal_gateway_route_and_permission_contract():
    path = PROJECT_ROOT / "support-files/apigw/resources/internal/app/incident.yaml"
    config = yaml.safe_load(path.read_text())["paths"]["/app/incident/topology_availability/"]["get"]
    gateway = config["x-bk-apigateway-resource"]
    assert gateway["isPublic"] is False and gateway["allowApplyPermission"] is False
    assert gateway["authConfig"] == {
        "appVerifiedRequired": True,
        "userVerifiedRequired": False,
        "resourcePermissionRequired": True,
    }
    assert gateway["backend"]["path"] == "/api/v4/incident/topology_availability/"
    namespace = {
        "ResourceViewSet": object,
        "ResourceRoute": lambda *args, **kwargs: (args, kwargs),
        "IncidentTopologyAvailabilityResource": object,
    }
    load_classes(PROJECT_ROOT / "kernel_api/views/v4/incident.py", namespace)
    assert namespace["IncidentViewSet"].resource_routes == [(("GET", object), {"endpoint": "topology_availability"})]
    assert "from .incident import *" in (PROJECT_ROOT / "kernel_api/views/v4/__init__.py").read_text()
