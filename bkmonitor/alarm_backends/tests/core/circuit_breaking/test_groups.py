"""Rule-group regression tests using a private, ephemeral Redis process."""

import copy
import json
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from redis.client import Redis
from redis.exceptions import ConnectionError

from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager
from alarm_backends.core.circuit_breaking.groups import (
    MAX_GROUPS,
    MAX_GROUP_BYTES,
    MAX_MODULE_BYTES,
    MAX_REVISION,
    CircuitBreakingGroupError,
    CircuitBreakingRuleGroupStore,
    capabilities,
    validate_conditions,
)
from alarm_backends.core.circuit_breaking.manager import (
    AccessDataCircuitBreakingManager,
    ActionCircuitBreakingManager,
    AlertBuilderCircuitBreakingManager,
    AlertManagerCircuitBreakingManager,
)
from alarm_backends.core.circuit_breaking.matcher import gen_circuit_breaking_matcher


@pytest.fixture(scope="module")
def isolated_redis():
    executable = shutil.which("redis-server")
    if not executable:
        pytest.skip("redis-server is required for atomic rule-group tests")
    with tempfile.TemporaryDirectory(prefix="cb-", dir="/tmp") as directory:
        socket = str(Path(directory) / "redis.sock")
        process = subprocess.Popen(
            [executable, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client = Redis(unix_socket_path=socket, decode_responses=True)
        try:
            for _ in range(100):
                try:
                    if client.ping():
                        break
                except ConnectionError:
                    if process.poll() is not None:
                        pytest.fail("private redis-server failed to start")
                    time.sleep(0.01)
            else:
                pytest.fail("private redis-server did not become ready")
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture
def store(isolated_redis, monkeypatch):
    # This process and database belong only to this module's fixture.
    isolated_redis.flushdb()
    monkeypatch.setattr(CircuitBreakingCacheManager, "cache", isolated_redis)
    return CircuitBreakingRuleGroupStore(isolated_redis)


def rule(key="strategy_id", value="101", method="eq", connector="and"):
    return {"key": key, "method": method, "value": [value], "condition": connector}


def create(store, module="access.data", conditions=None, ttl=60):
    return store.create(module, str(uuid4()), conditions or [rule()], ttl, "incident mitigation", "operator")


def state(store, module="access.data"):
    key = store.get_cache_key(module)
    return store.redis.hgetall(key), store.redis.execute_command("PEXPIRETIME", key)


def expire(store, group):
    group = copy.deepcopy(group)
    clock = store.redis.time()
    now = clock[0] * 1000 + clock[1] // 1000
    group.update(created_at_ms=now - 10000, updated_at_ms=now - 9000, expires_at_ms=now - 5000)
    store.redis.hset(store.get_cache_key(group["module"]), group["group_id"], json.dumps(group))


def test_lifecycle_preserves_identity_and_independent_deadlines(store):
    first = create(store, ttl=60)
    second = create(store, conditions=[rule(value="102")], ttl=120)
    before = store.snapshot("access.data")
    assert len(before["groups"]) == 2
    assert first["revision"] == 1
    assert first["expires_at_ms"] - first["created_at_ms"] == 60000
    assert abs(before["server_time_ms"] - first["created_at_ms"]) < 1000
    key = store.get_cache_key("access.data")
    assert state(store)[1] == second["expires_at_ms"]

    updated = store.update(
        "access.data", first["group_id"], 1, conditions=[rule(value="103")], reason="updated reason", operator="editor"
    )
    assert updated["group_id"] == first["group_id"]
    assert updated["module"] == first["module"]
    assert updated["created_at_ms"] == first["created_at_ms"]
    assert updated["expires_at_ms"] == first["expires_at_ms"]
    assert updated["revision"] == 2
    assert updated["reason"] == "updated reason"
    assert updated["operator"] == "editor"
    assert state(store)[1] == second["expires_at_ms"]

    extended = store.extend("access.data", first["group_id"], 2, 180, "extender")
    assert extended["expires_at_ms"] == first["expires_at_ms"] + 180000
    assert extended["revision"] == 3
    assert state(store)[1] == extended["expires_at_ms"]
    removed = store.revoke("access.data", first["group_id"], 3, "revoker")
    assert removed == extended
    assert state(store)[1] == second["expires_at_ms"]
    assert store.snapshot("access.data")["groups"] == [second]
    store.revoke("access.data", second["group_id"], 1, "revoker")
    assert not store.redis.exists(key)


@pytest.mark.parametrize("operation", ["create", "update", "extend", "revoke"])
def test_conflict_has_no_side_effects_even_with_expired_groups(store, operation):
    active, expired = create(store), create(store)
    expire(store, expired)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        if operation == "create":
            store.create("access.data", active["group_id"], [rule()], 60, "reason", "operator")
        elif operation == "update":
            store.update("access.data", active["group_id"], 2, reason="new reason", operator="operator")
        elif operation == "extend":
            store.extend("access.data", active["group_id"], 2, 60, "operator")
        else:
            store.revoke("access.data", active["group_id"], 2, "operator")
    assert error.value.code == ("already_exists" if operation == "create" else "revision_conflict")
    assert state(store) == before


@pytest.mark.parametrize("operation", ["update", "extend", "revoke"])
def test_logical_expiry_cannot_be_resurrected(store, operation):
    expired = create(store)
    create(store, ttl=120)
    expire(store, expired)
    before = state(store)
    assert all(group["group_id"] != expired["group_id"] for group in store.snapshot("access.data")["groups"])
    with pytest.raises(CircuitBreakingGroupError) as error:
        if operation == "update":
            store.update("access.data", expired["group_id"], 1, reason="new reason", operator="operator")
        elif operation == "extend":
            store.extend("access.data", expired["group_id"], 1, 60, "operator")
        else:
            store.revoke("access.data", expired["group_id"], 1, "operator")
    assert error.value.code == "not_found"
    assert state(store) == before
    create(store)
    assert not store.redis.hexists(store.get_cache_key("access.data"), expired["group_id"])


def test_extending_uses_old_deadline_and_rejects_excess_remaining_time(store):
    group = create(store, ttl=86400)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError, match="remaining lifetime"):
        store.extend("access.data", group["group_id"], 1, 1, "operator")
    assert state(store) == before


def test_concurrent_revisions_allow_exactly_one_writer(store):
    group = create(store)

    def update(reason):
        try:
            return store.update("access.data", group["group_id"], 1, reason=reason, operator="operator")
        except CircuitBreakingGroupError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, ["first update", "second update"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("revision_conflict") == 1
    assert store.snapshot("access.data")["groups"][0]["revision"] == 2


def test_capacity_and_write_cleanup_are_atomic(store):
    groups = [create(store) for _ in range(MAX_GROUPS)]
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        create(store)
    assert error.value.code == "capacity_exceeded"
    assert state(store) == before
    expire(store, groups[0])
    create(store)
    assert len(store.snapshot("access.data")["groups"]) == MAX_GROUPS
    assert not store.redis.hexists(store.get_cache_key("access.data"), groups[0]["group_id"])


@pytest.mark.parametrize(
    "conditions",
    [
        [],
        [dict(rule(), unknown=True)],
        [dict(rule(), method="unknown")],
        [dict(rule(), condition="xor")],
        [dict(rule(), key="labels")],
        [dict(rule(), value=[])],
        [dict(rule(), value=False)],
        [dict(rule(), value="")],
        [dict(rule(), value=None)],
        [dict(rule(), value=[None])],
        [dict(rule(), value=[{}])],
        [dict(rule(), value=[float("nan")])],
        [dict(rule(), value=[float("inf")])],
        [dict(rule(), value=["["], method="reg")],
        [dict(rule(), value=["word"], method="gt")],
        [rule(), dict(rule(), method="unknown")],
        [rule()] * 21,
        [dict(rule(), value=list(range(101)))],
    ],
)
def test_invalid_condition_never_creates_a_partial_or_empty_group(store, conditions):
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError):
        store.create("access.data", str(uuid4()), conditions, 60, "reason", "operator")
    assert state(store) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("ttl_seconds", 0),
        ("ttl_seconds", 86401),
        ("ttl_seconds", True),
        ("ttl_seconds", 1.5),
        ("reason", "x" * 513),
        ("reason", ""),
        ("reason", "   "),
        ("operator", "x" * 33),
        ("operator", ""),
        ("group_id", "bad-id"),
        ("module", "unknown"),
    ],
)
def test_invalid_group_fields_never_write(store, field, value):
    kwargs = dict(
        module="access.data",
        group_id=str(uuid4()),
        conditions=[rule()],
        ttl_seconds=60,
        reason="reason",
        operator="operator",
    )
    kwargs[field] = value
    with pytest.raises(CircuitBreakingGroupError):
        store.create(**kwargs)
    assert store.redis.dbsize() == 0


def test_falsy_zero_is_retained_and_missing_dimensions_fail_for_negative_and_regex_methods(store):
    conditions = validate_conditions("access.data", [dict(rule(), value=0)])
    assert conditions[0]["value"] == ["0"]
    matcher = gen_circuit_breaking_matcher(conditions)
    assert matcher.is_match({"strategy_id": "0"})
    assert not matcher.is_match({"strategy_id": "101"})
    for method in ("neq", "reg", "nreg", "exclude"):
        matcher = gen_circuit_breaking_matcher(validate_conditions("access.data", [rule(method=method)]))
        assert not matcher.is_match({})


def test_and_or_and_multiple_groups_use_existing_evaluation_contexts(store):
    create(
        store,
        conditions=[rule(), rule("bk_biz_id", "2"), rule("strategy_source", "custom:time_series", connector="or")],
    )
    create(store, conditions=[rule(value="102")])
    manager = AccessDataCircuitBreakingManager()
    assert manager
    assert manager.is_circuit_breaking(strategy_id=101, bk_biz_id=2)
    assert manager.is_circuit_breaking(strategy_id=102)
    assert manager.is_circuit_breaking(data_source_label="custom", data_type_label="time_series")
    assert not manager.is_circuit_breaking(strategy_id=101)
    assert not manager.is_strategy_only_circuit_breaking(101)
    assert manager.is_strategy_only_circuit_breaking(102)
    assert not manager.is_circuit_breaking(bk_biz_id=2)


def test_existing_manager_stops_using_expired_groups_without_a_redis_read(store, monkeypatch):
    create(store, ttl=1)
    manager = AccessDataCircuitBreakingManager()
    assert manager.is_strategy_only_circuit_breaking(101)
    monkeypatch.setattr(
        "alarm_backends.core.circuit_breaking.manager.time.monotonic", lambda: manager._group_snapshot_time + 2
    )
    monkeypatch.setattr(store.redis, "eval", lambda *args: pytest.fail("matching must not query Redis"))
    assert not manager
    assert not manager.is_strategy_only_circuit_breaking(101)


def test_legacy_setters_do_not_change_groups_and_groups_do_not_change_legacy(store):
    CircuitBreakingCacheManager.set_config("access.data", [rule(value="102")])
    legacy_key = CircuitBreakingCacheManager.get_cache_key("access.data")
    legacy_value = store.redis.get(legacy_key)
    group = create(store)
    assert store.redis.get(legacy_key) == legacy_value
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(102)
    CircuitBreakingCacheManager.set_config("access.data", [])
    assert store.snapshot("access.data")["groups"] == [group]
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(101)
    assert not AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(102)


def test_invalid_new_hash_and_invalid_legacy_are_isolated(store):
    CircuitBreakingCacheManager.set_config("access.data", [rule()])
    store.redis.hset(store.get_cache_key("access.data"), str(uuid4()), "broken json")
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(101)
    store.redis.delete(store.get_cache_key("access.data"))
    create(store)
    store.redis.set(CircuitBreakingCacheManager.get_cache_key("access.data"), "broken json")
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(101)


def test_group_source_connection_failure_does_not_break_legacy(store, monkeypatch):
    CircuitBreakingCacheManager.set_config("access.data", [rule()])
    monkeypatch.setattr(
        CircuitBreakingRuleGroupStore, "snapshot", lambda *args: (_ for _ in ()).throw(ConnectionError())
    )
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(101)


def test_alert_manager_preserves_only_legacy_builder_fallback(store):
    CircuitBreakingCacheManager.set_config("alert.builder", [rule(value="101")])
    create(store, "alert.builder", conditions=[rule(value="102")])
    create(store, "alert.manager", conditions=[rule(value="103")])
    manager = AlertManagerCircuitBreakingManager()
    assert manager.is_strategy_only_circuit_breaking(101)
    assert not manager.is_strategy_only_circuit_breaking(102)
    assert manager.is_strategy_only_circuit_breaking(103)
    assert AlertBuilderCircuitBreakingManager().is_strategy_only_circuit_breaking(102)
    CircuitBreakingCacheManager.set_config("alert.manager", [rule(value="104")])
    manager = AlertManagerCircuitBreakingManager()
    assert not manager.is_strategy_only_circuit_breaking(101)
    assert manager.is_strategy_only_circuit_breaking(103)
    assert manager.is_strategy_only_circuit_breaking(104)


def test_action_plugin_and_source_dimension_matching(store):
    create(store, "action", conditions=[rule("plugin_type", "notice"), rule("bk_biz_id", "2")])
    manager = ActionCircuitBreakingManager()
    assert manager.is_circuit_breaking(plugin_type="notice", bk_biz_id=2)
    assert not manager.is_circuit_breaking(plugin_type="webhook", bk_biz_id=2)
    assert not manager.is_circuit_breaking(bk_biz_id=2)


def test_capabilities_disclose_existing_contexts_without_labels():
    capabilities_by_module = {
        module: capabilities(module) for module in ("access.data", "alert.builder", "alert.manager", "action")
    }
    access = capabilities_by_module["access.data"]
    assert next(c for c in access["evaluation_contexts"] if c["name"] == "before_pull")["dimensions"] == ["strategy_id"]
    assert all("labels" not in result["dimensions"] for result in capabilities_by_module.values())
    assert "plugin_type" in capabilities_by_module["action"]["dimensions"]
    assert "plugin_type" not in access["dimensions"]


def test_numeric_values_keep_the_matcher_representation_across_lua_encoding(store):
    for value in (9007199254740993, 0.1234567890123456):
        group = create(store, conditions=[rule(value=value)])
        assert group["conditions"][0]["value"] == [str(value)]
        assert AccessDataCircuitBreakingManager().is_circuit_breaking(strategy_id=value)


@pytest.mark.parametrize("expected_revision", [0, True, "1", None])
def test_invalid_revisions_never_write(store, expected_revision):
    group = create(store)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError):
        store.update("access.data", group["group_id"], expected_revision, reason="changed", operator="operator")
    assert state(store) == before


def test_invalid_update_does_not_replace_any_condition(store):
    group = create(store)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError):
        store.update(
            "access.data",
            group["group_id"],
            1,
            conditions=[rule(), dict(rule(), method="unknown")],
            operator="operator",
        )
    assert state(store) == before


def test_unknown_group_and_corrupt_hash_fail_without_mutation(store):
    create(store)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        store.revoke("access.data", str(uuid4()), 1, "operator")
    assert error.value.code == "not_found"
    assert state(store) == before
    store.redis.hset(store.get_cache_key("access.data"), str(uuid4()), "invalid JSON")
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        create(store)
    assert error.value.code == "corrupt_state"
    assert state(store) == before


def test_group_budget_counts_utf8_bytes_and_rejects_oversized_updates(store):
    ascii_values = ["x" * 1024] * 10
    group = create(store, conditions=[dict(rule(), value=ascii_values)])
    assert len(store.redis.hget(store.get_cache_key("access.data"), group["group_id"]).encode()) < MAX_GROUP_BYTES
    before = state(store)
    # Character count is unchanged; UTF-8 storage doubles for these values.
    conditions = [dict(rule(), value=["é" * 1024] * 10)]
    with pytest.raises(CircuitBreakingGroupError, match="group byte limit"):
        store.update("access.data", group["group_id"], 1, conditions=conditions, operator="operator")
    assert state(store) == before
    with pytest.raises(CircuitBreakingGroupError, match="group byte limit"):
        create(store, conditions=conditions)
    assert state(store) == before


def test_module_budget_is_atomic_and_disclosed(store):
    conditions = [dict(rule(), value=["x" * 1024] * 14)]
    for _ in range(MAX_GROUPS):
        before = state(store)
        try:
            create(store, conditions=conditions)
        except CircuitBreakingGroupError as error:
            assert error.code == "capacity_exceeded"
            assert "module rule group byte limit" in str(error)
            assert state(store) == before
            break
    else:
        pytest.fail("module byte budget was not enforced before the group count limit")
    payload = store.redis.hgetall(store.get_cache_key("access.data"))
    assert sum(len(field.encode()) + len(value.encode()) for field, value in payload.items()) <= MAX_MODULE_BYTES
    assert capabilities("access.data")["limits"]["group_bytes"] == MAX_GROUP_BYTES
    assert capabilities("access.data")["limits"]["module_bytes"] == MAX_MODULE_BYTES


def test_snapshot_rejects_oversized_stored_values_without_breaking_legacy(store):
    CircuitBreakingCacheManager.set_config("access.data", [rule()])
    store.redis.hset(store.get_cache_key("access.data"), str(uuid4()), "é" * MAX_GROUP_BYTES)
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        store.snapshot("access.data")
    assert error.value.code == "corrupt_state"
    assert state(store) == before
    assert AccessDataCircuitBreakingManager().is_strategy_only_circuit_breaking(101)


def test_revision_limit_still_allows_revocation(store):
    group = create(store)
    group["revision"] = MAX_REVISION
    store.redis.hset(store.get_cache_key("access.data"), group["group_id"], json.dumps(group))
    before = state(store)
    with pytest.raises(CircuitBreakingGroupError) as error:
        store.extend("access.data", group["group_id"], MAX_REVISION, 1, "operator")
    assert error.value.code == "revision_conflict"
    assert state(store) == before
    assert store.revoke("access.data", group["group_id"], MAX_REVISION, "operator") == group
    assert not store.snapshot("access.data")["groups"]


def test_oversized_conditions_are_rejected_before_redis_or_matcher_compilation(store, monkeypatch):
    monkeypatch.setattr(store.redis, "eval", lambda *args: pytest.fail("oversized conditions must not reach Redis"))
    monkeypatch.setattr(
        "alarm_backends.core.circuit_breaking.groups.gen_circuit_breaking_matcher",
        lambda *args: pytest.fail("oversized conditions must not be compiled"),
    )
    with pytest.raises(CircuitBreakingGroupError, match="group byte limit"):
        create(store, conditions=[dict(rule(), value=["x" * 1024] * 100)] * 20)
