from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import json
import os
from threading import Barrier, Event, Lock
import zlib

import pytest
from api.cmdb.mock import HOSTS
from django.urls import resolve
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.share.api_auth_resource import ApiAuthResource
from monitor_web.performance import snapshot


@pytest.fixture(autouse=True)
def enable_host_metric_progressive(settings):
    settings.ENABLE_HOST_METRIC_PROGRESSIVE = True


class FakeCache:
    def __init__(self):
        self.data = {}
        self.timeouts = {}
        self.zsets = {}
        self.client = self
        self.eval_lock = Lock()

    def get_client(self, write=False):
        return self

    @staticmethod
    def make_key(key):
        return key

    def add(self, key, value, timeout=None):
        if key in self.data:
            return False
        self.set(key, value, timeout)
        return True

    def delete(self, key):
        return self.data.pop(key, None) is not None

    def get(self, key, default=None):
        return deepcopy(self.data.get(key, default))

    def set(self, key, value, timeout=None):
        self.data[key] = deepcopy(value)
        self.timeouts[key] = timeout

    def touch(self, key, timeout=None):
        if key not in self.data:
            return False
        self.timeouts[key] = timeout
        return True

    def eval(self, script, numkeys, *values):
        keys = values[:numkeys]
        args = values[numkeys:]
        with self.eval_lock:
            if "host-metric-snapshot-claim" in script:
                pointer_key, lease_key = keys
                now, expires_at, limit, member, pointer_timeout, lease_timeout = args
                current = self.data.get(pointer_key)
                if current:
                    return [current, 0]
                leases = self.zsets.setdefault(lease_key, {})
                self.zsets[lease_key] = leases = {
                    existing_member: score for existing_member, score in leases.items() if score > float(now)
                }
                if len(leases) >= int(limit):
                    return ["", -1]
                self.data[pointer_key] = member
                self.timeouts[pointer_key] = int(pointer_timeout)
                leases[member] = float(expires_at)
                self.timeouts[lease_key] = int(lease_timeout)
                return [member, 1]
            if "host-metric-snapshot-renew" in script:
                pointer_key, lease_key = keys
                member, now, expires_at, timeout = args
                score = self.zsets.get(lease_key, {}).get(member)
                if self.data.get(pointer_key) != member or score is None or score <= float(now):
                    return 0
                self.timeouts[pointer_key] = int(timeout)
                self.zsets[lease_key][member] = float(expires_at)
                self.timeouts[lease_key] = int(timeout)
                return 1
            if "host-metric-snapshot-terminal-claim" in script:
                key = keys[0]
                leases = self.zsets.get(key, {})
                score = leases.get(args[0])
                if score is None:
                    return 0
                leases.pop(args[0])
                return 1 if score > float(args[1]) and float(args[2]) >= float(args[1]) else -1
            if "del" in script:
                key = keys[0]
                if self.data.get(key) == args[0]:
                    return int(self.delete(key))
                return 0
            if "expire" in script:
                key = keys[0]
                if self.data.get(key) == args[0]:
                    self.timeouts[key] = int(args[1])
                    return 1
                return 0
            raise AssertionError("unexpected Redis script")

    def zscore(self, key, member):
        return self.zsets.get(key, {}).get(member)


class ConcurrentPointerCache(FakeCache):
    def __init__(self):
        super().__init__()
        self.pointer_barrier = Barrier(2)
        self.pointer_reads = 0
        self.pointer_reads_lock = Lock()

    def get(self, key, default=None):
        should_wait = False
        if ":pointer:" in key and key not in self.data:
            with self.pointer_reads_lock:
                if self.pointer_reads < 2:
                    self.pointer_reads += 1
                    should_wait = True
        if should_wait:
            self.pointer_barrier.wait(timeout=2)
        return super().get(key, default)


class PrefixedFakeCache(FakeCache):
    @staticmethod
    def make_key(key):
        return f"deployment-a:1:{key}"


def make_payload(host_ids_hash="sha256:hosts"):
    return {
        "bk_biz_id": 2,
        "bk_tenant_id": "tenant-a",
        "canonical_start_time": 100,
        "canonical_end_time": 200,
        "deadline_at": int(snapshot.time.time()) + snapshot.SNAPSHOT_DEADLINE,
        "host_count": 2,
        "host_ids_hash": host_ids_hash,
        "scope": {"type": "business"},
        "sections": {},
    }


def test_host_ids_hash_is_order_independent_and_set_sensitive():
    assert snapshot.build_host_ids_hash([3, 1, 2]) == snapshot.build_host_ids_hash([1, 2, 3])
    assert snapshot.build_host_ids_hash([1, 2, 3]) != snapshot.build_host_ids_hash([1, 2, 4])


@pytest.mark.parametrize(
    ("host_ids", "expected"),
    [
        ([2, 10, 2], "3b5140aab9f8b8240b81687ea6a802d4bb00fc5da32c97b4b2bff91263b3a545"),
        ([], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ],
)
def test_host_ids_hash_has_cross_language_vectors(host_ids, expected):
    assert snapshot.build_host_ids_hash(host_ids) == expected


def test_live_time_fingerprint_reuses_same_minute_bucket_and_anchor():
    first = snapshot.canonicalize_snapshot_time(100, 200, now=201, is_share=False)
    second = snapshot.canonicalize_snapshot_time(110, 210, now=211, is_share=False)

    assert (
        first.time_key
        == second.time_key
        == {
            "end_time": 180,
            "mode": "live",
            "start_time": 80,
        }
    )
    assert (first.start_time, first.end_time) == (80, 180)
    assert (second.start_time, second.end_time) == (80, 180)


def test_live_time_fingerprint_does_not_reuse_across_minute_buckets():
    first = snapshot.canonicalize_snapshot_time(100, 200, now=201, is_share=False)
    second = snapshot.canonicalize_snapshot_time(160, 260, now=261, is_share=False)

    assert first.time_key != second.time_key
    assert (first.start_time, first.end_time) == (80, 180)
    assert (second.start_time, second.end_time) == (140, 240)


def test_historical_time_fingerprint_keeps_exact_range():
    first = snapshot.canonicalize_snapshot_time(100, 200, now=1000, is_share=False)
    second = snapshot.canonicalize_snapshot_time(110, 210, now=1000, is_share=False)

    assert first.time_key != second.time_key
    assert first.time_key == {"end_time": 200, "mode": "historical", "start_time": 100}


def test_share_time_fingerprint_is_always_exact():
    result = snapshot.canonicalize_snapshot_time(100, 200, now=201, is_share=True)

    assert result.time_key == {"end_time": 200, "mode": "historical", "start_time": 100}


@pytest.mark.parametrize("start_time,end_time", [(100, 100), (101, 100)])
def test_time_range_must_be_positive(start_time, end_time):
    with pytest.raises(ValueError, match="end_time must be greater"):
        snapshot.canonicalize_snapshot_time(start_time, end_time, now=200, is_share=False)


def test_fingerprint_binds_tenant_scope_and_canonical_time():
    base = {
        "bk_tenant_id": "tenant-a",
        "bk_biz_id": 2,
        "scope": {"type": "business"},
        "time_key": {"end_time": 180, "mode": "live", "start_time": 80},
    }
    fingerprint = snapshot.build_snapshot_fingerprint(**base)

    for key, replacement in (
        ("bk_tenant_id", "tenant-b"),
        ("bk_biz_id", 3),
        ("scope", {"type": "host", "bk_host_id": 1}),
        ("time_key", {"end_time": 240, "mode": "live", "start_time": 140}),
    ):
        changed = {**base, key: replacement}
        assert snapshot.build_snapshot_fingerprint(**changed) != fingerprint


def test_cache_add_singleflight_returns_one_snapshot_for_same_fingerprint(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())

    first, first_created = store.create_or_get("sha256:fingerprint", make_payload())
    second, second_created = store.create_or_get("sha256:fingerprint", make_payload())

    assert first_created is True
    assert second_created is False
    assert first["snapshot_id"] == second["snapshot_id"] == "a" * 32


def test_capacity_limit_counts_distinct_running_snapshots_per_tenant_and_business(monkeypatch):
    ids = iter(("a" * 32, "b" * 32, "c" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 2, raising=False)
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())

    first, first_created = store.create_or_get("sha256:first", make_payload())
    second, second_created = store.create_or_get("sha256:second", make_payload())

    assert first_created is second_created is True
    with pytest.raises(snapshot.SnapshotCapacityExceeded):
        store.create_or_get("sha256:third", make_payload())
    assert store.get_manifest("c" * 32) is None
    assert first["capacity_lease_key"] == second["capacity_lease_key"]


def test_capacity_limit_defaults_to_one(settings):
    if "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ" in os.environ:
        pytest.skip("deployment overrides snapshot capacity")
    assert settings.HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ == 1


def test_capacity_key_isolated_by_tenant_and_business():
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())

    assert store.capacity_lease_key(bk_tenant_id="tenant-a", bk_biz_id=2) != store.capacity_lease_key(
        bk_tenant_id="tenant-b", bk_biz_id=2
    )
    assert store.capacity_lease_key(bk_tenant_id="tenant-a", bk_biz_id=2) != store.capacity_lease_key(
        bk_tenant_id="tenant-a", bk_biz_id=3
    )


def test_raw_pointer_and_capacity_keys_use_django_cache_namespace(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = PrefixedFakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)

    manifest, _ = store.create_or_get("sha256:first", make_payload())

    assert manifest["capacity_lease_key"].startswith("deployment-a:1:")
    assert cache.get("deployment-a:1:" + store.pointer_key("sha256:first")) == manifest["snapshot_id"]


def test_compare_delete_does_not_remove_replaced_pointer(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    old, _ = store.create_or_get("sha256:first", make_payload())
    cache.set(store.pointer_key("sha256:first"), "b" * 32, snapshot.RUNNING_TTL)

    store._delete_pointer("sha256:first", old["snapshot_id"])

    assert cache.get(store.pointer_key("sha256:first")) == "b" * 32


def test_same_fingerprint_reuse_does_not_consume_another_capacity_slot(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)

    first, first_created = store.create_or_get("sha256:same", make_payload())
    reused, reused_created = store.create_or_get("sha256:same", make_payload())

    assert first_created is True
    assert reused_created is False
    assert reused["snapshot_id"] == first["snapshot_id"]
    lease_key = first["capacity_lease_key"]
    assert set(cache.zsets[lease_key]) == {first["snapshot_id"]}


def test_concurrent_same_fingerprint_claims_one_capacity_member(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = ConcurrentPointerCache()

    def create_snapshot():
        return snapshot.HostMetricSnapshotStore(cache=cache).create_or_get("sha256:same", make_payload())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create_snapshot(), range(2)))

    manifests = [result[0] for result in results]
    assert {manifest["snapshot_id"] for manifest in manifests} == {manifests[0]["snapshot_id"]}
    assert sorted(result[1] for result in results) == [False, True]
    assert set(cache.zsets[manifests[0]["capacity_lease_key"]]) == {manifests[0]["snapshot_id"]}


@pytest.mark.parametrize("terminal_state", ["ready", "failed", "expired"])
def test_terminal_snapshot_releases_capacity_slot(monkeypatch, terminal_state):
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    first, _ = store.create_or_get("sha256:first", make_payload())

    if terminal_state == "ready":
        store.mark_ready(first["snapshot_id"], expected_sections=set())
    elif terminal_state == "failed":
        store.fail(first["snapshot_id"], "task_failed")
    else:
        store.expire(first["snapshot_id"])

    second, created = store.create_or_get("sha256:second", make_payload())
    assert created is True
    assert second["snapshot_id"] == "b" * 32


def test_expire_winning_terminal_lease_race_cannot_be_revived_ready(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:first", make_payload())
    store.write_section(manifest["snapshot_id"], "agent_status", {})
    store.mark_section_ready(manifest["snapshot_id"], "agent_status")
    ready_waiting = Event()
    continue_ready = Event()
    original_claim_terminal = store._claim_terminal

    def pause_ready_claim(current_manifest):
        ready_waiting.set()
        assert continue_ready.wait(timeout=2)
        return original_claim_terminal(current_manifest)

    monkeypatch.setattr(store, "_claim_terminal", pause_ready_claim)
    with ThreadPoolExecutor(max_workers=1) as executor:
        ready_future = executor.submit(
            store.mark_ready,
            manifest["snapshot_id"],
            expected_sections={"agent_status"},
        )
        assert ready_waiting.wait(timeout=2)
        monkeypatch.setattr(store, "_claim_terminal", original_claim_terminal)
        store.expire(manifest["snapshot_id"])
        continue_ready.set()
        ready_future.result(timeout=2)

    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.EXPIRED
    assert store.cache.timeouts[store.pointer_key("sha256:first")] == snapshot.FAILED_TTL


def test_ready_terminal_winner_cannot_be_overwritten_by_losing_expire(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:first", make_payload())
    ready_waiting = Event()
    continue_ready = Event()
    original_set = store._set

    def pause_ready_write(key, value, timeout):
        if key == store.manifest_key(manifest["snapshot_id"]) and value.get("state") == snapshot.SnapshotState.READY:
            ready_waiting.set()
            assert continue_ready.wait(timeout=2)
        return original_set(key, value, timeout)

    monkeypatch.setattr(store, "_set", pause_ready_write)
    with ThreadPoolExecutor(max_workers=1) as executor:
        ready_future = executor.submit(store.mark_ready, manifest["snapshot_id"], expected_sections=set())
        assert ready_waiting.wait(timeout=2)
        store.expire(manifest["snapshot_id"])
        continue_ready.set()
        ready_future.result(timeout=2)

    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.READY


def test_running_manifest_update_cannot_overwrite_concurrent_expire(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:first", make_payload())
    update_waiting = Event()
    continue_update = Event()
    original_owns_capacity = store.owns_capacity
    owns_calls = 0

    def pause_after_initial_capacity_check(current_manifest, **kwargs):
        nonlocal owns_calls
        owns_calls += 1
        result = original_owns_capacity(current_manifest, **kwargs)
        if owns_calls == 1:
            update_waiting.set()
            assert continue_update.wait(timeout=2)
        return result

    monkeypatch.setattr(store, "owns_capacity", pause_after_initial_capacity_check)
    with ThreadPoolExecutor(max_workers=1) as executor:
        update_future = executor.submit(store.update_manifest, manifest["snapshot_id"], host_count=1)
        assert update_waiting.wait(timeout=2)
        store.expire(manifest["snapshot_id"])
        continue_update.set()
        update_future.result(timeout=2)

    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.EXPIRED


def test_deadline_expired_snapshot_cannot_publish_ready_with_live_capacity_lease(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    monkeypatch.setattr(snapshot.time, "time", lambda: 300)
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:first", {**make_payload(), "deadline_at": 299})

    store.mark_ready(manifest["snapshot_id"], expected_sections=set())

    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.EXPIRED


def test_capacity_reservation_has_short_ttl_and_old_worker_cannot_release_new_owner(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:first", make_payload())
    slot_key = manifest["capacity_lease_key"]

    assert cache.timeouts[slot_key] == snapshot.RUNNING_TTL
    assert cache.timeouts[store.pointer_key("sha256:first")] == snapshot.RESERVATION_TTL
    cache.zsets[slot_key] = {"b" * 32: 400}
    store.fail(manifest["snapshot_id"], "old_task_failed")

    assert cache.zscore(slot_key, "b" * 32) == 400


def test_capacity_reservation_can_be_renewed_for_running_task(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:first", make_payload())

    assert store.renew_capacity(manifest) is True
    assert cache.timeouts[manifest["capacity_lease_key"]] == snapshot.RUNNING_TTL
    assert cache.timeouts[store.pointer_key("sha256:first")] == snapshot.RUNNING_TTL


def test_new_reservation_does_not_shorten_existing_running_capacity_key_ttl(monkeypatch):
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 2, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    first, _ = store.create_or_get("sha256:first", make_payload())
    store.renew_capacity(first)

    second, _ = store.create_or_get("sha256:second", make_payload())

    assert cache.timeouts[first["capacity_lease_key"]] == snapshot.RUNNING_TTL
    assert cache.zscore(first["capacity_lease_key"], first["snapshot_id"]) is not None
    assert cache.zscore(second["capacity_lease_key"], second["snapshot_id"]) is not None


def test_expired_capacity_lease_allows_another_fingerprint(monkeypatch):
    ids = iter(("a" * 32, "b" * 32))
    now = [100]
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    monkeypatch.setattr(snapshot.time, "time", lambda: now[0])
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    first, _ = store.create_or_get("sha256:first", make_payload())

    now[0] += snapshot.RESERVATION_TTL + 1
    second, created = store.create_or_get("sha256:second", make_payload())

    assert created is True
    assert cache.zscore(first["capacity_lease_key"], first["snapshot_id"]) is None
    assert cache.zscore(second["capacity_lease_key"], second["snapshot_id"]) is not None


def test_expired_old_capacity_member_cannot_publish_ready_or_remove_new_member(monkeypatch):
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    monkeypatch.setattr(snapshot.time, "time", lambda: 200)
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 2, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    old, _ = store.create_or_get("sha256:old", make_payload())
    new, _ = store.create_or_get("sha256:new", make_payload())
    lease_key = old["capacity_lease_key"]
    cache.zsets[lease_key][old["snapshot_id"]] = 199

    store.mark_ready(old["snapshot_id"], expected_sections=set())

    assert store.get_manifest(old["snapshot_id"])["state"] == snapshot.SnapshotState.EXPIRED
    assert cache.zscore(lease_key, old["snapshot_id"]) is None
    assert cache.zscore(lease_key, new["snapshot_id"]) > 200


def test_dangling_pointer_without_manifest_can_be_reclaimed(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "b" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    cache.set(store.pointer_key("sha256:fingerprint"), "a" * 32, snapshot.RUNNING_TTL)

    manifest, created = store.create_or_get("sha256:fingerprint", make_payload())

    assert created is True
    assert manifest["snapshot_id"] == "b" * 32
    assert store.get_current("sha256:fingerprint")["snapshot_id"] == "b" * 32


def test_manifest_and_section_keys_are_isolated_by_snapshot_id(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 2, raising=False)
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)

    first, _ = store.create_or_get("sha256:first", make_payload())
    second, _ = store.create_or_get("sha256:second", make_payload("sha256:other"))
    store.write_section(first["snapshot_id"], "agent_status", {1: {"status": 1}})
    store.write_section(second["snapshot_id"], "agent_status", {2: {"status": 2}})

    assert store.read_section(first["snapshot_id"], "agent_status") == {1: {"status": 1}}
    assert store.read_section(second["snapshot_id"], "agent_status") == {2: {"status": 2}}


def test_section_blob_compression_gate_for_twenty_thousand_hosts(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:first", make_payload())
    data = {
        host_id: {
            "cpu_load": host_id % 100,
            "cpu_usage": host_id % 100,
            "disk_in_use": host_id % 100,
            "io_util": host_id % 100,
            "mem_usage": host_id % 100,
            "psc_mem_usage": host_id % 100,
        }
        for host_id in range(1, 20_001)
    }

    store.write_section(manifest["snapshot_id"], "performance_data", data)

    blob = cache.get(store.section_key(manifest["snapshot_id"], "performance_data"))
    raw_size = len(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
    assert len(blob) < raw_size * 0.35
    assert len(store.read_section(manifest["snapshot_id"], "performance_data")) == 20_000


def test_old_task_cannot_replace_new_pointer(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 2, raising=False)
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)

    old, _ = store.create_or_get("sha256:same", make_payload())
    cache.delete(store.pointer_key("sha256:same"))
    new, _ = store.create_or_get("sha256:same", make_payload())
    store.mark_ready(old["snapshot_id"], expected_sections=set())

    assert store.get_current("sha256:same")["snapshot_id"] == new["snapshot_id"]
    assert store.get_manifest(old["snapshot_id"])["state"] == snapshot.SnapshotState.READY


def test_missing_ready_section_blob_fails_closed(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    store.mark_section_ready(manifest["snapshot_id"], "agent_status")
    store.mark_ready(manifest["snapshot_id"], expected_sections={"agent_status"})

    response = store.build_response(manifest["snapshot_id"])

    assert response["state"] == snapshot.SnapshotState.FAILED
    assert response["data"] == {}
    assert response["failed_sections"] == ["agent_status"]
    assert response["retry_after"] == 5
    assert store.get_manifest(manifest["snapshot_id"])["error_code"] == "section_missing"
    assert cache.timeouts[store.pointer_key("sha256:fingerprint")] == snapshot.FAILED_TTL


@pytest.mark.parametrize("corrupt_blob", [b"not-zlib", zlib.compress(b"not-json")])
def test_corrupt_ready_section_blob_persists_failed_state_and_short_retry(monkeypatch, corrupt_blob):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    cache.set(store.section_key(manifest["snapshot_id"], "agent_status"), corrupt_blob, snapshot.SECTION_TTL)
    store.mark_section_ready(manifest["snapshot_id"], "agent_status")
    store.mark_ready(manifest["snapshot_id"], expected_sections={"agent_status"})

    response = store.build_response(manifest["snapshot_id"])

    assert response["state"] == snapshot.SnapshotState.FAILED
    assert response["data"] == {}
    assert response["failed_sections"] == ["agent_status"]
    assert response["retry_after"] == 5
    assert store.get_manifest(manifest["snapshot_id"])["error_code"] == "section_corrupt"
    assert cache.timeouts[store.pointer_key("sha256:fingerprint")] == snapshot.FAILED_TTL


def test_enqueue_failure_is_visible_and_pointer_has_short_retry_ttl(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())

    store.fail(manifest["snapshot_id"], "enqueue_failed")

    assert store.build_response(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.FAILED
    assert cache.timeouts[store.pointer_key("sha256:fingerprint")] == snapshot.FAILED_TTL


def test_missing_redis_alias_fails_closed(monkeypatch):
    monkeypatch.setattr(snapshot, "caches", {})

    with pytest.raises(snapshot.SnapshotUnavailable):
        snapshot.HostMetricSnapshotStore()


def test_poll_since_revision_only_returns_new_section_blobs(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    snapshot_id = manifest["snapshot_id"]
    store.write_section(snapshot_id, "agent_status", {1: {"status": 1}})
    store.mark_section_ready(snapshot_id, "agent_status")
    store.write_section(snapshot_id, "performance_data", {1: {"cpu_usage": 10}})
    store.mark_section_ready(snapshot_id, "performance_data")

    response = store.build_response(snapshot_id, since_revision=1, now=200)

    assert response["revision"] == 2
    assert set(response["sections"]) == {"agent_status", "performance_data"}
    assert response["data"] == {"performance_data": {1: {"cpu_usage": 10}}}


def test_poll_does_not_read_already_delivered_section_blobs(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    snapshot_id = manifest["snapshot_id"]
    store.write_section(snapshot_id, "agent_status", {1: {"status": 1}})
    store.mark_section_ready(snapshot_id, "agent_status")
    read_section = monkeypatch.setattr

    original_read_section = store.read_section
    calls = []

    def track_read(section_snapshot_id, section):
        calls.append((section_snapshot_id, section))
        return original_read_section(section_snapshot_id, section)

    read_section(store, "read_section", track_read)

    response = store.build_response(snapshot_id, since_revision=1, now=200)

    assert response["data"] == {}
    assert calls == []


def test_ready_requires_every_expected_section(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())

    with pytest.raises(ValueError, match="incomplete sections"):
        store.mark_ready(manifest["snapshot_id"], expected_sections={"agent_status", "performance_data"})


def test_running_snapshot_past_deadline_is_expired(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", {**make_payload(), "deadline_at": 260})

    response = store.build_response(manifest["snapshot_id"], now=261)

    assert response["state"] == snapshot.SnapshotState.EXPIRED
    assert response["expired"] is True
    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.EXPIRED
    assert store.cache.timeouts[store.pointer_key("sha256:fingerprint")] == snapshot.FAILED_TTL
    assert response["retry_after"] == 5


def test_expired_snapshot_can_be_rebuilt_after_short_pointer_ttl(monkeypatch):
    ids = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": next(ids)})())
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    old, _ = store.create_or_get("sha256:fingerprint", {**make_payload(), "deadline_at": 260})

    response = store.build_response(old["snapshot_id"], now=261)
    assert response["retry_after"] == 5
    assert cache.timeouts[store.pointer_key("sha256:fingerprint")] == snapshot.FAILED_TTL

    cache.delete(store.pointer_key("sha256:fingerprint"))
    cache.delete(store.manifest_key(old["snapshot_id"]))
    rebuilt, created = store.create_or_get("sha256:fingerprint", make_payload())

    assert created is True
    assert rebuilt["snapshot_id"] == "b" * 32


def test_snapshot_serializers_require_exact_time_and_reject_unknown_fields():
    resources = import_module("monitor_web.performance.resources")
    create_serializer = resources.CreateHostMetricSnapshotResource.RequestSerializer
    poll_serializer = resources.GetHostMetricSnapshotResource.RequestSerializer

    for serializer_class, base in (
        (create_serializer, {"bk_biz_id": 2}),
        (poll_serializer, {"bk_biz_id": 2, "snapshot_id": "snapshot-1"}),
    ):
        for invalid in (
            base,
            {**base, "start_time": 100},
            {**base, "end_time": 200},
            {**base, "start_time": 100, "end_time": 200, "full_business": True},
            {**base, "start_time": 100, "end_time": 200, "target_filter": {}},
            {**base, "start_time": 100, "end_time": 200, "capacity_lease_key": "forged"},
            {**base, "start_time": 100, "end_time": 200, "capacity_slot": 1},
            {**base, "start_time": 100, "end_time": 200, "release": True},
        ):
            with pytest.raises(serializers.ValidationError):
                serializer_class(data=invalid).is_valid(raise_exception=True)

    poll = poll_serializer(
        data={"bk_biz_id": 2, "snapshot_id": "snapshot-1", "start_time": 100, "end_time": 200, "since_revision": -1}
    )
    with pytest.raises(serializers.ValidationError):
        poll.is_valid(raise_exception=True)


def test_snapshot_routes_resolve_to_dedicated_gzip_create_and_retrieve_actions():
    views = import_module("monitor_web.performance.views")
    create_match = resolve("/rest/v2/performance/host_metric_snapshot/")
    poll_match = resolve("/rest/v2/performance/host_metric_snapshot/snapshot-1/")

    assert create_match.func.cls is views.HostMetricSnapshotViewSet
    assert create_match.func.actions == {"post": "create"}
    assert poll_match.func.cls is views.HostMetricSnapshotViewSet
    assert poll_match.func.actions == {"get": "retrieve"}
    assert all(route.content_encoding == "gzip" for route in views.HostMetricSnapshotViewSet.resource_routes)


def test_snapshot_routes_require_view_host_and_api_auth_resources():
    resources = import_module("monitor_web.performance.resources")
    views = import_module("monitor_web.performance.views")

    permissions = views.HostMetricSnapshotViewSet().get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], BusinessActionPermission)
    assert permissions[0].actions == [ActionEnum.VIEW_HOST]
    assert issubclass(resources.CreateHostMetricSnapshotResource, ApiAuthResource)
    assert issubclass(resources.GetHostMetricSnapshotResource, ApiAuthResource)


def test_disabled_feature_flag_blocks_create_and_poll_before_store_access(mocker, settings):
    resources = import_module("monitor_web.performance.resources")
    tasks = import_module("monitor_web.performance.tasks")
    settings.ENABLE_HOST_METRIC_PROGRESSIVE = False
    store = mocker.patch.object(
        resources,
        "HostMetricSnapshotStore",
        side_effect=AssertionError("disabled snapshot touched Redis"),
    )
    enqueue = mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    task_store = mocker.patch.object(
        tasks,
        "HostMetricSnapshotStore",
        side_effect=AssertionError("disabled task touched Redis"),
    )

    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    polled = resources.GetHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "snapshot_id": "snapshot-1", "start_time": 100, "end_time": 200}
    )
    tasks.build_host_metric_snapshot.run("snapshot-1")

    assert created["state"] == polled["state"] == snapshot.SnapshotState.UNAVAILABLE
    assert created["data"] == polled["data"] == {}
    store.assert_not_called()
    task_store.assert_not_called()
    enqueue.assert_not_called()


def test_disabling_feature_after_create_blocks_existing_snapshot_data(mocker, settings):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    get_manifest = mocker.patch.object(store, "get_manifest", wraps=store.get_manifest)
    settings.ENABLE_HOST_METRIC_PROGRESSIVE = False

    result = resources.GetHostMetricSnapshotResource().perform_request(
        {
            "bk_biz_id": 2,
            "snapshot_id": created["snapshot_id"],
            "start_time": created["canonical_start_time"],
            "end_time": created["canonical_end_time"],
        }
    )

    assert result["state"] == snapshot.SnapshotState.UNAVAILABLE
    assert result["data"] == {}
    get_manifest.assert_not_called()


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/rest/v2/performance/host_metric_snapshot/", "POST"),
        ("/rest/v2/performance/host_metric_snapshot/snapshot-1/", "GET"),
    ],
)
def test_snapshot_routes_reject_generic_async_header_before_resource_delay(mocker, path, method):
    resources = import_module("monitor_web.performance.resources")
    match = resolve(path)
    resource_class = (
        resources.CreateHostMetricSnapshotResource if method == "POST" else resources.GetHostMetricSnapshotResource
    )
    mocker.patch.object(match.func.cls, "get_permissions", return_value=[])
    delay = mocker.patch.object(resource_class, "delay", side_effect=AssertionError("generic async path used"))
    factory = APIRequestFactory()

    if method == "POST":
        response = match.func(factory.post(path, {}, format="json", HTTP_X_ASYNC_TASK="1"))
    else:
        response = match.func(factory.get(path, {}, HTTP_X_ASYNC_TASK="1"), pk="snapshot-1")

    assert response.status_code == 400
    delay.assert_not_called()


def test_snapshot_create_reuses_singleflight_and_returns_canonical_anchor(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    get_hosts = mocker.patch.object(resources.api.cmdb, "get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    delay = mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    params = {"bk_biz_id": 2, "start_time": 100, "end_time": 200}

    first = resources.CreateHostMetricSnapshotResource().perform_request(params)
    second = resources.CreateHostMetricSnapshotResource().perform_request(params)

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["canonical_start_time"] == 80
    assert first["canonical_end_time"] == 180
    assert first["host_count"] == 0
    assert first["host_ids_hash"] == ""
    assert first["state"] == snapshot.SnapshotState.RUNNING
    assert first["retry_after"] == 1
    get_hosts.assert_not_called()
    delay.assert_called_once_with(first["snapshot_id"])


def test_snapshot_create_capacity_exceeded_returns_unavailable_without_enqueue(mocker, monkeypatch):
    resources = import_module("monitor_web.performance.resources")
    monkeypatch.setattr(snapshot.settings, "HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ", 1, raising=False)
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    delay = mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")

    first = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    second = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 40, "end_time": 140}
    )

    assert first["state"] == snapshot.SnapshotState.RUNNING
    assert second["state"] == snapshot.SnapshotState.UNAVAILABLE
    assert second["retry_after"] == 5
    delay.assert_called_once_with(first["snapshot_id"])


def test_snapshot_create_enqueue_failure_returns_failed_with_short_retry(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    mocker.patch(
        "monitor_web.performance.tasks.build_host_metric_snapshot.delay",
        side_effect=RuntimeError("broker unavailable"),
    )

    response = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )

    assert response["state"] == snapshot.SnapshotState.FAILED
    assert response["retry_after"] == 5
    manifest = store.get_manifest(response["snapshot_id"])
    assert manifest["error_code"] == "enqueue_failed"
    assert cache.timeouts[store.pointer_key(manifest["fingerprint"])] == snapshot.FAILED_TTL
    assert cache.zscore(manifest["capacity_lease_key"], manifest["snapshot_id"]) is None


def test_create_renewal_loser_does_not_expire_worker_ready_snapshot(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    delay = mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")

    def worker_finishes_before_create_renewal(manifest):
        store.mark_ready(manifest["snapshot_id"], expected_sections=set())
        return False

    mocker.patch.object(store, "renew_capacity", side_effect=worker_finishes_before_create_renewal)

    response = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )

    assert response["state"] == snapshot.SnapshotState.READY
    assert store.get_manifest(response["snapshot_id"])["state"] == snapshot.SnapshotState.READY
    delay.assert_called_once_with(response["snapshot_id"])


def test_snapshot_create_reusing_ready_manifest_does_not_return_unvalidated_section_data(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    get_hosts = mocker.patch.object(resources.api.cmdb, "get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    delay = mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    params = {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    created = resources.CreateHostMetricSnapshotResource().perform_request(params)
    snapshot_id = created["snapshot_id"]
    store.update_manifest(
        snapshot_id,
        host_count=2,
        host_ids_hash=snapshot.build_host_ids_hash(host.bk_host_id for host in HOSTS[:2]),
    )
    for section in snapshot.SNAPSHOT_SECTIONS:
        store.write_section(snapshot_id, section, {HOSTS[0].bk_host_id: {"section": section}})
        store.mark_section_ready(snapshot_id, section)
    store.mark_ready(snapshot_id, expected_sections=set(snapshot.SNAPSHOT_SECTIONS))

    reused = resources.CreateHostMetricSnapshotResource().perform_request(params)

    assert reused["state"] == snapshot.SnapshotState.READY
    assert reused["revision"] == 0
    assert reused["data"] == {}
    get_hosts.assert_not_called()
    delay.assert_called_once_with(snapshot_id)

    get_hosts.return_value = HOSTS[:1]
    polled = resources.GetHostMetricSnapshotResource().perform_request(
        {
            **params,
            "start_time": reused["canonical_start_time"],
            "end_time": reused["canonical_end_time"],
            "snapshot_id": snapshot_id,
            "since_revision": reused["revision"],
        }
    )
    assert polled["state"] == snapshot.SnapshotState.EXPIRED
    assert polled["data"] == {}


def test_snapshot_running_poll_without_new_data_does_not_resolve_full_business_hosts(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    get_hosts = mocker.patch.object(resources.api.cmdb, "get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    get_hosts.reset_mock()

    result = resources.GetHostMetricSnapshotResource().perform_request(
        {
            "bk_biz_id": 2,
            "snapshot_id": created["snapshot_id"],
            "start_time": created["canonical_start_time"],
            "end_time": created["canonical_end_time"],
            "since_revision": 0,
        }
    )

    assert result["state"] == snapshot.SnapshotState.RUNNING
    get_hosts.assert_not_called()


@pytest.mark.parametrize("mismatch", ["tenant", "business", "scope", "time"])
def test_snapshot_poll_binding_mismatch_is_indistinguishable_from_unknown_and_does_not_touch_snapshot(mocker, mismatch):
    resources = import_module("monitor_web.performance.resources")
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    tenant = mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources, "get_request_username", return_value="admin")
    mocker.patch.object(resources.time, "time", return_value=201)
    mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    params = {
        "bk_biz_id": 2,
        "snapshot_id": created["snapshot_id"],
        "start_time": created["canonical_start_time"],
        "end_time": created["canonical_end_time"],
    }
    if mismatch == "tenant":
        tenant.return_value = "other-tenant"
    elif mismatch == "business":
        params["bk_biz_id"] = 3
    elif mismatch == "scope":
        params["bk_host_id"] = HOSTS[0].bk_host_id
    else:
        params["start_time"] += 1

    build_response = mocker.patch.object(store, "build_response")
    expire = mocker.patch.object(store, "expire")
    expected = resources.GetHostMetricSnapshotResource().perform_request({**params, "snapshot_id": "unknown-snapshot"})
    actual = resources.GetHostMetricSnapshotResource().perform_request(params)

    assert {key: value for key, value in actual.items() if key != "snapshot_id"} == {
        key: value for key, value in expected.items() if key != "snapshot_id"
    }
    assert actual["state"] == snapshot.SnapshotState.EXPIRED
    assert actual["data"] == {}
    build_response.assert_not_called()
    expire.assert_not_called()


def test_snapshot_data_bearing_poll_expires_when_resolved_host_set_changes(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    get_hosts = mocker.patch.object(resources.api.cmdb, "get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    store.update_manifest(
        created["snapshot_id"],
        host_count=2,
        host_ids_hash=snapshot.build_host_ids_hash(host.bk_host_id for host in HOSTS[:2]),
    )
    store.write_section(created["snapshot_id"], "agent_status", {HOSTS[0].bk_host_id: {"status": 1}})
    store.mark_section_ready(created["snapshot_id"], "agent_status")
    get_hosts.reset_mock()
    get_hosts.return_value = HOSTS[:1]

    result = resources.GetHostMetricSnapshotResource().perform_request(
        {
            "bk_biz_id": 2,
            "snapshot_id": created["snapshot_id"],
            "start_time": created["canonical_start_time"],
            "end_time": created["canonical_end_time"],
            "since_revision": 0,
        }
    )

    assert result["state"] == snapshot.SnapshotState.EXPIRED
    assert result["expired"] is True
    get_hosts.assert_called_once_with(bk_biz_id=2)


def test_snapshot_poll_revalidates_hash_when_section_completes_during_manifest_read(mocker):
    resources = import_module("monitor_web.performance.resources")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    mocker.patch.object(resources, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(resources, "get_request_tenant_id", return_value="system")
    mocker.patch.object(resources, "get_request", return_value=None)
    mocker.patch.object(resources.time, "time", return_value=201)
    get_hosts = mocker.patch.object(resources.api.cmdb, "get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch("monitor_web.performance.tasks.build_host_metric_snapshot.delay")
    created = resources.CreateHostMetricSnapshotResource().perform_request(
        {"bk_biz_id": 2, "start_time": 100, "end_time": 200}
    )
    store.update_manifest(
        created["snapshot_id"],
        host_count=2,
        host_ids_hash=snapshot.build_host_ids_hash(host.bk_host_id for host in HOSTS[:2]),
    )
    get_hosts.reset_mock()
    get_hosts.return_value = HOSTS[:1]

    def publish_then_build(snapshot_id, **kwargs):
        store.write_section(snapshot_id, "agent_status", {HOSTS[0].bk_host_id: {"status": 1}})
        store.mark_section_ready(snapshot_id, "agent_status")
        return snapshot.HostMetricSnapshotStore.build_response(store, snapshot_id, **kwargs)

    mocker.patch.object(store, "build_response", side_effect=publish_then_build)

    result = resources.GetHostMetricSnapshotResource().perform_request(
        {
            "bk_biz_id": 2,
            "snapshot_id": created["snapshot_id"],
            "start_time": created["canonical_start_time"],
            "end_time": created["canonical_end_time"],
            "since_revision": 0,
        }
    )

    assert result["state"] == snapshot.SnapshotState.EXPIRED
    assert result["data"] == {}
    get_hosts.assert_called_once_with(bk_biz_id=2)


def test_snapshot_task_only_marks_ready_after_all_sections_succeed(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(snapshot.build_host_ids_hash([host.bk_host_id for host in HOSTS[:2]])),
            "bk_tenant_id": "system",
            "username": "admin",
        },
    )
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(tasks, "resolve_host_metric_snapshot_scope", return_value=({"type": "business"}, HOSTS[:2]))
    mocker.patch.object(tasks.time, "time", return_value=200)
    mocker.patch.object(tasks, "_build_snapshot_section", side_effect=lambda section, *_: {1: {"section": section}})

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    response = store.build_response(manifest["snapshot_id"], since_revision=0, now=200)
    assert response["state"] == snapshot.SnapshotState.READY
    assert set(response["data"]) == set(tasks.SNAPSHOT_SECTIONS)
    assert response["revision"] == len(tasks.SNAPSHOT_SECTIONS)


def test_snapshot_task_does_not_compute_after_capacity_lease_is_lost(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(),
            "username": "admin",
        },
    )
    cache.zsets[manifest["capacity_lease_key"]] = {}
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    resolve_scope = mocker.patch.object(tasks, "resolve_host_metric_snapshot_scope")
    build_section = mocker.patch.object(tasks, "_build_snapshot_section")
    mocker.patch.object(tasks.time, "time", return_value=200)

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    assert store.get_manifest(manifest["snapshot_id"])["state"] == snapshot.SnapshotState.RUNNING
    resolve_scope.assert_not_called()
    build_section.assert_not_called()


def test_snapshot_task_degrades_and_keeps_successful_sections_when_one_section_fails(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    cache = FakeCache()
    store = snapshot.HostMetricSnapshotStore(cache=cache)
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(snapshot.build_host_ids_hash([host.bk_host_id for host in HOSTS[:2]])),
            "bk_tenant_id": "system",
            "username": "admin",
        },
    )
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(tasks, "resolve_host_metric_snapshot_scope", return_value=({"type": "business"}, HOSTS[:2]))
    mocker.patch.object(tasks.time, "time", return_value=200)

    def build(section, *_):
        if section == "performance_data":
            raise RuntimeError("partial")
        return {1: {"section": section}}

    mocker.patch.object(tasks, "_build_snapshot_section", side_effect=build)

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    response = store.build_response(manifest["snapshot_id"], now=200)
    assert response["state"] == snapshot.SnapshotState.DEGRADED
    assert response["failed_sections"] == ["performance_data"]
    assert set(response["data"]) == {"agent_status", "alarm_count", "process_status"}
    assert response["data"]["agent_status"] == {1: {"section": "agent_status"}}


def test_snapshot_task_degrades_and_keeps_partial_section_records(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(snapshot.build_host_ids_hash([host.bk_host_id for host in HOSTS[:2]])),
            "bk_tenant_id": "system",
            "username": "admin",
        },
    )
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(tasks, "resolve_host_metric_snapshot_scope", return_value=({"type": "business"}, HOSTS[:2]))
    mocker.patch.object(tasks.time, "time", return_value=200)

    def build(section, *_):
        if section == "performance_data":
            return {
                "data": {HOSTS[0].bk_host_id: {"cpu_usage": 81}},
                "state": snapshot.SnapshotState.PARTIAL,
            }
        return {HOSTS[0].bk_host_id: {"section": section}}

    mocker.patch.object(tasks, "_build_snapshot_section", side_effect=build)

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    response = store.build_response(manifest["snapshot_id"], now=200)
    assert response["state"] == snapshot.SnapshotState.DEGRADED
    assert response["failed_sections"] == []
    assert response["partial_sections"] == ["performance_data"]
    assert response["data"]["performance_data"] == {HOSTS[0].bk_host_id: {"cpu_usage": 81}}


def test_missing_section_blob_degrades_only_that_section_and_keeps_other_data(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "a" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    store.write_section(manifest["snapshot_id"], "agent_status", {1: {"status": 0}})
    store.mark_section_ready(manifest["snapshot_id"], "agent_status")
    store.mark_section_ready(manifest["snapshot_id"], "performance_data")
    store.mark_ready(manifest["snapshot_id"], expected_sections={"agent_status", "performance_data"})

    response = store.build_response(manifest["snapshot_id"])

    assert response["state"] == snapshot.SnapshotState.DEGRADED
    assert response["failed_sections"] == ["performance_data"]
    assert response["data"] == {"agent_status": {1: {"status": 0}}}


def test_missing_new_section_keeps_already_consumed_section_usable(monkeypatch):
    monkeypatch.setattr(snapshot, "uuid4", lambda: type("UUID", (), {"hex": "b" * 32})())
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get("sha256:fingerprint", make_payload())
    store.write_section(manifest["snapshot_id"], "agent_status", {1: {"status": 0}})
    store.mark_section_ready(manifest["snapshot_id"], "agent_status")
    store.mark_section_ready(manifest["snapshot_id"], "performance_data")
    store.mark_ready(manifest["snapshot_id"], expected_sections={"agent_status", "performance_data"})

    response = store.build_response(manifest["snapshot_id"], since_revision=1)

    assert response["state"] == snapshot.SnapshotState.DEGRADED
    assert response["failed_sections"] == ["performance_data"]
    assert response["data"] == {}


def test_snapshot_task_publishes_ready_empty_sections_for_legitimate_empty_scope(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(""),
            "host_count": 0,
            "bk_tenant_id": "system",
            "username": "admin",
        },
    )
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    resolve_scope = mocker.patch.object(
        tasks,
        "resolve_host_metric_snapshot_scope",
        return_value=({"type": "business"}, []),
    )
    build_section = mocker.patch.object(tasks, "_build_snapshot_section", return_value={})
    mocker.patch.object(tasks.time, "time", return_value=200)

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    response = store.build_response(manifest["snapshot_id"], now=200)
    assert response["state"] == snapshot.SnapshotState.READY
    assert response["host_count"] == 0
    assert response["host_ids_hash"] == snapshot.build_host_ids_hash([])
    resolve_scope.assert_called_once()
    assert build_section.call_count == len(tasks.SNAPSHOT_SECTIONS)


def test_snapshot_task_fails_when_scope_resolution_raises(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    store = snapshot.HostMetricSnapshotStore(cache=FakeCache())
    manifest, _ = store.create_or_get(
        "sha256:fingerprint",
        {
            **make_payload(""),
            "host_count": 0,
            "bk_tenant_id": "system",
            "username": "admin",
        },
    )
    mocker.patch.object(tasks, "HostMetricSnapshotStore", return_value=store)
    mocker.patch.object(tasks, "resolve_host_metric_snapshot_scope", side_effect=RuntimeError("cmdb unavailable"))
    build_section = mocker.patch.object(tasks, "_build_snapshot_section")
    mocker.patch.object(tasks.time, "time", return_value=200)

    tasks.build_host_metric_snapshot.run(manifest["snapshot_id"])

    response = store.build_response(manifest["snapshot_id"], now=200)
    assert response["state"] == snapshot.SnapshotState.FAILED
    assert store.get_manifest(manifest["snapshot_id"])["error_code"] == "task_failed"
    build_section.assert_not_called()


def test_full_business_snapshot_section_uses_explicit_empty_target_filter(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    get_agent_status = mocker.patch.object(
        tasks.SearchHostMetricResource,
        "get_agent_status",
        side_effect=lambda *_args, incomplete_callback, **_kwargs: incomplete_callback(),
    )

    result = tasks._build_snapshot_section(
        "agent_status",
        2,
        HOSTS[:1],
        100,
        200,
        {"type": "business"},
    )

    assert get_agent_status.call_args.kwargs["target_filter"] == {}
    assert get_agent_status.call_args.kwargs["fail_on_incomplete"] is False
    assert result == {"data": {HOSTS[0].bk_host_id: {}}, "state": snapshot.SnapshotState.PARTIAL}


def test_full_business_snapshot_alarm_section_omits_linear_host_ip_terms(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    get_alarm_count = mocker.patch.object(tasks.SearchHostMetricResource, "get_alarm_count")

    tasks._build_snapshot_section(
        "alarm_count",
        2,
        HOSTS[:1],
        100,
        200,
        {"type": "business"},
    )

    assert get_alarm_count.call_args.kwargs["filter_by_host_ip"] is False


def test_snapshot_section_sets_tenant_and_user_context_inside_worker_thread(mocker):
    tasks = import_module("monitor_web.performance.tasks")
    set_tenant = mocker.patch.object(tasks, "set_local_tenant_id")
    set_user = mocker.patch.object(tasks, "set_local_username")
    mocker.patch.object(tasks.SearchHostMetricResource, "get_agent_status")

    tasks._build_snapshot_section(
        "agent_status",
        2,
        HOSTS[:1],
        100,
        200,
        {"type": "business"},
        bk_tenant_id="tenant-a",
        username="admin",
    )

    set_tenant.assert_called_once_with("tenant-a")
    set_user.assert_called_once_with("admin")


def test_snapshot_task_is_dedicated_and_ignores_celery_result():
    tasks = import_module("monitor_web.performance.tasks")

    assert tasks.build_host_metric_snapshot.ignore_result is True
    assert tasks.build_host_metric_snapshot.queue == "celery_resource"


def test_snapshot_task_is_registered_from_monitor_web_task_module():
    root_tasks = import_module("monitor_web.tasks")
    snapshot_tasks = import_module("monitor_web.performance.tasks")

    assert root_tasks.build_host_metric_snapshot is snapshot_tasks.build_host_metric_snapshot
