"""Unified MCP 可选的原生权限实现，不新增第二套路由。

先检查原生权限，只有原生明确拒绝才检查旧 MCP Action；身份、资源、配置和 IAM 异常
都必须失败关闭，不能转换成旧权限放行。
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


class MCPPermissionDenied(PermissionDenied):
    """保留权限状态中的 bool/null 类型，同时兼容 DRF 异常 introspection。"""

    def __init__(self, state):
        super().__init__(state)
        self.detail = state

    def get_codes(self):
        return PermissionDenied(self.detail).get_codes()

    def get_full_details(self):
        return PermissionDenied(self.detail).get_full_details()


def _log_mcp_event(prefix, event, request=None, *, level=logging.INFO, **fields):
    """写入有长度上限的单行 MCP 元信息；调用方禁止传业务正文。"""
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
    # ASCII 单行 JSON 防止日志换行注入；禁止传 Header、tool_args、凭证和异常正文。
    logger.log(level, "%s: event=%s %s", prefix, event, json.dumps(fields, ensure_ascii=True, sort_keys=True))


def log_mcp_event(event, request=None, *, level=logging.INFO, **fields):
    """记录身份和权限判定使用的统一 MCP_AUTH 日志。"""
    _log_mcp_event("MCP_AUTH", event, request, level=level, **fields)


def log_mcp_tool_event(event, request=None, *, level=logging.INFO, **fields):
    """记录 Tool Search 和 Unified 执行链路使用的统一 MCP_TOOL 日志。"""
    _log_mcp_event("MCP_TOOL", event, request, level=level, **fields)


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
    """按统一字段记录权限阶段、判定、资源和授权来源。"""
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
    """调用 IAM 并要求返回严格布尔值，异常不能伪装成无权限。"""
    try:
        allowed = client.is_allowed(query)
    except Exception as exc:
        raise AuthorizationUnavailable() from exc
    if not isinstance(allowed, bool):
        raise AuthorizationUnavailable("IAM did not return a boolean decision.")
    return allowed


def _checked_permission(tool, request, phase, client, query, bk_biz_id):
    """记录权限检查前后事件，并返回严格布尔判定。"""
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
    """构造并反校验监控业务空间资源，防止资源系统或 ID 漂移。"""
    from bkmonitor.iam import ResourceEnum

    resource = ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)
    if resource.system != settings.BK_IAM_SYSTEM_ID or resource.type != "space" or str(resource.id) != str(bk_biz_id):
        raise AuthorizationUnavailable("The resolved business resource does not match the request.")
    return resource


def _validate_alert_target(spec, bk_biz_id, context):
    """有目标 ID 时确认告警／策略属于请求业务；无 ID 的列表探测可跳过。"""
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
    """验证网关用户、JWT、租户及业务空间属于同一身份边界。"""
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
    """创建显式关闭 skip_check 的监控权限客户端。"""
    from bkmonitor.iam import Permission

    client = Permission(user.username, bk_tenant_id=user.tenant_id)
    client.skip_check = False
    return client


def _log_iam(user):
    """使用监控应用凭证创建查询日志系统策略的跨系统 IAM 客户端。"""
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
    """按当前用户和租户读取可见索引集目录，供资源归属校验。"""
    from api.log_search.default import SearchIndexSetResource

    # 不使用共享 API 实例，避免实例内残留的用户／租户状态被跨请求复用。
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
    """旧调用保持不变；原生执行使用请求内独立 API 身份。"""
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
    """把业务或索引集上下文解析为日志 IAM V3 资源。"""
    if spec["resource_type"] == "space":
        # 日志 IAM V3 引用监控空间资源，而不是日志系统内自建的 space。
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
    # ponytail: 当前只支持普通同空间索引集；平台／关联空间需要后续显式建模。
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
    """为真实缺失权限生成申请信息；生成失败不改变拒绝结果。"""
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
    # 申请链接生成失败不能改变拒绝结论，也不能泄漏 IAM 响应正文。
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
    """权限探测与执行共用同一个 native-first 判定，并返回实际回退结果。"""
    try:
        _audit(tool, request, "scope", "started", bk_biz_id=bk_biz_id)
        return _permission_state(tool, request, bk_biz_id, resource_context, include_apply_guide)
    except Exception as exc:
        _audit(tool, request, "authorization", "aborted", bk_biz_id=bk_biz_id, error_type=type(exc).__name__)
        raise


def _permission_state(tool, request, bk_biz_id, context, include_apply_guide):
    """执行资源解析、原生权限和旧 MCP 权限的严格顺序判定。"""
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
        # 资源范围先于 N/L 判定；归属校验失败不能触发旧权限回退。
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

    # 只有严格 False 才能触发回退；资源或 IAM 异常不能被捕获并伪装成无权限。
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
    """standalone Middleware 与 Unified execute_tool 共用的原生权限执行入口。"""
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
    """校验请求契约、权限和资源范围后调用共享 dispatcher。"""
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
    # standalone 历史告警 Schema 需要 bk_biz_ids；这里只接受与 bk_biz_id 相同的单业务，
    # 随后仍由共享 dispatcher 重新派生，调用方不能扩大业务范围。
    if "bk_biz_ids" in tool.backend_derived_fields and "bk_biz_ids" in args:
        values = args.pop("bk_biz_ids")
        if not isinstance(values, list) or len(values) != 1 or str(values[0]) != args.get("bk_biz_id"):
            raise ValidationError("bk_biz_ids must contain exactly the requested bk_biz_id.")
    # 资源 ID 必须是严格正整数，拒绝 bool 和整数值浮点数；
    # 传输兼容只在 standalone 边界处理，核心执行器不做宽松转换。
    resource_arg = tool.native_permission["resource_arg"]
    if tool.native_permission["resource_type"] == "indices" and resource_arg in args:
        value = args[resource_arg]
        if type(value) is not int or value < 1:
            raise ValidationError({resource_arg: "A positive integer resource ID is required."})
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
        # 权限状态是保留 bool/null 的结构化数据，不是 ValidationError 消息树。
        raise MCPPermissionDenied(state)
    request.biz_id = int(args["bk_biz_id"])
    request.skip_check = False
    from kernel_api.unified_mcp.dispatcher import dispatch_tool

    # 该标记只传递请求内身份，不是授权旁路，也不能跨请求复用。
    previous = getattr(request, "native_mcp_tool", None)
    request.native_mcp_tool = tool.name
    try:
        # dispatcher 继续执行原结果表／空间归属保护和 Resource 校验链。
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
