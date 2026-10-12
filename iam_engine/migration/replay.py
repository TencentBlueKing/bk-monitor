"""Replay a reviewed V4 authorization plan without changing V3 entitlements.

This module deliberately does NOT translate arbitrary V3 policy ASTs to RBAC
roles. That mapping is a product decision, not a generic engine inference.
Callers must review the role/resource mapping and supply complete permission
checks. A frozen plan keeps its expiry unchanged across retries and restarts.
"""

from copy import deepcopy
from dataclasses import dataclass


def freeze_grant_plan(entries, *, now, expire_days=365):
    if isinstance(expire_days, bool) or not isinstance(expire_days, int) or not 1 <= expire_days <= 365:
        raise ValueError("expire_days must be between 1 and 365")
    plan = deepcopy(list(entries))
    for entry in plan:
        if not isinstance(entry, dict) or not entry.get("mapping_reference"):
            raise ValueError("Each grant requires an explicitly reviewed mapping_reference")
        authorization = entry.get("authorization", {})
        if not authorization.get("role_id") or not authorization.get("related_resource_type_id"):
            raise ValueError("An explicit role and resource branch are required")
        subject = authorization.get("subject", {})
        if subject.get("type") != "user" or not subject.get("id"):
            raise ValueError("This migration plan requires an explicit user subject")
        resources = authorization.get("resources")
        if not resources or not all(
            isinstance(r, dict) and r.get("type") and r.get("id") is not None and str(r.get("id", ""))
            for r in resources
        ):
            raise ValueError("An explicit, non-empty resource scope is required")
        checks = entry.get("checks")
        if not checks or not all(isinstance(check, dict) and check.get("action_id") for check in checks):
            raise ValueError("Permission read-back checks are required")
        expiry = authorization.setdefault("expired_at", now + expire_days * 86400)
        if isinstance(expiry, bool) or not isinstance(expiry, int) or not now < expiry <= now + 365 * 86400:
            raise ValueError("The frozen expiry must be future and within 365 days")
    return plan


@dataclass(frozen=True)
class ReplayResult:
    index: int
    status: str


def replay_grant_plan(plan, *, source_allowed, target_allowed, grant, apply=False):
    """Preview by default. Repeat runs skip permissions already confirmed in V4.

    These callbacks are explicit V3/V4 calls, never union or bypass-enabled
    Permission checks. Exceptions / non-boolean responses fail closed.
    Read-back proves only the checked permission set, not grant-row TTL identity.
    """
    results = []
    # Preflight all source checks before the first write, avoiding a partial
    # migration caused by a known denied source permission later in the plan.
    for entry in plan:
        if not entry.get("mapping_reference") or not entry.get("checks"):
            raise ValueError("A reviewed mapping and complete checks are required")
        if any(source_allowed(entry, check) is not True for check in entry["checks"]):
            raise ValueError("V3 source authorization is missing or unavailable")
    for index, entry in enumerate(plan):
        if _target_confirmed(entry, target_allowed):
            results.append(ReplayResult(index, "already_allowed"))
        elif not apply:
            results.append(ReplayResult(index, "would_grant"))
        else:
            grant(deepcopy(entry["authorization"]))
            if not _target_confirmed(entry, target_allowed):
                raise RuntimeError(f"V4 permission read-back failed for plan entry {index}")
            results.append(ReplayResult(index, "granted"))
    return tuple(results)


def _target_confirmed(entry, target_allowed):
    results = [target_allowed(entry, check) for check in entry["checks"]]
    if any(type(result) is not bool for result in results):
        raise ValueError("V4 returned an incomplete authorization decision")
    return all(results)
