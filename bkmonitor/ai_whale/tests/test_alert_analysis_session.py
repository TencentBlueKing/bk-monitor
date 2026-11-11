"""Run without databases; upstream persistence and Redis are explicit test doubles."""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ai_whale.alert_analysis_session import (
    SessionPreparationError,
    ensure_session,
    history,
    owned_alert_id,
    session_code_for,
)


def ok(data):
    return {"result": True, "data": data}


class Missing(Exception):
    response_status_code = 404


class Store:
    def __init__(self):
        self.session = None
        self.records = []
        self.creates = 0
        self.lose_write_response = False
        self.drop_write = False

    def retrieve_chat_session(self, session_code):
        if self.session is None:
            raise Missing()
        return ok(self.session)

    def create_chat_session(self, params, username):
        self.creates += 1
        self.session = {**params, "username": username}
        return ok(self.session)

    def get_chat_session_contents(self, session_code):
        return ok(deepcopy(self.records))

    def create_chat_session_content(self, params):
        if not self.drop_write:
            self.records.append({**deepcopy(params), "id": len(self.records) + 1})
        if self.lose_write_response:
            self.lose_write_response = False
            raise TimeoutError()
        return ok({})


class Lock:
    busy = False
    valid = True

    @contextmanager
    def lock(self, key, **kwargs):
        if self.busy:
            raise RuntimeError("busy")
        self.busy = True
        try:
            yield SimpleNamespace(owned=lambda: self.valid)
        finally:
            self.busy = False


@pytest.fixture
def setup():
    store, lock = Store(), Lock()
    context = {
        "subject": {"type": "alert", "alert_id": "123"},
        "source": {"type": "incident_analysis", "incident_id": 7},
        "analysis": {"status": "finished", "sub_panels": {"summary": {"contents": "evidence"}}},
    }

    def run():
        return ensure_session(
            store,
            lock,
            context_factory=lambda: deepcopy(context),
            alert_id="123",
            username="alice",
            tenant_id="tenant",
            agent_code="monitor",
        )

    return store, lock, context, run


def test_identity_stable_and_isolated():
    code = session_code_for("123", "中文用户", "tenant")
    assert code == session_code_for("123", "中文用户", "tenant")
    assert owned_alert_id(code, "中文用户", "tenant") == "123"
    for user, tenant in [("other", "tenant"), ("中文用户", "other")]:
        with pytest.raises(ValueError):
            owned_alert_id(code, user, tenant)
    assert len(session_code_for("9" * 32, "alice", "tenant")) <= 64
    assert owned_alert_id("legacy-session", "alice", "tenant") is None


@pytest.mark.parametrize("alert", ["0", "01", "-1", "1.5", "1/2", "9" * 33])
def test_bad_alert_ids(alert):
    with pytest.raises(ValueError):
        session_code_for(alert, "alice", "tenant")


def test_prepare_readback_and_retry(setup):
    store, _, _, run = setup
    first = run()
    assert first == run()
    assert first["status"] == "ready"
    assert store.creates == len(store.records) == 1
    record = store.records[0]
    envelope = record["property"]["extra"]["alert_analysis_message"]
    assert record["status"] == "complete"
    assert envelope["payload"]["subject"]["type"] == "alert"
    assert envelope["payload"]["source"]["type"] == "incident_analysis"
    assert "不能直接认定" in record["content"]
    assert "evidence" in record["content"]


def test_changed_then_reverted_analysis_appends_current_snapshot(setup):
    store, _, context, run = setup
    first = run()
    context["analysis"]["status"] = "running"
    second = run()
    context["analysis"]["status"] = "finished"
    third = run()
    assert len({x["snapshot_event_id"] for x in [first, second, third]}) == 3
    assert run() == third
    assert len(store.records) == 3


def test_ambiguous_write_retry_does_not_duplicate(setup):
    store, _, _, run = setup
    store.lose_write_response = True
    with pytest.raises(TimeoutError):
        run()
    assert run()["status"] == "ready"
    assert len(store.records) == 1


def test_write_success_without_readback_is_not_ready(setup):
    store, _, _, run = setup
    store.drop_write = True
    with pytest.raises(SessionPreparationError):
        run()


def test_non_404_never_creates_session(setup):
    store, _, _, run = setup

    def denied(**kwargs):
        raise PermissionError()

    store.retrieve_chat_session = denied
    with pytest.raises(PermissionError):
        run()
    assert store.creates == 0


def test_expired_lock_does_not_write(setup):
    store, lock, _, run = setup
    lock.valid = False
    with pytest.raises(SessionPreparationError):
        run()
    assert not store.records


def test_busy_lock_does_not_fetch_or_write(setup):
    store, lock, _, run = setup
    lock.busy = True
    with pytest.raises(RuntimeError):
        run()
    assert not store.records and not store.creates


@pytest.mark.parametrize("data", [{"results": [], "next": "page2"}, {"results": [], "count": 5}, None, [None]])
def test_incomplete_or_invalid_history_fails_closed(data):
    with pytest.raises(SessionPreparationError):
        history(SimpleNamespace(get_chat_session_contents=lambda **kw: ok(data)), "code")


def test_no_incident_is_explicit_not_finished(setup):
    store, _, context, run = setup
    context["source"] = None
    context["analysis"] = {"status": "unavailable", "reason": "no_related_incident", "sub_panels": {}}
    result = run()
    assert result["analysis_status"] == "unavailable"
    assert result["source"] is None
    assert "no_related_incident" in store.records[0]["content"]


def test_history_order_does_not_change_deduplication(setup):
    store, _, context, run = setup
    run()
    context["analysis"]["status"] = "running"
    latest = run()
    store.records.reverse()
    assert run() == latest
    assert len(store.records) == 2
