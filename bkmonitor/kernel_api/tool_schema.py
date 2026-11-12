"""Shared public request schemas for MCP and independent user APIs."""

from copy import deepcopy
from typing import Any

BACKEND_DERIVED_FIELDS = {
    "list_alerts": ("bk_biz_ids",),
    "get_alert_top_n": ("bk_biz_ids",),
}


UNIFIED_HIDDEN_FIELDS = {
    # ponytail: 全局标签缺少 profile_id 范围；APM Web 接管该校验后移除此覆盖。
    "get_profile_label": ("global_query",),
}


def _extract_input_schema(operation: dict[str, Any]) -> dict[str, Any]:
    """把 OpenAPI requestBody 或 query parameters 统一转换成对象 Schema。"""
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    body_schema = (content.get("application/json") or {}).get("schema")
    if body_schema:
        return deepcopy(body_schema)

    properties: dict[str, Any] = {}
    required: list[str] = []
    for parameter in operation.get("parameters") or []:
        name = parameter["name"]
        schema = deepcopy(parameter.get("schema") or {"type": "string"})
        if parameter.get("description"):
            schema["description"] = parameter["description"]
        properties[name] = schema
        if parameter.get("required"):
            required.append(name)
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _normalize_public_schema(tool_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """将原 MCP Schema 收敛为模型可直接使用的 Unified 公共契约。"""
    result = deepcopy(schema)
    result.setdefault("type", "object")
    properties = result.setdefault("properties", {})
    required = list(result.get("required") or [])

    # 统一数据工具必须显式携带业务上下文；兼容旧 OpenAPI 遗漏 required 的情况。
    if "bk_biz_id" in properties and "bk_biz_id" not in required:
        required.append("bk_biz_id")
    if "bk_biz_id" in properties:
        properties["bk_biz_id"]["type"] = "string"
    if tool_name in {"create_dashboard", "update_dashboard"}:
        # standalone 历史 wire-format 将 configs 描述为字符串；Unified 直接接收 JSON，
        # 而后端 Resource 实际需要字典，因此在公共 Schema 中修正类型。
        properties["configs"].update(
            type="object",
            minProperties=1,
            additionalProperties={"type": "string"},
        )

    # 后端兼容字段由 Unified 从 bk_biz_id 派生，模型只提交一个业务标识。
    for field_name in BACKEND_DERIVED_FIELDS.get(tool_name, ()):
        properties.pop(field_name, None)
        required = [name for name in required if name != field_name]
    for field_name in UNIFIED_HIDDEN_FIELDS.get(tool_name, ()):
        properties.pop(field_name, None)
        required = [name for name in required if name != field_name]

    if required:
        result["required"] = required
    else:
        result.pop("required", None)
    _normalize_nullable_schemas(result)
    _close_object_schemas(result)
    return result


def _normalize_nullable_schemas(schema: dict[str, Any]) -> None:
    """将 OpenAPI nullable 转为 Draft7 可执行的 null 类型约束。"""
    if schema.pop("nullable", False):
        schema_type = schema.get("type")
        if isinstance(schema_type, str):
            schema["type"] = [schema_type, "null"]
        elif isinstance(schema_type, list) and "null" not in schema_type:
            schema["type"] = [*schema_type, "null"]
        if "enum" in schema and None not in schema["enum"]:
            schema["enum"] = [*schema["enum"], None]

    for child in (schema.get("properties") or {}).values():
        if isinstance(child, dict):
            _normalize_nullable_schemas(child)
    if isinstance(schema.get("items"), dict):
        _normalize_nullable_schemas(schema["items"])
    for keyword in ("allOf", "anyOf", "oneOf"):
        for child in schema.get(keyword) or []:
            if isinstance(child, dict):
                _normalize_nullable_schemas(child)


def _close_object_schemas(schema: dict[str, Any]) -> None:
    """递归拒绝对象中的未声明字段，避免身份和权限参数被夹带。"""
    if schema.get("type") == "object" and "properties" in schema:
        schema.setdefault("additionalProperties", False)
    for child in (schema.get("properties") or {}).values():
        if isinstance(child, dict):
            _close_object_schemas(child)
    if isinstance(schema.get("items"), dict):
        _close_object_schemas(schema["items"])
    for keyword in ("allOf", "anyOf", "oneOf"):
        for child in schema.get(keyword) or []:
            if isinstance(child, dict):
                _close_object_schemas(child)
