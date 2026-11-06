from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from opentelemetry.context import attach, detach, get_value, set_value

from bkmonitor.iam.concurrency import bind_current_context, map_chunks_concurrently, run_pair_concurrently
from bkmonitor.utils.local import local


@pytest.fixture
def request_context():
    previous = dict(local)
    token = attach(set_value("iam-test", "caller"))
    local.username = "alice"
    local.bk_tenant_id = "tenant-a"
    local.current_request = object()
    try:
        with timezone.override(ZoneInfo("Asia/Shanghai")):
            yield dict(local)
    finally:
        local.clear()
        for key, value in previous.items():
            setattr(local, key, value)
        detach(token)


def test_parallel_branches_inherit_product_context_without_leaking_to_caller(request_context):
    def worker():
        assert local.username == "alice"
        assert local.bk_tenant_id == "tenant-a"
        assert local.current_request is request_context["current_request"]
        assert get_value("iam-test") == "caller"
        assert str(timezone.get_current_timezone()) == "Asia/Shanghai"
        local.username = "worker-only"
        return True

    assert run_pair_concurrently(worker, worker) == (True, True)
    assert map_chunks_concurrently([1, 2], lambda _: worker(), max_workers=2) == [True, True]
    assert dict(local) == request_context


def test_context_is_restored_even_when_worker_raises(request_context):
    def fail():
        assert local.username == "alice"
        assert local.bk_tenant_id == "tenant-a"
        assert get_value("iam-test") == "caller"
        local.new_worker_value = "must not survive"
        raise TimeoutError("offline")

    bound = bind_current_context(fail)
    local.username = "previous-worker"
    local.bk_tenant_id = "tenant-b"
    previous = dict(local)
    token = attach(set_value("iam-test", "previous-worker"))
    try:
        with timezone.override(ZoneInfo("UTC")):
            with pytest.raises(TimeoutError, match="offline"):
                bound()
            assert dict(local) == previous
            assert get_value("iam-test") == "previous-worker"
            assert str(timezone.get_current_timezone()) == "UTC"
    finally:
        detach(token)
