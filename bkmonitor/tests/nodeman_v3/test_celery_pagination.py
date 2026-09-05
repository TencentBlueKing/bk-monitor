import uuid
from types import SimpleNamespace

from monitor_web.nodeman_integration.v3 import tasks
from monitor_web.models.node_man import NodeManOperationStatus


class FakeValues:
    def __init__(self, values):
        self.values = values

    def first(self):
        return self.values[0] if self.values else None

    def __iter__(self):
        return iter(self.values)

    def __getitem__(self, item):
        return self.values[item]


class FakeQuerySet:
    def __init__(self, values):
        self.values = list(values)

    def filter(self, *args, **conditions):
        del args
        values = self.values
        if "pk__gt" in conditions:
            cursor = _coerce(conditions["pk__gt"], values)
            values = [value for value in values if value > cursor]
        if "pk__lte" in conditions:
            upper_bound = _coerce(conditions["pk__lte"], values or self.values)
            values = [value for value in values if value <= upper_bound]
        return FakeQuerySet(values)

    def order_by(self, field):
        return FakeQuerySet(sorted(self.values, reverse=field.startswith("-")))

    def values_list(self, field, flat):
        assert field == "pk"
        assert flat is True
        return FakeValues(self.values)

    def distinct(self):
        return FakeQuerySet(dict.fromkeys(self.values))


class FakeManager:
    def __init__(self, values):
        self.values = values

    def filter(self, *args, **conditions):
        del args, conditions
        return FakeQuerySet(self.values)


def _coerce(value, examples):
    if examples and isinstance(examples[0], uuid.UUID) and not isinstance(value, uuid.UUID):
        return uuid.UUID(str(value))
    if examples and isinstance(examples[0], int):
        return int(value)
    return value


def test_operation_poller_cursor_pages_cover_all_records_without_fixed_head_starvation(monkeypatch):
    operation_ids = [uuid.UUID(int=index) for index in range(1, 451)]
    monkeypatch.setattr(tasks, "MonitorNodeManOperation", SimpleNamespace(objects=FakeManager(operation_ids)))
    polled = []
    continuations = []
    monkeypatch.setattr(tasks.poll_operation, "apply_async", lambda **kwargs: polled.append(kwargs))
    monkeypatch.setattr(tasks.poll_pending_operations, "apply_async", lambda **kwargs: continuations.append(kwargs))

    tasks.poll_pending_operations.run(limit=200)
    first = continuations.pop()
    tasks.poll_pending_operations.run(**first["kwargs"])
    second = continuations.pop()
    tasks.poll_pending_operations.run(**second["kwargs"])

    assert len(polled) == 450
    assert len({call["args"][0] for call in polled}) == 450
    assert continuations == []
    assert first["kwargs"] == {
        "limit": 200,
        "cursor": str(operation_ids[199]),
        "upper_bound": str(operation_ids[-1]),
    }


def test_monitor_does_not_register_a_periodic_target_reconciliation_loop():
    assert not hasattr(tasks, "reconcile_active_bindings")


class FakeOperationLookup:
    def __init__(self, operation):
        self.operation = operation

    def select_related(self, *args):
        del args
        return self

    def prefetch_related(self, *args):
        del args
        return self

    def get(self, **kwargs):
        del kwargs
        return self.operation


def test_terminal_operation_with_held_lease_is_finalized_without_remote_query(monkeypatch):
    workflows = [SimpleNamespace(workflow_id="workflow-1")]
    operation = SimpleNamespace(
        id=uuid.uuid4(),
        status=NodeManOperationStatus.SUCCESS,
        workflows=SimpleNamespace(all=lambda: workflows),
    )
    monkeypatch.setattr(
        tasks,
        "MonitorNodeManOperation",
        SimpleNamespace(objects=FakeOperationLookup(operation)),
    )
    finalized = []
    monkeypatch.setattr(
        tasks,
        "finalize_target_operation",
        lambda current, current_workflows: finalized.append((current, current_workflows)) or True,
    )

    result = tasks.poll_operation.run(str(operation.id))

    assert result == {
        "operation_id": str(operation.id),
        "status": NodeManOperationStatus.SUCCESS,
        "finalized": True,
    }
    assert finalized == [(operation, workflows)]
