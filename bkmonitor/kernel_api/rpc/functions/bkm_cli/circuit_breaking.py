"""bkm-cli circuit breaking rule group management and bounded configuration reads."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from redis.exceptions import RedisError

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.management import validate_management_request

COMMON_FIELDS = {"operation", "module", "confirmed", "operator", "bk_tenant_id"}
OPERATION_FIELDS = {
    "create": {"group_id", "conditions", "ttl_seconds", "reason"},
    "update": {"group_id", "expected_revision", "conditions", "reason"},
    "extend": {"group_id", "expected_revision", "extend_seconds"},
    "revoke": {"group_id", "expected_revision"},
}
REQUIRED_FIELDS = {
    "create": {"group_id", "conditions", "ttl_seconds", "reason"},
    "update": {"group_id", "expected_revision"},
    "extend": {"group_id", "expected_revision", "extend_seconds"},
    "revoke": {"group_id", "expected_revision"},
}
MAX_LEGACY_BYTES = 256 * 1024


def _group_backend():
    from alarm_backends.core.circuit_breaking import groups

    return groups


def _validate_module(module: Any) -> str:
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingModule

    if not isinstance(module, str) or not CircuitBreakingModule.is_valid_module(module):
        raise CustomException(message=f"module must be one of {CircuitBreakingModule.get_all_values()}")
    return module


def _validate_group_id(group_id: Any) -> str:
    if isinstance(group_id, str):
        try:
            if str(UUID(group_id)) == group_id:
                return group_id
        except ValueError:
            pass
    raise CustomException(message="group_id must be a canonical UUID")


def _reject_null_fields(params: dict[str, Any]) -> None:
    null_fields = sorted(key for key, value in params.items() if value is None)
    if null_fields:
        raise CustomException(message=f"parameters cannot be null: {null_fields}")


def manage_circuit_breaking(params: dict[str, Any]) -> dict[str, Any]:
    """Manage independently expiring groups in the shared deployment scope."""
    if not isinstance(params, dict):
        raise CustomException(message="params must be an object")
    operation = params.get("operation")
    if not isinstance(operation, str) or operation not in OPERATION_FIELDS:
        raise CustomException(message="operation must be create, update, extend or revoke")
    operator = validate_management_request(
        params,
        allowed_fields=COMMON_FIELDS | OPERATION_FIELDS[operation],
        max_operator_length=32,
    )
    _reject_null_fields(params)
    missing = REQUIRED_FIELDS[operation] - set(params)
    if missing:
        raise CustomException(message=f"missing required parameters: {sorted(missing)}")
    module = _validate_module(params.get("module"))
    group_id = _validate_group_id(params["group_id"])
    if operation == "update" and not ({"conditions", "reason"} & set(params)):
        raise CustomException(message="update requires conditions or reason")

    backend = _group_backend()
    try:
        store = backend.CircuitBreakingRuleGroupStore()
        kwargs = {key: params[key] for key in OPERATION_FIELDS[operation] - {"group_id"} if key in params}
        # Tenant context belongs to the service bridge; circuit breaking keys are shared by deployment.
        group = getattr(store, operation)(module=module, group_id=group_id, operator=operator, **kwargs)
    except backend.CircuitBreakingGroupError as exc:
        raise CustomException(message=f"{exc.code}: {exc}") from exc
    except RedisError as exc:
        raise CustomException(message="circuit breaking storage operation failed; read back before retrying") from exc
    return {"operation": operation, "module": module, "group": group, "requested_operator": operator}


def _read_legacy(module: str) -> dict[str, Any]:
    from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

    key = CircuitBreakingCacheManager.get_cache_key(module)
    # Bound the transferred value even if an older writer stored an oversized configuration.
    try:
        with CircuitBreakingCacheManager.cache.pipeline(transaction=True) as pipeline:
            pipeline.strlen(key)
            pipeline.getrange(key, 0, MAX_LEGACY_BYTES)
            pipeline.pttl(key)
            size, raw, ttl_ms = pipeline.execute()
    except UnicodeError as exc:
        raise CustomException(
            message="legacy circuit breaking configuration cannot be decoded within the read limit"
        ) from exc
    if size > MAX_LEGACY_BYTES:
        raise CustomException(message=f"legacy circuit breaking configuration exceeds {MAX_LEGACY_BYTES} bytes")
    if ttl_ms == -2:
        return {"exists": False, "ttl_ms": -2, "rules": []}
    try:
        rules = json.loads(raw)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise CustomException(message="legacy circuit breaking configuration contains invalid JSON") from exc
    if not isinstance(rules, list) or any(not isinstance(rule, dict) for rule in rules):
        raise CustomException(message="legacy circuit breaking configuration must be a list of rules")
    from alarm_backends.core.circuit_breaking.matcher import gen_circuit_breaking_matcher

    try:
        gen_circuit_breaking_matcher(rules)
    except Exception as exc:
        raise CustomException(message="legacy circuit breaking configuration matcher construction failed") from exc
    return {"exists": True, "ttl_ms": ttl_ms, "rules": rules}


def read_circuit_breaking(params: dict[str, Any]) -> dict[str, Any]:
    """Read legacy rules and active managed groups without suppressing storage errors."""
    unknown = set(params) - {"module", "group_id"}
    if unknown:
        raise CustomException(message=f"unsupported circuit breaking params: {sorted(unknown)}")
    _reject_null_fields(params)
    module = _validate_module(params.get("module"))
    group_id = _validate_group_id(params["group_id"]) if "group_id" in params else None
    backend = _group_backend()
    try:
        legacy = _read_legacy(module)
        legacy_fallback = None
        if module == "alert.manager" and not legacy["rules"]:
            fallback = _read_legacy("alert.builder")
            legacy_fallback = {"module": "alert.builder", **fallback, "adopted": bool(fallback["rules"])}
        snapshot = backend.CircuitBreakingRuleGroupStore().snapshot(module)
        capabilities = backend.capabilities(module)
    except backend.CircuitBreakingGroupError as exc:
        raise CustomException(message=f"{exc.code}: {exc}") from exc
    except RedisError as exc:
        raise CustomException(message="failed to read circuit breaking storage") from exc
    groups = snapshot["groups"]
    if group_id is not None:
        groups = [group for group in groups if group["group_id"] == group_id]
    return {
        "cache_type": "circuit_breaking",
        "params": dict(params),
        "exists": (
            bool(groups)
            if group_id is not None
            else legacy["exists"] or bool(groups) or bool(legacy_fallback and legacy_fallback["exists"])
        ),
        "data": {
            "module": module,
            "legacy": legacy,
            "legacy_fallback": legacy_fallback,
            "groups": groups,
            "server_time_ms": snapshot["server_time_ms"],
            "capabilities": capabilities,
        },
    }


_PARAMS_SCHEMA = {
    "operation": "create | update | extend | revoke",
    "module": "access.data | alert.builder | alert.manager | action",
    "group_id": "canonical UUID, supplied before create",
    "conditions": "create required; update optional; flat key/method/value/condition rule list",
    "ttl_seconds": "create required; positive integer up to 86400",
    "reason": "create required; update optional; nonempty string up to 512 characters",
    "expected_revision": "update/extend/revoke required; positive integer",
    "extend_seconds": "extend required; positive integer up to 86400",
    "confirmed": "must be true after human authorization",
    "operator": "actual authorized operator, up to 32 characters",
}
_DESCRIPTION = (
    "Manage independently expiring circuit breaking rule groups with revision checks. "
    "Uses existing module evaluation contexts in the shared deployment scope. "
    "Read back with read-config-cache cache_type=circuit_breaking and the preassigned group_id."
)
_EXAMPLE = {
    "operation": "create",
    "module": "access.data",
    "group_id": "c40993a1-2a9c-4d7d-8539-c06352e648b7",
    "conditions": [{"key": "strategy_id", "method": "eq", "value": [12345]}],
    "ttl_seconds": 300,
    "reason": "temporary maintenance",
    "operator": "<operator>",
    "confirmed": False,
}

KernelRPCRegistry.register_function(
    func_name="bkm_cli.manage_circuit_breaking",
    handler=manage_circuit_breaking,
    summary="Manage circuit breaking rule groups",
    description=_DESCRIPTION,
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
BkmCliOpRegistry.register(
    op_id="manage-circuit-breaking",
    func_name="bkm_cli.manage_circuit_breaking",
    summary="Manage circuit breaking rule groups",
    description=_DESCRIPTION,
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["circuit_breaking", "admin", "mutation"],
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
