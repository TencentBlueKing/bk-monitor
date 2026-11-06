"""Isolated circuit breaking management, readback and bridge contract tests."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import fakeredis
from redis.exceptions import ConnectionError

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli import circuit_breaking as rpc
from kernel_api.rpc.functions.bkm_cli.cache import read_config_cache

GROUP_ID = "c40993a1-2a9c-4d7d-8539-c06352e648b7"
OTHER_GROUP_ID = "d453e3e0-7ff1-4b52-a7d2-989a2ac2ca75"
CONDITIONS = [{"key": "bk_biz_id", "method": "eq", "value": [2], "condition": "and"}]


class GroupError(ValueError):
    def __init__(self, message, code="validation_error"):
        super().__init__(message)
        self.code = code


def request_for(operation):
    params = {
        "operation": operation,
        "module": "access.data",
        "confirmed": True,
        "operator": "alice",
        "group_id": GROUP_ID,
    }
    if operation == "create":
        params.update(conditions=deepcopy(CONDITIONS), ttl_seconds=300, reason="maintenance")
    else:
        params["expected_revision"] = 1
    if operation == "update":
        params["reason"] = "adjusted maintenance"
    elif operation == "extend":
        params["extend_seconds"] = 60
    return params


@pytest.fixture
def backend(monkeypatch):
    group = {
        "group_id": GROUP_ID,
        "module": "access.data",
        "conditions": deepcopy(CONDITIONS),
        "reason": "maintenance",
        "operator": "alice",
        "revision": 1,
        "created_at_ms": 1000,
        "updated_at_ms": 1000,
        "expires_at_ms": 301000,
    }
    store = Mock()
    for operation in rpc.OPERATION_FIELDS:
        getattr(store, operation).return_value = deepcopy(group)
    store.snapshot.return_value = {"module": "access.data", "server_time_ms": 2000, "groups": [deepcopy(group)]}
    module = SimpleNamespace(
        CircuitBreakingRuleGroupStore=Mock(return_value=store),
        CircuitBreakingGroupError=GroupError,
        capabilities=Mock(return_value={"module": "access.data", "evaluation_contexts": []}),
        store=store,
        group=group,
    )
    monkeypatch.setattr(rpc, "_group_backend", lambda: module)
    return module


@pytest.fixture
def legacy(monkeypatch):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    pipeline = Mock()
    pipeline.__enter__ = Mock(return_value=pipeline)
    pipeline.__exit__ = Mock(return_value=False)
    rules = [{"key": "strategy_id", "method": "eq", "value": [12345]}]
    raw = json.dumps(rules).encode()
    pipeline.execute.return_value = [len(raw), raw, 60000]
    cache = Mock()
    cache.pipeline.return_value = pipeline
    monkeypatch.setattr(CircuitBreakingCacheManager, "cache", cache)
    return SimpleNamespace(cache=cache, pipeline=pipeline, rules=rules)


@pytest.mark.parametrize("operation", rpc.OPERATION_FIELDS)
def test_management_dispatches_exact_operation_fields_and_trims_operator(backend, operation):
    params = request_for(operation)
    params.update(operator=" alice ", bk_tenant_id="tenant-a")
    original = deepcopy(params)
    result = rpc.manage_circuit_breaking(params)
    expected = {key: params[key] for key in rpc.OPERATION_FIELDS[operation] if key in params}
    expected.update(module="access.data", operator="alice")
    getattr(backend.store, operation).assert_called_once_with(**expected)
    assert result == {
        "operation": operation,
        "module": "access.data",
        "group": backend.group,
        "requested_operator": "alice",
    }
    assert params == original


@pytest.mark.parametrize(
    "operation,field",
    [
        (operation, field)
        for operation in rpc.OPERATION_FIELDS
        for field in ("unknown", "ttl_seconds", "expected_revision", "conditions", "extend_seconds", "reason")
        if field not in rpc.OPERATION_FIELDS[operation]
    ],
)
def test_management_rejects_unknown_and_inapplicable_fields_before_store(backend, operation, field):
    params = request_for(operation)
    params[field] = 1
    with pytest.raises(CustomException, match="不支持的参数"):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("field", ["operation", "module", "confirmed", "operator"])
def test_management_requires_every_public_field(backend, field):
    params = request_for("create")
    del params[field]
    with pytest.raises(CustomException):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("params", [None, [], "invalid"])
def test_management_rejects_non_object_requests(backend, params):
    with pytest.raises(CustomException, match="params must be an object"):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("operation", rpc.OPERATION_FIELDS)
def test_management_rejects_every_missing_or_null_operation_field(backend, operation):
    for field in rpc.REQUIRED_FIELDS[operation]:
        params = request_for(operation)
        del params[field]
        with pytest.raises(CustomException, match="missing required parameters"):
            rpc.manage_circuit_breaking(params)
    for field in set(request_for(operation)) | {"bk_tenant_id"}:
        params = request_for(operation)
        params[field] = None
        with pytest.raises(CustomException):
            rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("operator", [None, "", "  ", "<operator>", "${USER}", "your-username", "a" * 33, 123])
def test_management_rejects_missing_placeholder_or_oversized_operator(backend, operator):
    params = request_for("create")
    params["operator"] = operator
    with pytest.raises(CustomException, match="operator"):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("confirmed", [None, False, 1, "true"])
def test_management_requires_explicit_boolean_confirmation(backend, confirmed):
    params = request_for("create")
    params["confirmed"] = confirmed
    with pytest.raises(CustomException, match="confirmed=true"):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "snapshot"),
        ("operation", []),
        ("module", "detect"),
        ("module", None),
        ("group_id", "not-a-uuid"),
        ("group_id", GROUP_ID.replace("-", "")),
    ],
)
def test_management_rejects_invalid_operation_module_and_uuid(backend, field, value):
    params = request_for("create")
    params[field] = value
    with pytest.raises(CustomException):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize(
    "patch", [{"reason": "changed"}, {"conditions": CONDITIONS}, {"reason": "changed", "conditions": CONDITIONS}]
)
def test_update_accepts_one_or_both_optional_changes(backend, patch):
    params = request_for("update")
    del params["reason"]
    params.update(patch)
    rpc.manage_circuit_breaking(params)
    assert all(backend.store.update.call_args.kwargs[key] == value for key, value in patch.items())


def test_update_requires_a_change_and_rejects_null_optional_field(backend):
    params = request_for("update")
    del params["reason"]
    with pytest.raises(CustomException, match="requires conditions or reason"):
        rpc.manage_circuit_breaking(params)
    params["conditions"] = None
    with pytest.raises(CustomException, match="cannot be null"):
        rpc.manage_circuit_breaking(params)
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


@pytest.mark.parametrize("operation", rpc.OPERATION_FIELDS)
def test_management_preserves_core_error_code_without_silent_success(backend, operation):
    getattr(backend.store, operation).side_effect = GroupError("revision changed", "revision_conflict")
    with pytest.raises(CustomException, match="revision_conflict: revision changed"):
        rpc.manage_circuit_breaking(request_for(operation))


def test_management_storage_error_does_not_expose_connection_details(backend):
    backend.store.create.side_effect = ConnectionError("private connection details")
    with pytest.raises(CustomException, match="read back before retrying") as error:
        rpc.manage_circuit_breaking(request_for("create"))
    assert "private" not in str(error.value)


def test_registry_and_service_bridge_audit_use_declared_and_trusted_identities(backend, monkeypatch):
    op = BkmCliOpRegistry.resolve("manage-circuit-breaking")
    assert (op.capability_level, op.risk_level, op.requires_confirmation) == ("admin", "mutation", True)
    monkeypatch.setattr(
        "kernel_api.resource.bkm_cli.inject_bk_tenant_id", lambda params: {**params, "bk_tenant_id": "tenant-a"}
    )
    monkeypatch.setattr("kernel_api.resource.bkm_cli.request_context.get_request_username", lambda: "trusted-caller")
    result = BkmCliOpCallResource().perform_request({"op_id": op.op_id, "params": request_for("create")})
    assert result["func_name"] == "bkm_cli.manage_circuit_breaking"
    assert result["result"]["requested_operator"] == "alice"
    assert result["audit"]["declared_operator"] == "alice"
    assert result["audit"]["request_caller"] == "trusted-caller"
    assert "bk_tenant_id" not in backend.store.create.call_args.kwargs


def read_request(**params):
    return {"cache_type": "circuit_breaking", "params": {"module": "access.data", **params}}


def test_snapshot_separates_legacy_and_active_managed_groups(backend, legacy):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    result = read_config_cache({**read_request(), "operation": "snapshot", "bk_tenant_id": "tenant-a"})
    assert result["exists"] is True
    assert result["params"] == {"module": "access.data"}
    assert result["data"] == {
        "module": "access.data",
        "legacy": {"exists": True, "ttl_ms": 60000, "rules": legacy.rules},
        "legacy_fallback": None,
        "groups": [backend.group],
        "server_time_ms": 2000,
        "capabilities": backend.capabilities.return_value,
    }
    key = CircuitBreakingCacheManager.get_cache_key("access.data")
    legacy.cache.pipeline.assert_called_once_with(transaction=True)
    legacy.pipeline.strlen.assert_called_once_with(key)
    legacy.pipeline.getrange.assert_called_once_with(key, 0, rpc.MAX_LEGACY_BYTES)
    legacy.pipeline.pttl.assert_called_once_with(key)
    backend.store.snapshot.assert_called_once_with("access.data")


def test_snapshot_group_id_readback_does_not_confuse_legacy_with_revoked_group(backend, legacy):
    assert read_config_cache(read_request(group_id=GROUP_ID))["exists"] is True
    result = read_config_cache(read_request(group_id=OTHER_GROUP_ID))
    assert result["exists"] is False
    assert result["data"]["groups"] == []
    assert result["data"]["legacy"]["exists"] is True


@pytest.mark.parametrize("own_legacy", [[0, b"", -2], [2, b"[]", 60000]])
def test_manager_empty_legacy_exposes_only_builder_legacy_fallback(backend, legacy, own_legacy):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    raw = json.dumps(legacy.rules).encode()
    legacy.pipeline.execute.side_effect = [own_legacy, [len(raw), raw, 40000]]
    backend.store.snapshot.return_value["groups"] = []
    result = read_config_cache(read_request(module="alert.manager"))
    assert result["exists"] is True
    assert result["data"]["legacy"]["rules"] == []
    assert result["data"]["legacy_fallback"] == {
        "module": "alert.builder",
        "exists": True,
        "ttl_ms": 40000,
        "rules": legacy.rules,
        "adopted": True,
    }
    assert [call.args[0] for call in legacy.pipeline.strlen.call_args_list] == [
        CircuitBreakingCacheManager.get_cache_key("alert.manager"),
        CircuitBreakingCacheManager.get_cache_key("alert.builder"),
    ]
    backend.store.snapshot.assert_called_once_with("alert.manager")


def test_manager_group_id_exists_tracks_only_managed_group_with_active_fallback(backend, legacy):
    raw = json.dumps(legacy.rules).encode()
    legacy.pipeline.execute.side_effect = [[0, b"", -2], [len(raw), raw, 40000]]
    backend.store.snapshot.return_value["groups"] = []
    result = read_config_cache(read_request(module="alert.manager", group_id=GROUP_ID))
    assert result["exists"] is False
    assert result["data"]["legacy_fallback"]["adopted"] is True


def test_manager_nonempty_legacy_does_not_read_builder_fallback(backend, legacy):
    result = read_config_cache(read_request(module="alert.manager"))
    assert result["data"]["legacy_fallback"] is None
    assert legacy.pipeline.execute.call_count == 1


@pytest.mark.parametrize("module", ["access.data", "alert.builder", "action"])
def test_other_modules_empty_legacy_never_read_builder_fallback(backend, legacy, module):
    legacy.pipeline.execute.return_value = [0, b"", -2]
    result = read_config_cache(read_request(module=module))
    assert result["data"]["legacy_fallback"] is None
    assert legacy.pipeline.execute.call_count == 1


@pytest.mark.parametrize("fallback", [[0, b"", -2], [2, b"[]", 40000]])
def test_manager_without_fallback_rules_does_not_claim_adoption(backend, legacy, fallback):
    legacy.pipeline.execute.side_effect = [[0, b"", -2], fallback]
    backend.store.snapshot.return_value["groups"] = []
    result = read_config_cache(read_request(module="alert.manager"))
    assert result["data"]["legacy_fallback"]["adopted"] is False
    assert result["exists"] is (fallback[2] != -2)


@pytest.mark.parametrize("failure", [ConnectionError("private connection details"), [3, b"bad", 40000]])
def test_manager_fallback_read_errors_remain_explicit(backend, legacy, failure):
    legacy.pipeline.execute.side_effect = [[0, b"", -2], failure]
    with pytest.raises(CustomException):
        read_config_cache(read_request(module="alert.manager"))
    backend.store.snapshot.assert_not_called()


def test_snapshot_missing_legacy_and_groups_is_empty(backend, legacy):
    legacy.pipeline.execute.return_value = [0, b"", -2]
    backend.store.snapshot.return_value["groups"] = []
    result = read_config_cache(read_request())
    assert result["exists"] is False
    assert result["data"]["legacy"] == {"exists": False, "ttl_ms": -2, "rules": []}


@pytest.mark.parametrize("ttl_ms", [-1, 0, 60000])
def test_snapshot_retains_empty_legacy_key_and_module_ttl(backend, legacy, ttl_ms):
    legacy.pipeline.execute.return_value = [2, b"[]", ttl_ms]
    result = read_config_cache(read_request())
    assert result["data"]["legacy"] == {"exists": True, "ttl_ms": ttl_ms, "rules": []}


@pytest.mark.parametrize("raw", [b"", b"not json", b"null", b"{}", b"[1]", b"\xff"])
def test_snapshot_corrupt_legacy_fails_instead_of_empty_rules(backend, legacy, raw):
    legacy.pipeline.execute.return_value = [len(raw), raw, 60000]
    with pytest.raises(CustomException, match="legacy circuit breaking configuration"):
        read_config_cache(read_request())
    backend.store.snapshot.assert_not_called()


def test_snapshot_oversized_legacy_fails_without_returning_partial_rules(backend, legacy):
    legacy.pipeline.execute.return_value = [rpc.MAX_LEGACY_BYTES + 1, b"[]", 60000]
    with pytest.raises(CustomException, match="exceeds"):
        read_config_cache(read_request())


def test_snapshot_legacy_matcher_construction_failure_is_explicit(backend, legacy):
    raw = json.dumps([{"key": "strategy_id", "method": [], "value": [12345]}]).encode()
    legacy.pipeline.execute.return_value = [len(raw), raw, 60000]
    with pytest.raises(CustomException, match="legacy circuit breaking configuration matcher construction failed"):
        read_config_cache(read_request(module="alert.manager"))
    assert legacy.pipeline.execute.call_count == 1
    backend.store.snapshot.assert_not_called()


def test_legacy_matcher_object_without_conditions_still_blocks_manager_fallback(backend, legacy):
    raw = json.dumps([{"key": "strategy_id", "method": "unsupported", "value": [12345]}]).encode()
    legacy.pipeline.execute.return_value = [len(raw), raw, 60000]
    result = read_config_cache(read_request(module="alert.manager"))
    assert result["data"]["legacy"]["rules"] == json.loads(raw)
    assert result["data"]["legacy_fallback"] is None
    assert legacy.pipeline.execute.call_count == 1


@pytest.mark.parametrize(
    "failure", [ConnectionError("private connection details"), GroupError("too many groups", "capacity_exceeded")]
)
def test_snapshot_storage_and_capacity_failures_are_explicit(backend, legacy, failure):
    backend.store.snapshot.side_effect = failure
    with pytest.raises(CustomException) as error:
        read_config_cache(read_request())
    assert "private connection details" not in str(error.value)
    if isinstance(failure, GroupError):
        assert "capacity_exceeded" in str(error.value)


def test_snapshot_legacy_read_failure_is_explicit(backend, legacy):
    legacy.pipeline.execute.side_effect = ConnectionError("private connection details")
    with pytest.raises(CustomException, match="failed to read circuit breaking storage"):
        read_config_cache(read_request())


def test_legacy_read_with_real_in_memory_redis_retains_ttl_and_original_key(monkeypatch):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(CircuitBreakingCacheManager, "cache", cache)
    key = CircuitBreakingCacheManager.get_cache_key("access.data")
    assert rpc._read_legacy("access.data") == {"exists": False, "ttl_ms": -2, "rules": []}
    cache.set(key, json.dumps(CONDITIONS), px=60000)
    result = rpc._read_legacy("access.data")
    assert result["exists"] is True
    assert 0 < result["ttl_ms"] <= 60000
    assert result["rules"] == CONDITIONS
    cache.set(key, "[]")
    assert rpc._read_legacy("access.data") == {"exists": True, "ttl_ms": -1, "rules": []}


def test_manager_fallback_read_uses_original_builder_key_with_real_in_memory_redis(backend, monkeypatch):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(CircuitBreakingCacheManager, "cache", cache)
    cache.set(CircuitBreakingCacheManager.get_cache_key("alert.builder"), json.dumps(CONDITIONS), px=60000)
    backend.store.snapshot.return_value["groups"] = []
    result = read_config_cache(read_request(module="alert.manager"))
    assert result["exists"] is True
    assert result["data"]["legacy"] == {"exists": False, "ttl_ms": -2, "rules": []}
    fallback = result["data"]["legacy_fallback"]
    assert fallback["module"] == "alert.builder"
    assert fallback["rules"] == CONDITIONS
    assert fallback["adopted"] is True
    assert 0 < fallback["ttl_ms"] <= 60000
    backend.store.snapshot.assert_called_once_with("alert.manager")


@pytest.mark.parametrize(
    "value",
    [b"\xff", "x" * (rpc.MAX_LEGACY_BYTES + 10), "字" * rpc.MAX_LEGACY_BYTES],
    ids=["invalid-utf8", "oversized-ascii", "oversized-unicode"],
)
def test_legacy_real_redis_invalid_encoding_or_oversized_value_fails(monkeypatch, value):
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(CircuitBreakingCacheManager, "cache", cache)
    cache.set(CircuitBreakingCacheManager.get_cache_key("access.data"), value)
    with pytest.raises(CustomException, match="legacy circuit breaking configuration"):
        rpc._read_legacy("access.data")


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"module": "unknown"},
        {"module": None},
        {"module": "access.data", "group_id": None},
        {"module": "access.data", "group_id": "invalid"},
        {"module": "access.data", "redis_key": "arbitrary"},
    ],
)
def test_snapshot_rejects_invalid_or_arbitrary_params_before_storage(backend, params):
    with pytest.raises(CustomException):
        read_config_cache({"cache_type": "circuit_breaking", "params": params})
    backend.CircuitBreakingRuleGroupStore.assert_not_called()


def test_snapshot_rejects_unknown_top_level_fields(backend):
    with pytest.raises(CustomException, match="unsupported circuit breaking parameters"):
        read_config_cache({**read_request(), "url": "arbitrary"})
    backend.CircuitBreakingRuleGroupStore.assert_not_called()
