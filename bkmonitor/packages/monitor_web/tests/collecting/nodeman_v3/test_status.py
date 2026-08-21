from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.client import NodeManV3RequestContext
from monitor_web.models.node_man import (
    NodeManOperationStatus,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
)
from monitor_web.nodeman_integration.v3.status import (
    aggregate_workflow_status,
    fetch_workflow_statuses,
    is_current_generation,
    normalize_workflow_status,
    refresh_operation_status,
)


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("running", NodeManWorkflowStatus.RUNNING),
        ("success", NodeManWorkflowStatus.SUCCESS),
        ("failed", NodeManWorkflowStatus.FAILED),
        ("partial_failed", NodeManWorkflowStatus.PARTIAL_FAILED),
        ("cancelled", NodeManWorkflowStatus.CANCELLED),
        ("unexpected", NodeManWorkflowStatus.UNKNOWN),
        (None, NodeManWorkflowStatus.UNKNOWN),
    ],
)
def test_normalize_workflow_status(raw_status, expected):
    assert normalize_workflow_status(raw_status) == expected


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([NodeManWorkflowStatus.SUCCESS], NodeManOperationStatus.SUCCESS),
        ([NodeManWorkflowStatus.FAILED], NodeManOperationStatus.FAILED),
        ([NodeManWorkflowStatus.CANCELLED], NodeManOperationStatus.CANCELLED),
        ([NodeManWorkflowStatus.RUNNING, NodeManWorkflowStatus.SUCCESS], NodeManOperationStatus.RUNNING),
        ([NodeManWorkflowStatus.SUCCESS, NodeManWorkflowStatus.FAILED], NodeManOperationStatus.PARTIAL_FAILED),
        ([NodeManWorkflowStatus.PARTIAL_FAILED], NodeManOperationStatus.PARTIAL_FAILED),
        ([NodeManWorkflowStatus.UNKNOWN, NodeManWorkflowStatus.SUCCESS], NodeManOperationStatus.UNKNOWN),
        ([], NodeManOperationStatus.UNKNOWN),
    ],
)
def test_aggregate_workflow_status(statuses, expected):
    assert aggregate_workflow_status(statuses) == expected


class FakeWorkflowClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list_workflows(self, payload, *, context):
        self.calls.append((payload, context))
        offset = payload["page"]["offset"]
        limit = payload["page"]["limit"]
        return {"total": len(self.items), "items": self.items[offset : offset + limit]}


def test_workflow_query_is_paginated_by_workflow_not_by_host():
    items = [
        {"workflow_id": f"workflow-{index}", "status": "success", "bk_host_id": list(range(100))}
        for index in range(205)
    ]
    client = FakeWorkflowClient(items)
    context = NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2)

    result = fetch_workflow_statuses(
        client,
        [item["workflow_id"] for item in items],
        context=context,
        page_size=100,
    )

    assert len(result) == 205
    assert len(client.calls) == 3
    assert [call[0]["page"] for call in client.calls] == [
        {"offset": 0, "limit": 100},
        {"offset": 100, "limit": 100},
        {"offset": 200, "limit": 100},
    ]
    assert all(
        call[0]["exact_include_conditions"]["workflow_id"] == [item["workflow_id"] for item in items]
        for call in client.calls
    )


def test_stale_generation_cannot_write_current_configuration_state():
    current = SimpleNamespace(binding=SimpleNamespace(generation=3), generation=3)
    stale = SimpleNamespace(binding=SimpleNamespace(generation=4), generation=3)

    assert is_current_generation(current) is True
    assert is_current_generation(stale) is False


@pytest.mark.parametrize(("binding_generation", "callback_count"), [(3, 1), (4, 0)])
def test_terminal_callback_only_updates_current_generation(monkeypatch, binding_generation, callback_count):
    workflows = [
        SimpleNamespace(
            workflow_id="workflow-1",
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
            raw_status="",
            normalized_status="pending",
            last_synced_at=None,
        ),
        SimpleNamespace(
            workflow_id="workflow-2",
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
            raw_status="",
            normalized_status="pending",
            last_synced_at=None,
        ),
    ]
    transitions = []
    operation = SimpleNamespace(
        status=NodeManOperationStatus.RUNNING,
        generation=3,
        binding=SimpleNamespace(generation=binding_generation),
        workflows=SimpleNamespace(all=lambda: workflows),
        transition_to=lambda status: transitions.append(status),
    )
    client = FakeWorkflowClient(
        [
            {"workflow_id": "workflow-1", "status": "success", "bk_host_id": [1]},
            {"workflow_id": "workflow-2", "status": "success", "bk_host_id": [2]},
        ]
    )
    bulk_updates = []
    callbacks = []
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.status.MonitorNodeManWorkflow.objects.bulk_update",
        lambda objects, fields: bulk_updates.append((objects, fields)),
    )

    result = refresh_operation_status(
        operation,
        client,
        context=NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2),
        on_current_terminal=lambda *args: callbacks.append(args),
    )

    assert result.status == NodeManOperationStatus.SUCCESS
    assert result.stale_generation is (binding_generation != 3)
    assert transitions == [NodeManOperationStatus.SUCCESS]
    assert len(bulk_updates) == 1
    assert len(callbacks) == callback_count


@pytest.mark.parametrize(
    ("dispatch_status", "expected"),
    [
        (NodeManWorkflowDispatchStatus.UNKNOWN, NodeManOperationStatus.UNKNOWN),
        (NodeManWorkflowDispatchStatus.SUBMITTING, NodeManOperationStatus.UNKNOWN),
        (NodeManWorkflowDispatchStatus.PREPARED, NodeManOperationStatus.RUNNING),
        (NodeManWorkflowDispatchStatus.DEFINITE_FAILED, NodeManOperationStatus.PARTIAL_FAILED),
    ],
)
def test_unsubmitted_batch_evidence_participates_in_operation_aggregation(
    monkeypatch,
    dispatch_status,
    expected,
):
    workflows = [
        SimpleNamespace(
            workflow_id="workflow-1",
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
            raw_status="",
            normalized_status=NodeManWorkflowStatus.RUNNING,
            last_synced_at=None,
        ),
        SimpleNamespace(
            workflow_id=None,
            dispatch_status=dispatch_status,
            raw_status="",
            normalized_status=NodeManWorkflowStatus.PENDING,
            last_synced_at=None,
        ),
    ]
    operation = SimpleNamespace(
        status=NodeManOperationStatus.RUNNING,
        generation=3,
        binding=SimpleNamespace(generation=3),
        workflows=SimpleNamespace(all=lambda: workflows),
        transition_to=lambda status: setattr(operation, "status", status),
    )
    client = FakeWorkflowClient([{"workflow_id": "workflow-1", "status": "success"}])
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.status.MonitorNodeManWorkflow.objects.bulk_update",
        lambda *args, **kwargs: None,
    )

    result = refresh_operation_status(
        operation,
        client,
        context=NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2),
    )

    assert result.status == expected
    assert client.calls[0][0]["exact_include_conditions"]["workflow_id"] == ["workflow-1"]


def test_terminal_callback_runs_for_stale_generation_so_its_lease_can_be_released(monkeypatch):
    workflow = SimpleNamespace(
        workflow_id="workflow-1",
        dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
        raw_status="",
        normalized_status=NodeManWorkflowStatus.RUNNING,
        last_synced_at=None,
    )
    transitions = []
    operation = SimpleNamespace(
        status=NodeManOperationStatus.RUNNING,
        generation=3,
        binding=SimpleNamespace(generation=4),
        workflows=SimpleNamespace(all=lambda: [workflow]),
        transition_to=lambda status: transitions.append(status),
    )
    callbacks = []
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.status.MonitorNodeManWorkflow.objects.bulk_update",
        lambda *args, **kwargs: None,
    )

    result = refresh_operation_status(
        operation,
        FakeWorkflowClient([{"workflow_id": "workflow-1", "status": "success"}]),
        context=NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2),
        on_terminal=lambda *args: callbacks.append(args),
    )

    assert result.stale_generation is True
    assert transitions == [NodeManOperationStatus.SUCCESS]
    assert len(callbacks) == 1
