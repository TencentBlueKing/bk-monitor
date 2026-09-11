"""Unified MCP 对外门面：工具检索、Schema、元数据、权限探测与统一执行。"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.iam import Permission, ResourceEnum
from bkmonitor.iam.action import get_action_by_id
from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from kernel_api.unified_mcp.dispatcher import dispatch_tool
from kernel_api.unified_mcp.registry import CATEGORIES, get_tool_registry
from kernel_api.unified_mcp.permissions import execute_native_tool, permission_state
from metadata.resources import ListBCSClusterInfoByBizResource, ListSpacesResource

CAPABILITIES = ("discovery", "query", "analysis", "detail", "relation", "mutation", "export")


def get_permission_client() -> Permission:
    """基于当前请求用户创建强制校验权限的客户端。"""
    # 门面元数据工具可能没有单一 bk_biz_id，因此可跳过旧 MCP Middleware；
    # 权限探测本身不能继承 request.skip_check，必须始终查询当前用户的 IAM。
    request = get_request()
    permission = Permission(request.user.username, bk_tenant_id=request.user.tenant_id)
    permission.skip_check = False
    return permission


def _permission_state_by_action(
    permission: Permission,
    actions: set[str],
    bk_biz_id: int | None = None,
) -> dict[str, str]:
    """按指定业务批量计算 Action 状态；未给业务时检查是否存在任一可用空间。"""
    states: dict[str, str] = {}
    for action_id in actions:
        if bk_biz_id is None:
            spaces = permission.filter_space_list_by_action(action_id)
            allowed = bool(spaces)
        else:
            allowed = permission.is_allowed_by_biz(bk_biz_id, action_id)
        states[action_id] = "granted" if allowed else "missing"
    return states


def _legacy_tool_state(tool, action_states, action_spaces=None):
    """合并旧 MCP 与附加 Action，只有同一空间全部满足才视为可用。"""
    if tool.permission_exempt:
        return "exempt"
    if not tool.legacy_action_ids:
        return "missing"
    if action_spaces is not None:
        common_spaces = set.intersection(*(action_spaces[action_id] for action_id in tool.legacy_action_ids))
        return "granted" if common_spaces else "missing"
    return (
        "granted"
        if all(action_states.get(action_id) == "granted" for action_id in tool.legacy_action_ids)
        else "missing"
    )


def _mixed_permission_scopes(tools, params, permission):
    """混合计算原生和旧权限，同时保留多 Action 必须全部满足的约束。"""
    request = get_request()
    bk_biz_id = params.get("bk_biz_id")
    scopes, missing = [], []
    legacy_spaces = {}
    legacy_actions = {action_id for tool in tools if not tool.native_permission for action_id in tool.legacy_action_ids}
    legacy_states = _permission_state_by_action(permission, legacy_actions, bk_biz_id) if bk_biz_id is not None else {}
    for tool in tools:
        # 原生工具复用执行阶段同一 permission_state，避免探测与执行口径分叉。
        if tool.native_permission:
            scope = permission_state(
                tool, request, bk_biz_id, params.get("resource_context"), params["include_apply_guide"]
            )
            scope["category"] = tool.category
            scopes.append(scope)
            if scope["state"] == "missing":
                missing.append(scope)
            continue
        # 平台可见目录不要求业务权限，但只代表发现能力，不授权后续数据访问。
        if tool.permission_exempt:
            scopes.append(
                {
                    "category": tool.category,
                    "tool_name": tool.name,
                    "state": "exempt",
                    "authorized": True,
                }
            )
            continue
        if bk_biz_id is None:
            # 未指定业务时取所有必需 Action 的空间交集，不能跨业务拼接权限。
            for action_id in tool.legacy_action_ids:
                if action_id not in legacy_spaces:
                    legacy_spaces[action_id] = {
                        str(space["bk_biz_id"]): space for space in permission.filter_space_list_by_action(action_id)
                    }
            common_ids = set.intersection(*(set(legacy_spaces[action_id]) for action_id in tool.legacy_action_ids))
            for space_id in sorted(common_ids):
                space = legacy_spaces[tool.iam_action][space_id]
                scope = {
                    "category": tool.category,
                    "tool_name": tool.name,
                    "action_id": tool.iam_action,
                    "resource": {"bk_biz_id": space_id, "space_name": space.get("display_name", "")},
                    "authorized": True,
                }
                if tool.additional_iam_actions:
                    scope["additional_action_ids"] = list(tool.additional_iam_actions)
                scopes.append(scope)
            continue

        # 指定业务后逐项保留缺失 Action，便于返回准确申请指引。
        denied_actions = [action_id for action_id in tool.legacy_action_ids if legacy_states[action_id] != "granted"]
        scope = {
            "category": tool.category,
            "tool_name": tool.name,
            "action_id": tool.iam_action,
            "resource": {"bk_biz_id": str(bk_biz_id)},
            "authorized": not denied_actions,
        }
        if tool.additional_iam_actions:
            scope["additional_action_ids"] = list(tool.additional_iam_actions)
        scopes.append(scope)
        for action_id in denied_actions:
            item = {
                "category": tool.category,
                "tool_name": tool.name,
                "action_id": action_id,
                "action_name": str(get_action_by_id(action_id).name),
                "resource": scope["resource"],
                "authorized": False,
            }
            if params["include_apply_guide"]:
                item["apply_url"] = permission.get_apply_url(
                    [action_id], [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)]
                )
            missing.append(item)
    unresolved = any(scope.get("state") == "requires_resource" for scope in scopes)
    return {
        "authorized": bool(scopes) and all(scope["authorized"] for scope in scopes),
        "scopes": scopes,
        "missing_permissions": missing,
        "next_step": "补充目标业务或资源上下文后重查"
        if unresolved
        else "申请原生权限或旧 MCP 权限后重试"
        if missing
        else "",
    }


class LookupToolResource(Resource):
    """按精确条件返回确定性工具目录，不做语义搜索或模型排序。"""

    class RequestSerializer(serializers.Serializer):
        tool_name = serializers.CharField(required=False, allow_blank=False)
        category = serializers.ChoiceField(required=False, choices=CATEGORIES)
        capability = serializers.ChoiceField(required=False, choices=CAPABILITIES)
        bk_biz_id = serializers.IntegerField(required=False)
        available_only = serializers.BooleanField(required=False, default=True)
        page = serializers.IntegerField(required=False, default=1, min_value=1)
        page_size = serializers.IntegerField(required=False, default=50, min_value=1, max_value=100)

    def perform_request(self, validated_request_data):
        # Step 1: 只按结构化条件筛选工具，不解释自然语言意图。
        registry = get_tool_registry()
        tools = registry.list(
            tool_name=validated_request_data.get("tool_name"),
            category=validated_request_data.get("category"),
            capability=validated_request_data.get("capability"),
        )
        if validated_request_data.get("tool_name") and not tools:
            raise ValidationError({"tool_name": "Unknown tool name; exact matching is required."})

        # Step 2: 批量查询旧权限；原生工具由 permission_state 单独计算。
        legacy_actions = {
            action_id for tool in tools if not tool.native_permission for action_id in tool.legacy_action_ids
        }
        bk_biz_id = validated_request_data.get("bk_biz_id")
        permission_states = {}
        action_spaces = None
        if legacy_actions:
            permission = get_permission_client()
            if bk_biz_id is None:
                action_spaces = {
                    action_id: {str(space["bk_biz_id"]) for space in permission.filter_space_list_by_action(action_id)}
                    for action_id in legacy_actions
                }
            else:
                permission_states = _permission_state_by_action(permission, legacy_actions, bk_biz_id)
        states_by_tool = {
            tool.name: permission_state(tool, get_request(), validated_request_data.get("bk_biz_id"))["state"]
            if tool.native_permission
            else _legacy_tool_state(tool, permission_states, action_spaces)
            for tool in tools
        }
        if validated_request_data["available_only"]:
            # 未提供实例上下文不等于拒绝，requires_resource 工具仍保留给模型补参。
            tools = [tool for tool in tools if states_by_tool[tool.name] != "missing"]

        total = len(tools)
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        start = (page - 1) * page_size
        page_tools = tools[start : start + page_size]
        return {
            "catalog_version": registry.catalog_version,
            "filters": {
                key: validated_request_data[key]
                for key in (
                    "tool_name",
                    "category",
                    "capability",
                    "bk_biz_id",
                    "available_only",
                )
                if key in validated_request_data
            },
            "tools": [tool.summary(states_by_tool[tool.name]) for tool in page_tools],
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }


class LookupToolSchemaResource(Resource):
    """按精确工具名返回完整 Schema、权限、限制和执行契约。"""

    class RequestSerializer(serializers.Serializer):
        tool_name = serializers.CharField(required=True, allow_blank=False)

    def perform_request(self, validated_request_data):
        registry = get_tool_registry()
        try:
            tool = registry.get(validated_request_data["tool_name"])
        except KeyError as exc:
            raise ValidationError({"tool_name": str(exc)}) from exc
        return tool.schema_payload(registry.catalog_version)


class LookupMetadataResource(Resource):
    """复用现有接口查询空间或 BCS 集群等前置元数据。"""

    class RequestSerializer(serializers.Serializer):
        metadata_type = serializers.ChoiceField(required=True, choices=["spaces", "bcs_clusters"])
        space_name = serializers.CharField(required=False, allow_blank=False)
        bk_biz_id = serializers.IntegerField(required=False)
        page = serializers.IntegerField(required=False, default=1, min_value=1)
        page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)

        def validate(self, attrs):
            if attrs["metadata_type"] == "spaces" and not attrs.get("space_name"):
                raise serializers.ValidationError({"space_name": "space_name is required for spaces lookup."})
            if attrs["metadata_type"] == "bcs_clusters" and attrs.get("bk_biz_id") is None:
                raise serializers.ValidationError({"bk_biz_id": "bk_biz_id is required for BCS cluster lookup."})
            return attrs

    def perform_request(self, validated_request_data):
        metadata_type = validated_request_data["metadata_type"]
        if metadata_type == "bcs_clusters":
            bk_biz_id = validated_request_data["bk_biz_id"]
            get_permission_client().is_allowed_by_biz(
                bk_biz_id,
                "using_metadata_mcp",
                raise_exception=True,
            )
            return {
                "metadata_type": metadata_type,
                "bcs_clusters": ListBCSClusterInfoByBizResource().request(bk_biz_id=bk_biz_id),
            }

        result = ListSpacesResource().request(
            space_name=validated_request_data["space_name"],
            page=validated_request_data["page"],
            page_size=validated_request_data["page_size"],
        )
        # 空间发现沿用现有平台可见目录语义；后续数据访问仍由 execute_tool 按目标业务鉴权。
        spaces = []
        for item in result.get("list") or []:
            space_uid = item.get("space_uid") or f"{item.get('space_type_id', '')}__{item.get('space_id', '')}"
            bk_biz_id = str(space_uid_to_bk_biz_id(space_uid, item.get("id")))
            spaces.append(
                {
                    "space_name": item.get("space_name", ""),
                    "space_type": item.get("space_type_id", ""),
                    "bk_biz_id": bk_biz_id,
                }
            )
        return {
            "metadata_type": metadata_type,
            "spaces": spaces,
            "pagination": {
                "page": validated_request_data["page"],
                "page_size": validated_request_data["page_size"],
                "total": result.get("count", len(spaces)),
            },
        }


class LookupPermissionsResource(Resource):
    """只读探测当前用户权限，不授予权限，也不替代最终执行校验。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False)
        category = serializers.ChoiceField(required=False, choices=CATEGORIES)
        tool_name = serializers.CharField(required=False, allow_blank=False)
        include_apply_guide = serializers.BooleanField(required=False, default=True)
        resource_context = serializers.DictField(required=False, default=dict)

        def validate(self, attrs):
            context = attrs["resource_context"]
            if context and not attrs.get("tool_name"):
                raise serializers.ValidationError("resource_context requires an exact tool_name")
            if (
                set(context) - {"index_set_id", "target_type", "id", "alert_id"}
                or context.get("target_type", "index_set") != "index_set"
            ):
                raise serializers.ValidationError("Unsupported permission resource_context")
            return attrs

    def perform_request(self, validated_request_data):
        # Step 1: 先按工具名／分类确定真实权限目标，权限点不接受调用方覆盖。
        registry = get_tool_registry()
        tool_name = validated_request_data.get("tool_name")
        category = validated_request_data.get("category")
        tool = None
        if tool_name:
            try:
                tool = registry.get(tool_name)
            except KeyError as exc:
                raise ValidationError({"tool_name": str(exc)}) from exc
            if category and category != tool.category:
                raise ValidationError({"category": f"{tool_name} belongs to category {tool.category}."})

        selected_tools = registry.list(tool_name=tool_name, category=category)
        if selected_tools and all(item.permission_exempt for item in selected_tools):
            return {
                "authorized": True,
                "scopes": [
                    {
                        "category": item.category,
                        "tool_name": item.name,
                        "state": "exempt",
                        "authorized": True,
                    }
                    for item in selected_tools
                ],
                "missing_permissions": [],
                "next_step": "",
            }

        # Step 2: 资源上下文必须与精确工具的原生资源模型一致。
        context = validated_request_data.get("resource_context")
        if context:
            spec = tool.native_permission if tool else None
            if tool and not spec:
                raise ValidationError(
                    {
                        "resource_context": (
                            f"{tool.name} is using legacy MCP permissions ({tool.iam_action}); "
                            "resource-level permission checks require native mode. "
                            "For supported tools, enable MCP_NATIVE_PERMISSION_TOOLS; "
                            "omit resource_context to check legacy space permissions only."
                        )
                    }
                )
            allowed_keys = (
                {"index_set_id", "target_type"}
                if spec and spec["resource_type"] == "indices"
                else {spec["target_arg"]}
                if spec and spec.get("target_arg")
                else set()
            )
            if set(context) - allowed_keys:
                raise ValidationError("resource_context does not match the selected tool")
        # Step 3: 原生、附加 Action 和权限豁免混合出现时，按工具逐项返回状态。
        if any(item.native_permission for item in selected_tools) or (
            (tool_name or category)
            and any(item.additional_iam_actions or item.permission_exempt for item in selected_tools)
        ):
            return _mixed_permission_scopes(selected_tools, validated_request_data, get_permission_client())

        # Step 4: 纯旧权限工具按 category/action 去重，减少重复 IAM 查询。
        permission_targets = sorted(
            {(item.category, action_id) for item in selected_tools for action_id in item.legacy_action_ids}
        )
        permission = get_permission_client()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        scopes = [
            {
                "category": item.category,
                "tool_name": item.name,
                "state": "exempt",
                "authorized": True,
            }
            for item in selected_tools
            if item.permission_exempt
        ]
        missing_permissions = []

        for action_category, action_id in permission_targets:
            action = get_action_by_id(action_id)
            if bk_biz_id is None:
                spaces = permission.filter_space_list_by_action(action_id)
                for space in spaces:
                    scopes.append(
                        {
                            "category": action_category,
                            "tool_name": tool_name,
                            "action_id": action_id,
                            "resource": {
                                "bk_biz_id": str(space["bk_biz_id"]),
                                "space_name": space.get("display_name", ""),
                            },
                            "authorized": True,
                        }
                    )
                continue

            authorized = permission.is_allowed_by_biz(bk_biz_id, action_id)
            resource = {"bk_biz_id": str(bk_biz_id)}
            scopes.append(
                {
                    "category": action_category,
                    "tool_name": tool_name,
                    "action_id": action_id,
                    "resource": resource,
                    "authorized": authorized,
                }
            )
            if not authorized:
                missing = {
                    "action_id": action_id,
                    "action_name": str(action.name),
                    "resource": resource,
                }
                if validated_request_data["include_apply_guide"]:
                    iam_resource = ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)
                    missing["apply_url"] = permission.get_apply_url([action_id], [iam_resource])
                missing_permissions.append(missing)

        return {
            "authorized": bool(scopes) and all(scope["authorized"] for scope in scopes),
            "scopes": scopes,
            "missing_permissions": missing_permissions,
            "next_step": "申请通过后重新执行原工具" if missing_permissions else "",
        }


class ExecuteToolResource(Resource):
    """校验工具、参数、权限与确认状态后，分发到原 Resource。"""

    class RequestSerializer(serializers.Serializer):
        tool_name = serializers.CharField(required=True, allow_blank=False)
        tool_args = serializers.JSONField(required=True)

        def validate_tool_args(self, value):
            if not isinstance(value, dict):
                raise serializers.ValidationError("tool_args must be a JSON object.")
            return value

    def perform_request(self, validated_request_data):
        # Step 1: tool_name 只从服务端 Registry 解析，拒绝未知工具和调用方自定义路由。
        registry = get_tool_registry()
        tool_name = validated_request_data["tool_name"]
        tool_args: dict[str, Any] = dict(validated_request_data["tool_args"])
        try:
            tool = registry.get(tool_name)
        except KeyError as exc:
            raise ValidationError({"tool_name": str(exc)}) from exc
        request = get_request(peaceful=True)
        if tool.native_permission:
            # standalone 与 Unified 共用同一套 Schema、native-first 判定和执行函数；
            # 历史 checked 标记不能作为新权限凭据。
            data = execute_native_tool(tool, tool_args, request)
        else:
            # Step 2: 在权限和 Resource 调用前执行完整 JSON Schema 校验。
            errors = sorted(
                Draft7Validator(tool.input_schema).iter_errors(tool_args),
                key=lambda error: ".".join(str(part) for part in error.absolute_path),
            )
            if errors:
                error = errors[0]
                path = ".".join(str(part) for part in error.absolute_path)
                raise ValidationError({f"tool_args.{path}" if path else "tool_args": error.message})
            if not tool.permission_exempt:
                # Step 3: 复用旧 MCP Action，并补回 Unified 直调可能绕过的原路由权限。
                if tool.resource_arg not in tool_args:
                    raise ValidationError({f"tool_args.{tool.resource_arg}": "This space-scoped argument is required."})
                try:
                    bk_biz_id = int(tool_args[tool.resource_arg])
                except (TypeError, ValueError) as exc:
                    raise ValidationError(
                        {f"tool_args.{tool.resource_arg}": "A valid integer business ID is required."}
                    ) from exc
                middleware_checked = getattr(request, "unified_mcp_permission_checked", False)
                permission = None
                for action_id in tool.legacy_action_ids:
                    if middleware_checked and action_id == tool.iam_action:
                        continue
                    permission = permission or get_permission_client()
                    permission.is_allowed_by_biz(bk_biz_id, action_id, raise_exception=True)
            # Unified 新增的 confirm 只用于门面确认；原 Resource 不接收时在分发前移除。
            dispatch_args = dict(tool_args)
            if tool.requires_confirmation and not tool.forwards_confirmation:
                dispatch_args.pop("confirm")
            # Step 4: 只有参数、确认和全部权限通过后，才进入原业务 Resource。
            data = dispatch_tool(tool_name, dispatch_args)
        return {
            "status": "success",
            "tool_name": tool_name,
            "data": data,
            "meta": {"truncated": False},
        }
