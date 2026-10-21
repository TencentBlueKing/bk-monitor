"""Exercise request propagation, real provider factories and concurrent HTTP calls."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock


from bkmonitor.iam import ActionEnum
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.concurrency import bind_current_context
from bkmonitor.iam.permission import Permission
from bkmonitor.utils.local import local
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from iam_engine.v4.config import V4Options
from iam_engine.v4.exceptions import V4ResponseError


def permission():
    instance = Permission(username="alice", bk_tenant_id="tenant-a")
    provider = build_provider(
        "v4",
        tenant_id="tenant-a",
        username="alice",
        options=replace(V4Options.from_settings(), batch_chunk_size=1, batch_max_workers=2),
    )
    provider.resolver = SimpleNamespace(resolve=lambda resource, **kwargs: resource)
    instance._providers = {"v4": provider}
    instance.skip_check = False
    instance.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode.V4)
    return instance


def response(data):
    result = Mock(status_code=200, content=b"{}")
    result.json.return_value = {"data": data}
    return result


def batch(instance, ids=("1", "2")):
    return instance.batch_is_allowed([ActionEnum.VIEW_BUSINESS], [[ResourceInstance("space", rid)] for rid in ids])


def test_factory_instances_share_cache_and_distinct_pages_stay_parallel(monkeypatch):
    monkeypatch.setattr(local, "current_request", SimpleNamespace(), raising=False)
    rendezvous = Barrier(2)

    def transport(**kwargs):
        # Both distinct pages must reach HTTP together, including after request change.
        rendezvous.wait(timeout=5)
        rid = kwargs["json"]["resources"][0]["id"]
        return response([{"resource_id": rid, "allowed": rid == "space|1"}])

    http = Mock(side_effect=transport)
    monkeypatch.setattr("iam_engine.v4.client.requests.request", http)
    first, second = permission(), permission()
    assert first.get_provider("v4").client is not second.get_provider("v4").client
    expected = {"1": {"view_business_v2": True}, "2": {"view_business_v2": False}}
    assert batch(first) == expected
    assert batch(second) == expected
    assert http.call_count == 2
    monkeypatch.setattr(local, "current_request", SimpleNamespace())
    assert batch(second) == expected
    assert http.call_count == 4


def test_concurrent_identical_queries_across_permissions_issue_one_http(monkeypatch):
    monkeypatch.setattr(local, "current_request", SimpleNamespace(), raising=False)
    first, second = permission(), permission()
    ready, entered, release = Barrier(2), Event(), Event()

    def transport(**kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return response([{"resource_id": "space|1", "allowed": True}])

    http = Mock(side_effect=transport)
    monkeypatch.setattr("iam_engine.v4.client.requests.request", http)

    def run(instance):
        ready.wait(timeout=5)
        return batch(instance, ("1",))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(bind_current_context(lambda instance=p: run(instance))) for p in (first, second)]
        assert entered.wait(timeout=5)
        release.set()
        assert [f.result(timeout=5) for f in futures] == [{"1": {"view_business_v2": True}}] * 2
    assert http.call_count == 1


def test_concurrent_failure_releases_key_and_next_caller_retries(monkeypatch):
    monkeypatch.setattr(local, "current_request", SimpleNamespace(), raising=False)
    client = permission().get_provider("v4").client
    ready, count_lock = Barrier(2), Lock()
    attempts = 0

    def transport(**kwargs):
        nonlocal attempts
        with count_lock:
            attempts += 1
            attempt = attempts
        return response({"allowed": "invalid"} if attempt == 1 else {"allowed": False})

    monkeypatch.setattr("iam_engine.v4.client.requests.request", transport)

    def query():
        return client.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business")

    def run():
        ready.wait(timeout=5)
        try:
            return query()
        except V4ResponseError:
            return "error"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(bind_current_context(run)) for _ in range(2)]
        results = [f.result(timeout=5) for f in futures]
    assert results.count("error") == 1
    assert results.count(False) == 1
    assert query() is False
    assert attempts == 2


def test_concurrent_http_requests_do_not_share_identical_results(monkeypatch):
    client = permission().get_provider("v4").client
    rendezvous = Barrier(2)

    def transport(**kwargs):
        rendezvous.wait(timeout=5)
        return response({"allowed": True})

    http = Mock(side_effect=transport)
    monkeypatch.setattr("iam_engine.v4.client.requests.request", http)

    def query():
        return client.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business")

    calls = []
    for _ in range(2):
        monkeypatch.setattr(local, "current_request", SimpleNamespace(), raising=False)
        calls.append(bind_current_context(query))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call) for call in calls]
        assert [f.result(timeout=5) for f in futures] == [True, True]
    assert http.call_count == 2
