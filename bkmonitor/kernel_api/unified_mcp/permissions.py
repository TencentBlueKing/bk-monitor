"""Opt-in native permissions for the existing MCP catalog; no second router.

Native permissions first, legacy MCP action second on explicit denial only.
Identity, resource, configuration and IAM errors never become fallback grants.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from iam import IAM, Action, Request, Resource, Subject
from iam.apply.models import ActionWithResources, Application, RelatedResourceType, ResourceInstance, ResourceNode
from jsonschema import Draft7Validator
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from kernel_api.unified_mcp.registry import ToolDefinition

logger = logging.getLogger(__name__)
INTERNAL_FIELDS = {
    "bk_username",
    "bk_tenant_id",
    "bk_app_code",
    "bk_app_secret",
    "skip_check",
    "token",
    "original_search",
    "enforce_permission",
}


class AuthorizationUnavailable(APIException):
    status_code = 503
    default_detail = "Permission service is unavailable. The request was not authorized."


def log_mcp_event(event, request=None, *, level=logging.INFO, **fields):
    """Shared English MCP-auth log format; callers supply metadata, never payloads."""
    from bkmonitor.utils.request import get_mcp_trace_id, get_request

    request = request or get_request(peaceful=True)
    user = getattr(request, "user", None)
    path = getattr(request, "path", "").split("?", 1)[0]
    fields = {
        "trace_id": get_mcp_trace_id(request),
        "username": getattr(user, "username", ""),
        "tenant_id": getattr(user, "tenant_id", ""),
        "method": getattr(request, "method", ""),
        "path": path,
        **fields,
    }
    fields = {
        key: value if value is None or isinstance(value, bool | int) else str(value)[:256]
        for key, value in fields.items()
    }
    # ASCII JSON prevents multiline injection; never pass headers, tool_args, secrets or exception text.
    logger.log(level, "MCP_AUTH: event=%s %s", event, json.dumps(fields, ensure_ascii=True, sort_keys=True))


def _audit(
    tool,
    request,
    phase,
    decision,
    *,
    bk_biz_id=None,
    system_id="",
    action_id="",
    source="none",
    error_type="",
    resource=None,
):
    fields = {
        "tool": tool.name,
        "backend_method": tool.backend_method,
        "backend_path": tool.backend_path,
        "phase": phase,
        "decision": decision,
        "bk_biz_id": str(bk_biz_id)[:32] if bk_biz_id is not None else "",
        "system_id": system_id,
        "action_id": action_id,
        "authorization_source": source,
        "error_type": error_type,
        "resource_system": getattr(resource, "system", ""),
        "resource_type": getattr(resource, "type", ""),
        "resource_id": str(getattr(resource, "id", ""))[:128],
    }
    level = logging.WARNING if decision in {"error", "aborted"} else logging.INFO
    log_mcp_event("permission_check", request, level=level, **fields)


def _iam_allowed(client, query):
    try:
        allowed = client.is_allowed(query)
    except Exception as exc:
        raise AuthorizationUnavailable() from exc
    if not isinstance(allowed, bool):
        raise AuthorizationUnavailable("IAM did not return a boolean decision.")
    return allowed


def _checked_permission(tool, request, phase, client, query, bk_biz_id):
    fields = {
        "bk_biz_id": bk_biz_id,
        "system_id": query.system,
        "action_id": query.action.id,
        "resource": query.resources[0] if query.resources else None,
    }
    if request is not None:
        request.mcp_permission_action = query.action.id
    _audit(tool, request, phase, "checking", **fields)
    try:
        allowed = _iam_allowed(client, query)
    except AuthorizationUnavailable as exc:
        _audit(tool, request, phase, "error", error_type=type(exc.__cause__ or exc).__name__, **fields)
        raise
    _audit(tool, request, phase, "allowed" if allowed else "denied", **fields)
    return allowed


def _business_resource(bk_biz_id):
    from bkmonitor.iam import ResourceEnum

    resource = ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)
    if resource.system != settings.BK_IAM_SYSTEM_ID or resource.type != "space" or str(resource.id) != str(bk_biz_id):
        raise AuthorizationUnavailable("The resolved business resource does not match the request.")
    return resource


def _validate_alert_target(spec, bk_biz_id, context):
    target_arg = spec.get("target_arg")
    if not target_arg or target_arg not in context:
        return  # Business-level introspection need not supply an alert/strategy ID.
    from kernel_api.resource.alert import ensure_alert_belongs_to_biz, ensure_strategy_ids_belong_to_biz

    if spec["target_kind"] == "strategy":
        target_id = serializers.IntegerField(min_value=1).run_validation(context[target_arg])
        ensure_strategy_ids_belong_to_biz(bk_biz_id, [target_id])
    else:
        target_id = serializers.CharField(allow_blank=False).run_validation(context[target_arg])
        ensure_alert_belongs_to_biz(bk_biz_id, target_id)


def _principal(request, bk_biz_id=None):
    user = getattr(request, "user", None)
    jwt = getattr(request, "jwt", None)
    claims = getattr(jwt, "user", {})
    if (
        not getattr(user, "is_authenticated", False)
        or not getattr(jwt, "is_valid", False)
        or claims.get("verified") is not True
        or claims.get("username") != getattr(user, "username", None)
        or not isinstance(getattr(user, "username", None), str)
        or not user.username
        or not isinstance(getattr(user, "tenant_id", None), str)
        or not user.tenant_id
    ):
        raise PermissionDenied("Native MCP requires a verified gateway user and tenant.")
    if getattr(settings, "ENABLE_MULTI_TENANT_MODE", False):
        if request.META.get("HTTP_X_BK_TENANT_ID") != user.tenant_id:
            raise PermissionDenied("MCP tenant does not match the authenticated user.")
    if bk_biz_id is not None:
        from bkmonitor.utils.tenant import is_biz_in_tenant
        from bkm_space.utils import bk_biz_id_to_space_uid

        if not is_biz_in_tenant(bk_biz_id, user.tenant_id):
            raise PermissionDenied("MCP business does not belong to the authenticated tenant.")
        if not bk_biz_id_to_space_uid(bk_biz_id):
            raise PermissionDenied("MCP business has no resolvable query space.")
    return user


def _monitor_permission(user):
    from bkmonitor.iam import Permission

    client = Permission(user.username, bk_tenant_id=user.tenant_id)
    client.skip_check = False
    return client


def _log_iam(user):
    profile = getattr(settings, "MCP_LOG_IAM_PROFILE", {})
    if not isinstance(profile, dict) or profile.get("mode") != "v3-current":
        raise ImproperlyConfigured(
            "Native log MCP requires MCP_LOG_IAM_PROFILE mode=v3-current; V4/union/legacy action models are not supported yet"
        )
    url = profile.get("gateway_url", "")
    parsed = urlsplit(url) if isinstance(url, str) else None
    if (
        not parsed
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured("MCP_LOG_IAM_PROFILE.gateway_url must be an explicit IAM gateway URL")
    if settings.ROLE in {"api", "worker"}:
        app_code, secret = settings.SAAS_APP_CODE, settings.SAAS_SECRET_KEY
    else:
        app_code, secret = settings.APP_CODE, settings.SECRET_KEY
    return IAM(app_code, secret, url, bk_tenant_id=user.tenant_id)


def log_index_sets(user, bk_biz_id):
    from api.log_search.default import SearchIndexSetResource

    # Do not use the pooled API shortcut: it retains per-instance user/tenant state.
    try:
        result = SearchIndexSetResource().request.cacheless(
            bk_biz_id=bk_biz_id,
            bk_username=user.username,
            bk_tenant_id=user.tenant_id,
        )
    except Exception as exc:
        log_mcp_event(
            "log_catalog_unavailable",
            level=logging.WARNING,
            error_type=type(exc).__name__,
            username=user.username,
            tenant_id=user.tenant_id,
            bk_biz_id=bk_biz_id,
        )
        raise AuthorizationUnavailable("Log resource metadata is unavailable.") from exc
    if not isinstance(result, list):
        raise AuthorizationUnavailable("The log index catalog did not return a resource list.")
    return result


def call_log_api(name, **params):
    """Keep legacy calls intact; native execution uses request-local API identity."""
    from core.drf_resource import api
    from bkmonitor.utils.request import get_request

    client = getattr(api.log_search, name)
    request = get_request(peaceful=True)
    if not getattr(request, "native_mcp_tool", None):
        return client(**params)
    client = type(client)()
    call = getattr(client.request, "cacheless", client.request)
    return call(**params, bk_username=request.user.username, bk_tenant_id=request.user.tenant_id)


def _log_resource(spec, user, bk_biz_id, context):
    if spec["resource_type"] == "space":
        # Log IAM V3 references the monitoring space resource, not a log-local space.
        return Resource("bk_monitorv3", "space", str(bk_biz_id), {"name": str(bk_biz_id)})
    if context.get("target_type", "index_set") != "index_set":
        raise ValidationError("Native log MCP currently supports fixed index sets only.")
    index_set_id = serializers.IntegerField(min_value=1).run_validation(context.get("index_set_id"))
    catalog = log_index_sets(user, bk_biz_id)
    matches = [
        item for item in catalog if isinstance(item, dict) and str(item.get("index_set_id")) == str(index_set_id)
    ]
    if len(matches) != 1:
        raise PermissionDenied("The log index set is not uniquely visible in the requested space.")
    item = matches[0]
    # ponytail: ordinary same-space indices only; platform/related-space rules need an explicit follow-up.
    if (
        item.get("is_platform_index") is not False
        or item.get("is_group") is not False
        or item.get("platform_index_owner_space_uid")
    ):
        raise ValidationError(
            "Native log MCP does not yet support platform or grouped index sets, or incomplete catalog metadata."
        )
    if str(item.get("bk_biz_id")) != str(bk_biz_id):
        raise PermissionDenied("The log index set does not belong to the requested business.")
    from bkm_space.utils import bk_biz_id_to_space_uid

    expected_space = bk_biz_id_to_space_uid(bk_biz_id)
    if not expected_space or item.get("space_uid") != expected_space:
        raise PermissionDenied("The log index set space does not match the requested business.")
    return Resource(
        "bk_log_search",
        "indices",
        str(index_set_id),
        {
            "name": item.get("index_set_name") or str(index_set_id),
            "bk_biz_id": str(bk_biz_id),
            "_bk_iam_path_": f"/space,{bk_biz_id}/",
        },
    )


def _apply_guide(client, spec, resource, request):
    application = Application(
        spec["system_id"],
        [
            ActionWithResources(
                spec["action_id"],
                [
                    RelatedResourceType(
                        resource.system,
                        resource.type,
                        [
                            ResourceInstance(
                                [
                                    ResourceNode(
                                        resource.type, resource.id, resource.attribute.get("name", resource.id)
                                    ),
                                ]
                            )
                        ],
                    ),
                ],
            )
        ],
    )
    result = {"permission": application.to_dict()}
    error_type = "InvalidResponse"
    try:
        ok, _, url = client.get_apply_url(application)
        if ok and isinstance(url, str) and url:
            result["apply_url"] = url
            return result
    except Exception as exc:
        error_type = type(exc).__name__
    # A failed application link must never turn denial into permission or leak IAM response details.
    log_mcp_event(
        "apply_guide_unavailable",
        request,
        level=logging.WARNING,
        error_type=error_type,
        system_id=spec["system_id"],
        action_id=spec["action_id"],
    )
    return result


def permission_state(tool: ToolDefinition, request, bk_biz_id=None, resource_context=None, include_apply_guide=False):
    """Probe and execution share native-first decisions, including the fallback result."""
    try:
        _audit(tool, request, "scope", "started", bk_biz_id=bk_biz_id)
        return _permission_state(tool, request, bk_biz_id, resource_context, include_apply_guide)
    except Exception as exc:
        _audit(tool, request, "authorization", "aborted", bk_biz_id=bk_biz_id, error_type=type(exc).__name__)
        raise


def _permission_state(tool, request, bk_biz_id, context, include_apply_guide):
    spec = tool.native_permission
    if not spec:
        raise ImproperlyConfigured("Tool is not enabled for native-first permissions")
    if bk_biz_id is not None:
        bk_biz_id = serializers.IntegerField().run_validation(bk_biz_id)
        if not bk_biz_id or (tool.category == "alert" and bk_biz_id == -1):
            raise ValidationError(
                {"bk_biz_id": "A concrete business is required; all-business sentinels are not allowed."}
            )
    user = _principal(request, bk_biz_id)
    context = context or {}
    result = {
        **tool.permission_payload(),
        "tool_name": tool.name,
        "resource": {},
        "native_authorized": None,
        "legacy_authorized": None,
        "authorization_source": "none",
    }
    if bk_biz_id is not None:
        result["resource"]["bk_biz_id"] = str(bk_biz_id)
    monitor = None
    if spec["system_id"] == "bk_monitorv3":
        if bk_biz_id is None:
            _audit(tool, request, "final", "requires_resource")
            return {**result, "state": "requires_resource", "authorized": False}
        if tool.category == "alert":
            _validate_alert_target(spec, bk_biz_id, context)
            if spec.get("target_arg") in context:
                result["target"] = {"type": spec["target_kind"], "id": str(context[spec["target_arg"]])}
        monitor = _monitor_permission(user)
        native_resource = _business_resource(bk_biz_id)
        native_client = monitor.iam_client
        native_query = monitor.make_request(spec["action_id"], [native_resource])
    else:
        native_client = _log_iam(user)
        if bk_biz_id is None or (spec["resource_type"] == "indices" and "index_set_id" not in context):
            _audit(tool, request, "final", "requires_resource", bk_biz_id=bk_biz_id)
            return {**result, "state": "requires_resource", "authorized": False}
        # Scope validation is BEFORE either permission decision; its failures never trigger fallback.
        native_resource = _log_resource(spec, user, bk_biz_id, context)
        if native_resource.type == "indices":
            result["resource"]["index_set_id"] = native_resource.id
        native_query = Request(
            spec["system_id"], Subject("user", user.username), Action(spec["action_id"]), [native_resource], None
        )

    _audit(
        tool,
        request,
        "scope",
        "resolved",
        bk_biz_id=bk_biz_id,
        system_id=native_query.system,
        action_id=native_query.action.id,
        resource=native_resource,
    )
    native_allowed = _checked_permission(tool, request, "native", native_client, native_query, bk_biz_id)
    result["native_authorized"] = native_allowed
    if native_allowed:
        _audit(
            tool,
            request,
            "final",
            "allowed",
            bk_biz_id=bk_biz_id,
            source="native",
            system_id=native_query.system,
            action_id=spec["action_id"],
            resource=native_resource,
        )
        return {
            **result,
            "state": "granted",
            "authorized": True,
            "authorization_source": "native",
            "matched_action_id": spec["action_id"],
        }

    # A real False is the ONLY fallback trigger. Do not catch resource or IAM errors as denial.
    monitor = monitor or _monitor_permission(user)
    legacy_resource = _business_resource(bk_biz_id)
    legacy_query = monitor.make_request(tool.iam_action, [legacy_resource])
    legacy_allowed = _checked_permission(tool, request, "legacy", monitor.iam_client, legacy_query, bk_biz_id)
    result["legacy_authorized"] = legacy_allowed
    result["legacy_permission"] = {
        "system_id": legacy_query.system,
        "action_id": tool.iam_action,
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    source = "legacy" if legacy_allowed else "none"
    _audit(
        tool,
        request,
        "final",
        "allowed" if legacy_allowed else "denied",
        bk_biz_id=bk_biz_id,
        source=source,
        system_id=legacy_query.system,
        action_id=tool.iam_action,
        resource=legacy_resource,
    )
    if not legacy_allowed and include_apply_guide:
        result.update(_apply_guide(native_client, spec, native_resource, request))
        result["legacy_permission"].update(
            _apply_guide(
                monitor.iam_client,
                {"system_id": legacy_query.system, "action_id": tool.iam_action},
                legacy_resource,
                request,
            )
        )
    return {
        **result,
        "state": "granted" if legacy_allowed else "missing",
        "authorized": legacy_allowed,
        "authorization_source": source,
        "matched_action_id": tool.iam_action if legacy_allowed else "",
    }


def execute_native_tool(tool: ToolDefinition, tool_args: dict, request):
    """Both standalone middleware and unified execute_tool use this exact entry."""
    if request is not None:
        request.mcp_permission_source = "none"
        request.mcp_permission_action = ""
    try:
        _audit(tool, request, "route", "resolved")
        _audit(tool, request, "validation", "started")
        return _execute_native_tool(tool, tool_args, request)
    except Exception as exc:
        _audit(
            tool,
            request,
            "execution",
            "aborted",
            bk_biz_id=getattr(request, "biz_id", None),
            source=getattr(request, "mcp_permission_source", "none"),
            action_id=getattr(request, "mcp_permission_action", ""),
            error_type=type(exc).__name__,
        )
        raise


def _execute_native_tool(tool, tool_args, request):
    if not tool.native_permission:
        raise ImproperlyConfigured("Tool is not enabled for native permissions")
    _principal(request)
    if request.method not in {"GET", "POST"}:
        raise ValidationError("Native MCP accepts GET or POST only.")
    if "HTTP_X_ASYNC_TASK" in request.META:
        raise ValidationError("Native MCP does not support the asynchronous task header.")
    if request.method == "POST" and (request.GET or request.content_type != "application/json"):
        raise ValidationError("Native MCP POST accepts JSON body arguments only.")
    if request.method == "GET" and request.body:
        raise ValidationError("Native MCP GET does not accept body arguments.")
    if not isinstance(tool_args, dict):
        raise ValidationError("tool_args must be an object.")
    args = dict(tool_args)
    if INTERNAL_FIELDS.intersection(args):
        raise ValidationError("MCP identity and permission fields are server-owned.")
    if "bk_biz_id" in args and not isinstance(args["bk_biz_id"], bool):
        args["bk_biz_id"] = str(args["bk_biz_id"])
    # The legacy standalone alert schema requires this field. Accept only the same
    # single business, then let the shared dispatcher derive it again.
    if "bk_biz_ids" in tool.backend_derived_fields and "bk_biz_ids" in args:
        values = args.pop("bk_biz_ids")
        if not isinstance(values, list) or len(values) != 1 or str(values[0]) != args.get("bk_biz_id"):
            raise ValidationError("bk_biz_ids must contain exactly the requested bk_biz_id.")
    # URL query parameters arrive as strings, unlike JSON tool_args.
    if request.method == "GET":
        for name, schema in tool.input_schema.get("properties", {}).items():
            field = {"integer": serializers.IntegerField, "boolean": serializers.BooleanField}.get(schema.get("type"))
            if name in args and field:
                args[name] = field().run_validation(args[name])
    errors = list(Draft7Validator(tool.input_schema).iter_errors(args))
    if errors:
        raise ValidationError({"tool_args": errors[0].message})
    if args.get("target_type", "index_set") != "index_set" or args.get("is_platform"):
        raise ValidationError("This native MCP version supports fixed, non-platform resources only.")
    _audit(tool, request, "validation", "passed", bk_biz_id=args.get("bk_biz_id"))
    state = permission_state(tool, request, args.get("bk_biz_id"), args, include_apply_guide=True)
    request.mcp_permission_source = state["authorization_source"]
    request.mcp_permission_action = (
        tool.iam_action if state["legacy_authorized"] is not None else tool.native_permission["action_id"]
    )
    if state["state"] != "granted":
        raise PermissionDenied(state)
    request.biz_id = int(args["bk_biz_id"])
    request.skip_check = False
    from kernel_api.unified_mcp.dispatcher import dispatch_tool

    # Identity propagation only, never an authorization bypass or a reusable grant.
    previous = getattr(request, "native_mcp_tool", None)
    request.native_mcp_tool = tool.name
    try:
        # The dispatcher keeps its existing table/space guards and Resource pipeline.
        _audit(
            tool,
            request,
            "execution",
            "started",
            bk_biz_id=request.biz_id,
            source=request.mcp_permission_source,
            action_id=request.mcp_permission_action,
        )
        data = dispatch_tool(tool.name, args)
        _audit(
            tool,
            request,
            "execution",
            "succeeded",
            bk_biz_id=request.biz_id,
            source=request.mcp_permission_source,
            action_id=request.mcp_permission_action,
        )
        return data
    finally:
        request.native_mcp_tool = previous
