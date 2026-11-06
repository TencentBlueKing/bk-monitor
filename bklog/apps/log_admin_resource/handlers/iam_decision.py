"""Resource Call handlers for bounded IAM permission decisions."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.api import TransferApi
from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.iam.exceptions import ActionNotExistError, ResourceNotExistError
from apps.iam.handlers.actions import ActionEnum, ActionMeta, get_action_by_id
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum, ResourceMeta, get_resource_by_id
from apps.log_admin_resource.handlers.inspection import (
    reject_identity_params,
    require_biz_in_request_tenant,
    require_request_tenant_id,
    scope_biz_queryset,
    scope_space_queryset,
)
from apps.log_admin_resource.response_schema import object_schema
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Space
from bkm_space.utils import space_uid_to_bk_biz_id


FUNC_NAME = "bklog.iam.decision.evaluate"
MAX_DECISIONS = 20

# Canonical Resource Call aliases map onto IAM ResourceMeta.id values.
RESOURCE_TYPE_ALIASES = {
    "business": ResourceEnum.BUSINESS.id,
    "space": ResourceEnum.BUSINESS.id,
    "indices": ResourceEnum.INDICES.id,
    "index_set": ResourceEnum.INDICES.id,
    "collection": ResourceEnum.COLLECTION.id,
    "es_source": ResourceEnum.ES_SOURCE.id,
}

SUPPORTED_ACTIONS = {action.id: action for action in ActionEnum.__dict__.values() if isinstance(action, ActionMeta)}


DECISION_ITEM_SCHEMA = object_schema(
    "action_id",
    "resource_type",
    "resource_id",
    "allowed",
    "status",
    "mode",
    "warnings",
    properties={
        "action_id": {"type": "string", "minLength": 1},
        "resource_type": {"type": "string"},
        "resource_id": {"type": "string"},
        "allowed": {"type": ["boolean", "null"]},
        "status": {"type": "string", "enum": ["ok", "unknown", "error"]},
        "mode": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    additional_properties=False,
)

RESPONSE_SCHEMA = object_schema(
    "username",
    "bk_tenant_id",
    "decisions",
    "decision_count",
    properties={
        "username": {"type": "string", "minLength": 1},
        "bk_tenant_id": {"type": "string", "minLength": 1},
        "decisions": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_DECISIONS,
            "items": DECISION_ITEM_SCHEMA,
        },
        "decision_count": {"type": "integer", "minimum": 1, "maximum": MAX_DECISIONS},
    },
    additional_properties=False,
)


def evaluate_iam_decisions(params: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a bounded batch of read-only IAM predicates for one username."""

    reject_identity_params(params)
    request_tenant_id = require_request_tenant_id()
    username = str(params.get("username") or "").strip()
    if not username:
        raise ValidationError("username is required")

    raw_decisions = params.get("decisions") or []
    if not isinstance(raw_decisions, list) or not raw_decisions:
        raise ValidationError("decisions must be a non-empty list")
    if len(raw_decisions) > MAX_DECISIONS:
        raise ValidationError(f"decisions may contain at most {MAX_DECISIONS} items")

    permission = Permission(username=username, bk_tenant_id=request_tenant_id)
    if permission.bk_tenant_id != request_tenant_id:
        raise BklogPermissionError("IAM decision tenant does not match the current Resource Call tenant")

    results = []
    for index, item in enumerate(raw_decisions):
        if not isinstance(item, dict):
            raise ValidationError(f"decisions[{index}] must be an object")
        results.append(_evaluate_one(permission, item, index=index))

    return {
        "username": username,
        "bk_tenant_id": request_tenant_id,
        "decisions": results,
        "decision_count": len(results),
    }


def _evaluate_one(permission: Permission, item: dict[str, Any], *, index: int) -> dict[str, Any]:
    action_id = str(item.get("action_id") or "").strip()
    resource_type = str(item.get("resource_type") or "").strip()
    resource_id = str(item.get("resource_id") or "").strip()
    if not action_id:
        raise ValidationError(f"decisions[{index}] requires action_id")

    action = _resolve_action(action_id)
    related_types = {item.id for item in (action.related_resource_types or [])}
    if not related_types:
        if resource_type or resource_id:
            raise ValidationError(f"decisions[{index}] action {action.id} does not accept a resource")
        resources = []
        resource_meta_id = ""
        resource_instance_id = ""
    else:
        if not resource_type or not resource_id:
            raise ValidationError(f"decisions[{index}] requires resource_type and resource_id")
        resource_meta = _resolve_resource_meta(resource_type)
        _assert_action_accepts_resource(action, resource_meta, index=index)
        resources = [_build_resource(resource_meta, resource_id)]
        resource_meta_id = resource_meta.id
        resource_instance_id = str(resources[0].id)

    warnings: list[str] = []
    if permission.is_demo_biz_resource(resources) and (settings.DEMO_BIZ_EDIT_ENABLED or action.is_read_action()):
        warnings.append("demo_biz_exemption")
        return {
            "action_id": action.id,
            "resource_type": resource_meta_id,
            "resource_id": resource_instance_id,
            "allowed": True,
            "status": "ok",
            "mode": "",
            "warnings": warnings,
        }

    request = permission.make_engine_request(action, resources)
    try:
        decision = permission.mode_router.is_allowed(request)
    except Exception as error:  # pylint: disable=broad-except
        return {
            "action_id": action.id,
            "resource_type": resource_meta_id,
            "resource_id": resource_instance_id,
            "allowed": None,
            "status": "unknown",
            "mode": "",
            "warnings": [f"iam_dependency_error:{error.__class__.__name__}"],
        }

    permission._record_decision(action.id, decision, permission._resource_type_label(request.resources))

    if decision.degraded and not decision.allowed:
        # Dependency/provider failure must not look like an authorization denial.
        warnings.append("iam_provider_degraded")
        return {
            "action_id": action.id,
            "resource_type": resource_meta_id,
            "resource_id": resource_instance_id,
            "allowed": None,
            "status": "unknown",
            "mode": str(decision.mode or ""),
            "warnings": warnings,
        }

    if decision.degraded:
        warnings.append("iam_provider_degraded")

    return {
        "action_id": action.id,
        "resource_type": resource_meta_id,
        "resource_id": resource_instance_id,
        "allowed": bool(decision.allowed),
        "status": "ok",
        "mode": str(decision.mode or ""),
        "warnings": warnings,
    }


def _resolve_action(action_id: str) -> ActionMeta:
    if action_id not in SUPPORTED_ACTIONS:
        raise ValidationError(f"unknown action_id: {action_id}")
    try:
        return get_action_by_id(action_id)
    except ActionNotExistError as error:
        raise ValidationError(f"unknown action_id: {action_id}") from error


def _resolve_resource_meta(resource_type: str) -> type[ResourceMeta]:
    canonical = RESOURCE_TYPE_ALIASES.get(resource_type, resource_type)
    try:
        return get_resource_by_id(canonical)
    except ResourceNotExistError as error:
        raise ValidationError(f"unsupported resource_type: {resource_type}") from error


def _assert_action_accepts_resource(action: ActionMeta, resource_meta: type[ResourceMeta], *, index: int) -> None:
    allowed_types = {item.id for item in (action.related_resource_types or [])}
    if resource_meta.id not in allowed_types:
        raise ValidationError(
            f"decisions[{index}] resource_type {resource_meta.id} is incompatible with action {action.id}"
        )


def _build_resource(resource_meta: type[ResourceMeta], resource_id: str):
    if resource_meta is ResourceEnum.BUSINESS:
        bk_biz_id = require_biz_in_request_tenant(resource_id)
        if settings.ENABLE_MULTI_TENANT_MODE and not Space.origin_objects.filter(bk_biz_id=bk_biz_id).exists():
            raise ValidationError("resource_not_found")
        return resource_meta.create_simple_instance(str(bk_biz_id))

    if resource_meta is ResourceEnum.INDICES:
        if not str(resource_id).isdigit():
            raise ValidationError("resource_not_found")
        index_set_id = int(resource_id)
        index_set = scope_space_queryset(LogIndexSet.objects).filter(index_set_id=index_set_id).first()
        if index_set is None:
            raise ValidationError("resource_not_found")
        # Keep an explicit tenant gate even when Space queryset scoping is disabled.
        require_biz_in_request_tenant(space_uid_to_bk_biz_id(index_set.space_uid))
        return resource_meta.create_simple_instance(str(index_set.index_set_id))

    if resource_meta is ResourceEnum.COLLECTION:
        if not str(resource_id).isdigit():
            raise ValidationError("resource_not_found")
        collector = scope_biz_queryset(CollectorConfig.objects).filter(collector_config_id=int(resource_id)).first()
        if collector is None:
            raise ValidationError("resource_not_found")
        return resource_meta.create_simple_instance(str(collector.collector_config_id))

    if resource_meta is ResourceEnum.ES_SOURCE:
        if not str(resource_id).isdigit():
            raise ValidationError("resource_not_found")
        cluster_id = int(resource_id)
        try:
            clusters = TransferApi.get_cluster_info({"cluster_id": cluster_id})
        except Exception as error:  # pylint: disable=broad-except
            raise ValidationError("resource_not_found") from error
        cluster = clusters[0] if isinstance(clusters, list) and clusters else None
        if not isinstance(cluster, dict):
            raise ValidationError("resource_not_found")
        cluster_config = cluster.get("cluster_config") or {}
        custom_option = cluster_config.get("custom_option") or {}
        require_biz_in_request_tenant(custom_option.get("bk_biz_id", 0), allow_global=True)
        return resource_meta.create_simple_instance(str(cluster_id))

    raise ValidationError(f"unsupported resource_type: {resource_meta.id}")


FUNCTIONS = {
    FUNC_NAME: {
        "func_name": FUNC_NAME,
        "description": (
            "Evaluate bounded IAM allow/deny decisions for any username and any published IAM action "
            "in the current tenant."
        ),
        "notes": (
            "This OP only inspects Permission.is_allowed; it does not grant or mutate IAM policy. "
            "All ActionEnum ids are accepted. Actions without related resources omit resource_type "
            "and resource_id. Resource Call request tenant is authoritative; caller-supplied "
            "bk_tenant_id is rejected. Dependency failures return status=unknown instead of a false denial."
        ),
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "minLength": 1, "maxLength": 128},
                "decisions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_DECISIONS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action_id": {
                                "type": "string",
                                "enum": sorted(SUPPORTED_ACTIONS),
                            },
                            "resource_type": {
                                "type": "string",
                                "enum": sorted(RESOURCE_TYPE_ALIASES),
                            },
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 128},
                        },
                        "required": ["action_id"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["username", "decisions"],
            "additionalProperties": False,
        },
        "response_schema": RESPONSE_SCHEMA,
        "examples": [
            {
                "params": {
                    "username": "alice",
                    "decisions": [
                        {
                            "action_id": "view_business_v2",
                            "resource_type": "business",
                            "resource_id": "2",
                        },
                        {
                            "action_id": "search_log_v2",
                            "resource_type": "indices",
                            "resource_id": "1001",
                        },
                        {
                            "action_id": "manage_collection_v2",
                            "resource_type": "collection",
                            "resource_id": "123",
                        },
                        {
                            "action_id": "manage_global_desensitize_rule",
                        },
                    ],
                }
            }
        ],
        "error_codes": [
            "username is required",
            "resource_not_found",
            "unknown action_id",
            "unsupported resource_type",
        ],
    }
}


HANDLERS = {FUNC_NAME: evaluate_iam_decisions}
