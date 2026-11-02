import datetime
import logging
from types import SimpleNamespace

import pytest

from apm.constants import ApmCacheType
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import BaseInstanceData
from apm.core.handlers.apm_cache_handler import ApmCacheHandler


class CacheDiscovery(CachedDiscoverMixin):
    bk_biz_id = 2
    app_name = "logging-test"

    @classmethod
    def _get_cache_type(cls):
        return ApmCacheType.ENDPOINT

    @classmethod
    def to_cache_key(cls, instance):
        return str(instance.id)

    @classmethod
    def build_instance_data(cls, instance_obj):
        return BaseInstanceData(id=instance_obj.id)


@pytest.fixture
def discovery(mocker):
    handler = CacheDiscovery()
    handler.application = SimpleNamespace(trace_datasource=SimpleNamespace(retention=7))
    handler.model = mocker.Mock()
    mocker.patch.object(handler, "_query_cache_data", return_value={})
    return handler


@pytest.mark.parametrize("changed", [False, True])
def test_cache_refresh_preserves_writes_and_only_logs_changes(discovery, mocker, caplog, changed):
    caplog.set_level(logging.INFO, logger="apm")
    mocker.patch.object(discovery, "_clear_data", return_value={"3"} if changed else set())
    refresh = mocker.patch.object(discovery, "_refresh_cache_data")
    discovery.handle_cache_refresh_after_create(
        [BaseInstanceData(id=2), BaseInstanceData(id=3)],
        [SimpleNamespace(id=1)] if changed else [],
        [BaseInstanceData(id=2)] if changed else [],
    )

    refresh.assert_called_once_with(
        old_cache_data={},
        create_instance_keys={"1"} if changed else set(),
        update_instance_keys={"2"} if changed else set(),
        delete_instance_keys={"3"} if changed else set(),
    )
    if changed:
        assert len(caplog.records) == 1
        assert "event=cache_refreshed bk_biz_id=2 app_name=logging-test" in caplog.text
        assert "existing_count=2 created_count=1 updated_count=1 deleted_count=1 duration_s=" in caplog.text
    else:
        assert not caplog.records


@pytest.mark.parametrize("overflow", [False, True])
@pytest.mark.parametrize("delete_fails", [False, True])
def test_cleanup_retains_reason_and_bounded_sample_even_on_failure(discovery, caplog, overflow, delete_fails):
    caplog.set_level(logging.INFO, logger="apm")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    expired = [BaseInstanceData(id=i, updated_at=now - datetime.timedelta(days=10)) for i in range(12)]
    active = [BaseInstanceData(id=i, updated_at=now - datetime.timedelta(hours=14 - i)) for i in (12, 13)]
    discovery.MAX_COUNT = 1 if overflow else 100
    expected_ids = set(range(13 if overflow else 12))
    delete = discovery.model.objects.filter.return_value.delete
    error = RuntimeError("delete unavailable")
    if delete_fails:
        delete.side_effect = error
        with pytest.raises(RuntimeError) as raised:
            discovery._clear_data({}, expired + active)
        assert raised.value is error
    else:
        assert discovery._clear_data({}, expired + active) == {str(i) for i in expected_ids}

    discovery.model.objects.filter.assert_called_once_with(pk__in=expected_ids)
    delete.assert_called_once()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == (logging.WARNING if overflow else logging.INFO)
    assert "event=cleanup_started bk_biz_id=2 app_name=logging-test" in record.getMessage()
    assert f"expired_count=12 overflow_count={int(overflow)} retention_days=7" in record.getMessage()
    sample = record.args[-1]
    assert len(sample) == 10
    assert set(sample) <= expected_ids
    assert "event=cache_refreshed" not in caplog.text


def test_cache_write_failure_preserves_exception_and_diagnostic_context(mocker, caplog):
    client = mocker.Mock()
    error = RuntimeError("redis unavailable")
    client.set.side_effect = error
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=client)

    with pytest.raises(RuntimeError) as raised:
        ApmCacheHandler().refresh_data("test-cache-key", {"private-entry": 123}, ex=60)

    assert raised.value is error
    assert "event=refresh_failed key=test-cache-key entry_count=1 ttl_s=60" in caplog.text
    assert "private-entry" not in caplog.text
    assert caplog.records[0].exc_info[1] is error
