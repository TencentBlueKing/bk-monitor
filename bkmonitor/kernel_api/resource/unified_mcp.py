"""Resources exposed by the unified monitoring MCP facade."""

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
from kernel_api.unified_mcp.registry import CATEGORY_ACTIONS, get_tool_registry
from kernel_api.unified_mcp.permissions import execute_native_tool, permission_state
from metadata.resources import ListBCSClusterInfoByBizResource, ListSpacesResource

CATEGORIES = tuple(CATEGORY_ACTIONS)
CAPABILITIES = ("discovery", "query", "analysis", "detail", "relation")


def get_permission_client() -> Permission:
    # The facade metadata tools are exempt from the legacy MCP middleware because
    # they do not have a single bk_biz_id.  Do not inherit request.skip_check here:
    # permission introspection must always query IAM for the current user.
    request = get_request()
    permission = Permission(request.user.username, bk_tenant_id=request.user.tenant_id)
    permission.skip_check = False
    return permission


def _permission_state_by_action(
    permission: Permission,
    actions: set[str],
    bk_biz_id: int | None = None,
) -> dict[str, str]:
    states: dict[str, str] = {}
    for action_id in actions:
        if bk_biz_id is None:
            spaces = permission.filter_space_list_by_action(action_id)
            allowed = bool(spaces)
        else:
            allowed = permission.is_allowed_by_biz(bk_biz_id, action_id)
        states[action_id] = "granted" if allowed else "missing"
    return states


def _mixed_permission_scopes(tools, params, permission):
    """Only used when native tools are selected; keep the legacy-only response unchanged."""
    request = get_request()
    bk_biz_id = params.get("bk_biz_id")
    scopes, missing = [], []
    legacy_spaces = {}
    legacy_states = (
        _permission_state_by_action(permission, {t.iam_action for t in tools if not t.native_permission}, bk_biz_id)
        if bk_biz_id is not None
        else {}
    )
    for tool in tools:
        if tool.native_permission:
            scope = permission_state(
                tool, request, bk_biz_id, params.get("resource_context"), params["include_apply_guide"]
            )
            scope["category"] = tool.category
            scopes.append(scope)
            if scope["state"] == "missing":
                missing.append(scope)
        elif bk_biz_id is None:
            if tool.iam_action not in legacy_spaces:
                legacy_spaces[tool.iam_action] = permission.filter_space_list_by_action(tool.iam_action)
            for space in legacy_spaces[tool.iam_action]:
                scopes.append(
                    {
                        "category": tool.category,
                        "tool_name": tool.name,
                        "action_id": tool.iam_action,
                        "resource": {"bk_biz_id": str(space["bk_biz_id"]), "space_name": space.get("display_name", "")},
                        "authorized": True,
                    }
                )
        else:
            allowed = legacy_states[tool.iam_action] == "granted"
            scope = {
                "category": tool.category,
                "tool_name": tool.name,
                "action_id": tool.iam_action,
                "resource": {"bk_biz_id": str(bk_biz_id)},
                "authorized": allowed,
            }
            scopes.append(scope)
            if not allowed:
                item = {**scope, "action_name": str(get_action_by_id(tool.iam_action).name)}
                if params["include_apply_guide"]:
                    item["apply_url"] = permission.get_apply_url(
                        [tool.iam_action], [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)]
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
    """Return deterministic catalog entries; no semantic search is performed."""

    class RequestSerializer(serializers.Serializer):
        tool_name = serializers.CharField(required=False, allow_blank=False)
        category = serializers.ChoiceField(required=False, choices=CATEGORIES)
        capability = serializers.ChoiceField(required=False, choices=CAPABILITIES)
        bk_biz_id = serializers.IntegerField(required=False)
        available_only = serializers.BooleanField(required=False, default=True)
        page = serializers.IntegerField(required=False, default=1, min_value=1)
        page_size = serializers.IntegerField(required=False, default=50, min_value=1, max_value=100)

    def perform_request(self, validated_request_data):
        registry = get_tool_registry()
        tools = registry.list(
            tool_name=validated_request_data.get("tool_name"),
            category=validated_request_data.get("category"),
            capability=validated_request_data.get("capability"),
        )
        if validated_request_data.get("tool_name") and not tools:
            raise ValidationError({"tool_name": "Unknown tool name; exact matching is required."})

        permission = get_permission_client()
        permission_states = _permission_state_by_action(
            permission,
            {tool.iam_action for tool in tools if not tool.native_permission},
            validated_request_data.get("bk_biz_id"),
        )
        states_by_tool = {
            tool.name: permission_state(tool, get_request(), validated_request_data.get("bk_biz_id"))["state"]
            if tool.native_permission
            else permission_states[tool.iam_action]
            for tool in tools
        }
        if validated_request_data["available_only"]:
            # Unknown instance scope is not denial. Keep it discoverable with requires_resource.
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
                for key in ("tool_name", "category", "capability", "bk_biz_id", "available_only")
                if key in validated_request_data
            },
            "tools": [tool.summary(states_by_tool[tool.name]) for tool in page_tools],
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }


class LookupToolSchemaResource(Resource):
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
        # Space discovery follows the existing platform-visible directory semantics.
        # Data access is still enforced by execute_tool on the target business.
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
        selected_tools = registry.list(tool_name=tool_name, category=category)
        if any(item.native_permission for item in selected_tools):
            return _mixed_permission_scopes(selected_tools, validated_request_data, get_permission_client())

        permission_targets = (
            [(tool.category, tool.iam_action)]
            if tool
            else [(category, CATEGORY_ACTIONS[category])]
            if category
            else list(CATEGORY_ACTIONS.items())
        )
        permission = get_permission_client()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        scopes = []
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
    class RequestSerializer(serializers.Serializer):
        tool_name = serializers.CharField(required=True, allow_blank=False)
        tool_args = serializers.JSONField(required=True)

        def validate_tool_args(self, value):
            if not isinstance(value, dict):
                raise serializers.ValidationError("tool_args must be a JSON object.")
            return value

    def perform_request(self, validated_request_data):
        registry = get_tool_registry()
        tool_name = validated_request_data["tool_name"]
        tool_args: dict[str, Any] = dict(validated_request_data["tool_args"])
        try:
            tool = registry.get(tool_name)
        except KeyError as exc:
            raise ValidationError({"tool_name": str(exc)}) from exc

        request = get_request(peaceful=True)
        if tool.native_permission:
            # Share validation, native-first authorization and execution with standalone MCP.
            # A legacy checked marker is never a grant for this path.
            data = execute_native_tool(tool, tool_args, request)
        else:
            errors = sorted(
                Draft7Validator(tool.input_schema).iter_errors(tool_args),
                key=lambda error: ".".join(str(part) for part in error.absolute_path),
            )
            if errors:
                error = errors[0]
                path = ".".join(str(part) for part in error.absolute_path)
                raise ValidationError({f"tool_args.{path}" if path else "tool_args": error.message})
            if tool.resource_arg not in tool_args:
                raise ValidationError({f"tool_args.{tool.resource_arg}": "This space-scoped argument is required."})
            try:
                bk_biz_id = int(tool_args[tool.resource_arg])
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    {f"tool_args.{tool.resource_arg}": "A valid integer business ID is required."}
                ) from exc
            if not getattr(request, "unified_mcp_permission_checked", False):
                get_permission_client().is_allowed_by_biz(bk_biz_id, tool.iam_action, raise_exception=True)
            data = dispatch_tool(tool_name, tool_args)
        return {
            "status": "success",
            "tool_name": tool_name,
            "data": data,
            "meta": {"truncated": False},
        }
