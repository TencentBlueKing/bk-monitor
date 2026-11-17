import datetime
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from apm.constants import ApmCacheType
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.instance_data import BaseInstanceData
from apm.core.handlers.apm_cache_handler import ApmCacheHandler


class BatchDiscovery(CachedDiscoverMixin):
    bk_biz_id = 2
    app_name = "cache-batch"

    @classmethod
    def _get_cache_type(cls):
        return ApmCacheType.ENDPOINT

    @classmethod
    def to_cache_key(cls, instance):
        return str(instance.id)

    @classmethod
    def _to_found_key(cls, instance):
        return (instance.id,)

    @classmethod
    def build_instance_data(cls, obj):
        return BaseInstanceData(id=obj.id, updated_at=getattr(obj, "updated_at", None))


@pytest.fixture
def batch(mocker):
    import fakeredis

    discoverer = BatchDiscovery()
    discoverer.application = SimpleNamespace(trace_datasource=SimpleNamespace(retention=7))
    discoverer.model = mocker.Mock()
    client = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=client)
    key = ApmCacheHandler.get_cache_key(ApmCacheType.ENDPOINT, 2, "cache-batch")
    get = mocker.spy(client, "get")
    put = mocker.spy(client, "set")
    clock = mocker.patch("apm.core.discover.cached_mixin.time.monotonic", return_value=10)
    wall = mocker.patch("apm.core.discover.cached_mixin.time.time", return_value=2000000000)
    discoverer.begin_cache_batch()
    return SimpleNamespace(discoverer=discoverer, client=client, key=key, get=get, put=put, clock=clock, wall=wall)


def refresh(batch, remain, created=(), updated=()):
    batch.discoverer.handle_cache_refresh_after_create(list(remain.values()), list(created), list(updated), remain)


def test_existing_heartbeats_are_batched_and_keep_observation_time(batch):
    instance = BaseInstanceData(id=1)
    remain = {(1,): instance}
    refresh(batch, remain, updated=[instance])
    assert batch.put.call_count == 1
    for i in range(1, 20):
        batch.wall.return_value = 2000000000 + i
        refresh(batch, remain, updated=[instance])
    assert batch.get.call_count == batch.put.call_count == 1
    batch.wall.return_value += 100
    batch.discoverer.flush_cache_updates()
    assert batch.put.call_count == 2
    assert json.loads(batch.client.get(batch.key)) == {"1": 2000000019}
    assert batch.client.ttl(batch.key) > 0
    assert batch.discoverer._pending_cache_updates == {}


def test_interval_flush_and_new_objects_are_published_immediately(batch):
    remain = {}
    refresh(batch, remain, created=[SimpleNamespace(id=1)])
    assert set(remain) == {(1,)}
    assert json.loads(batch.client.get(batch.key)) == {"1": 2000000000}
    batch.wall.return_value += 1
    refresh(batch, remain, updated=list(remain.values()))
    assert batch.put.call_count == 1
    batch.clock.return_value += 30
    refresh(batch, remain, updated=list(remain.values()))
    assert batch.put.call_count == 2
    refresh(batch, remain, created=[SimpleNamespace(id=2)])
    assert batch.put.call_count == 3
    assert set(json.loads(batch.client.get(batch.key))) == {"1", "2"}


def test_flush_merges_other_writer_and_preserves_newer_timestamps(batch):
    remain = {(1,): BaseInstanceData(id=1)}
    refresh(batch, remain, updated=list(remain.values()))
    batch.wall.return_value += 1
    refresh(batch, remain, updated=list(remain.values()))
    batch.client.set(batch.key, json.dumps({"1": 2000000050, "other": 2000000020}))
    batch.discoverer.flush_cache_updates()
    assert json.loads(batch.client.get(batch.key)) == {"1": 2000000050, "other": 2000000020}


def test_failed_flush_preserves_pending_and_can_retry(batch, mocker):
    remain = {(1,): BaseInstanceData(id=1)}
    with mock.patch.object(batch.client, "set", side_effect=RuntimeError("write failed")):
        with pytest.raises(RuntimeError, match="write failed"):
            refresh(batch, remain, updated=list(remain.values()))
    assert batch.discoverer._pending_cache_updates == {"1": 2000000000}
    batch.discoverer.flush_cache_updates()
    assert json.loads(batch.client.get(batch.key)) == {"1": 2000000000}
    assert not batch.discoverer._pending_cache_updates


def test_expired_record_is_removed_once_and_observed_record_is_retained(batch):
    old = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    remain = {(i,): BaseInstanceData(id=i, updated_at=old) for i in [1, 2]}
    refresh(batch, remain, updated=[remain[(1,)]])
    assert set(remain) == {(1,)}
    batch.discoverer.model.objects.filter.assert_called_once_with(pk__in={2})
    for _ in range(3):
        refresh(batch, remain, updated=list(remain.values()))
    assert batch.discoverer.model.objects.filter.call_count == 1
    assert json.loads(batch.client.get(batch.key)) == {"1": 2000000000}


def test_failed_delete_does_not_remove_mapping_or_mark_cleanup_complete(batch, mocker):
    old = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    remain = {(1,): BaseInstanceData(id=1, updated_at=old)}
    batch.discoverer.model.objects.filter.return_value.delete.side_effect = RuntimeError("delete failed")
    with pytest.raises(RuntimeError, match="delete failed"):
        refresh(batch, remain)
    assert set(remain) == {(1,)}
    assert batch.discoverer._cache_cleanup_done is False
    assert not batch.put.called


def test_overflow_is_checked_after_new_objects_and_removes_oldest(batch):
    batch.discoverer.MAX_COUNT = 2
    remain = {(i,): BaseInstanceData(id=i) for i in [1, 2]}
    batch.client.set(batch.key, json.dumps({"1": 1999999900, "2": 2000000000}))
    refresh(batch, remain, updated=[remain[(2,)]])
    refresh(batch, remain, created=[SimpleNamespace(id=3)])
    assert set(remain) == {(2,), (3,)}
    batch.discoverer.model.objects.filter.assert_called_once_with(pk__in={1})
    assert set(json.loads(batch.client.get(batch.key))) == {"2", "3"}


def test_overflow_reloads_ids_when_bulk_create_does_not_return_primary_keys(batch, mocker):
    from apm.core.discover.endpoint import EndpointDiscover
    from apm.core.discover.instance_data import EndpointInstanceData

    discoverer = object.__new__(EndpointDiscover)
    discoverer.bk_biz_id, discoverer.app_name = 2, "cache-batch"
    discoverer.MAX_COUNT = 1
    discoverer.model = mocker.Mock()
    mocker.patch.object(
        EndpointDiscover, "application", new_callable=mocker.PropertyMock, return_value=batch.discoverer.application
    )
    discoverer.begin_cache_batch()
    batch.discoverer = discoverer
    old = EndpointInstanceData(id=10, service_name="service", endpoint_name="old")
    new = EndpointInstanceData(id=None, service_name="service", endpoint_name="new")
    persisted_new = EndpointInstanceData(id=11, service_name="service", endpoint_name="new")
    old_key, new_key = map(discoverer._to_found_key, [old, new])
    old_cache_key, new_cache_key = map(discoverer.to_cache_key, [old, new])
    remain = {old_key: old}
    batch.client.set(batch.key, json.dumps({old_cache_key: 1999999900}))
    reload = mocker.patch.object(discoverer, "get_remain_data", return_value={old_key: old, new_key: persisted_new})
    refresh(batch, remain, created=[new])
    reload.assert_called_once()
    discoverer.model.objects.filter.assert_called_once_with(pk__in={10})
    assert remain == {new_key: persisted_new}
    assert json.loads(batch.client.get(batch.key)) == {new_cache_key: 2000000000}
    refresh(batch, remain, updated=list(remain.values()))
    assert reload.call_count == 1
    assert discoverer.model.objects.filter.call_count == 1


def test_failed_new_endpoint_publish_does_not_create_again_on_next_page(batch, mocker):
    from apm.core.discover.endpoint import EndpointDiscover

    discoverer = object.__new__(EndpointDiscover)
    discoverer.bk_biz_id, discoverer.app_name = 2, "cache-batch"
    model = mocker.patch("apm.core.discover.endpoint.Endpoint")
    model.side_effect = lambda **kwargs: SimpleNamespace(id=None, updated_at=None, **kwargs)
    discoverer.model = model
    mocker.patch.object(
        EndpointDiscover, "application", new_callable=mocker.PropertyMock, return_value=batch.discoverer.application
    )
    mocker.patch.object(
        discoverer, "get_rules", return_value=([], SimpleNamespace(endpoint_key=("", "span_name"), category_id="other"))
    )
    mocker.patch("apm.core.discover.endpoint.TraceDataSource.get_category_kind", return_value=(None, None))
    discoverer.begin_cache_batch()
    remain = {}
    span = {"resource": {"service.name": "service"}, "attributes": {}, "kind": 2, "span_name": "GET /item"}
    with mock.patch.object(batch.client, "set", side_effect=RuntimeError("write failed")):
        with pytest.raises(RuntimeError, match="write failed"):
            discoverer.discover([span], remain)
    assert len(remain) == 1
    assert discoverer._pending_cache_updates
    discoverer.discover([span], remain)
    assert [len(call.args[0]) for call in model.objects.bulk_create.call_args_list] == [1, 0]
    discoverer.flush_cache_updates()
    assert set(json.loads(batch.client.get(batch.key))) == {discoverer.to_cache_key(next(iter(remain.values())))}


def test_non_batch_caller_keeps_immediate_refresh(mocker):
    discoverer = BatchDiscovery()
    mocker.patch.object(discoverer, "_query_cache_data", return_value={})
    mocker.patch.object(discoverer, "_clear_data", return_value=set())
    refresh_cache = mocker.patch.object(discoverer, "_refresh_cache_data")
    remain = {}
    discoverer.handle_cache_refresh_after_create([], [SimpleNamespace(id=1)], [], remain)
    assert set(remain) == {(1,)}
    refresh_cache.assert_called_once()
