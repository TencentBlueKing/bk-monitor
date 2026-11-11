"""Reviewed independent user API catalog shared by gateway generation and routing.

The original MCP OpenAPI files own business schemas. Only this explicit allowlist
is published in the user directory; operational and dedicated endpoints stay private.
This module is also used by merge_resources.py and must not depend on Django.
"""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import re

import yaml

from kernel_api.tool_schema import _extract_input_schema, _normalize_public_schema

USER_API_PREFIX = "/user/"
USER_API_BACKEND_PREFIX = "/api/v4/user/"
USER_API_TAG = "独立用户态接口"
FACADE_OPERATIONS = frozenset(
    {"lookup_tool", "lookup_tool_schema", "lookup_metadata", "lookup_permissions", "execute_tool"}
)

# Explicitly reviewed business sources; new MCP files do not publish themselves.
USER_API_SOURCE_FILES = (
    "alert_handling_mcp.yaml",
    "alert_mcp.yaml",
    "apm_mcp.yaml",
    "dashboard_mcp.yaml",
    "event_mcp.yaml",
    "log_collection_clean_config_mcp.yaml",
    "log_collection_create_mcp.yaml",
    "log_collection_discovery_mcp.yaml",
    "log_collection_etl_preview_mcp.yaml",
    "log_collection_index_set_mcp.yaml",
    "log_collection_mcp.yaml",
    "log_collection_special_create_mcp.yaml",
    "log_collection_special_update_mcp.yaml",
    "log_collection_status_mcp.yaml",
    "log_collection_update_mcp.yaml",
    "log_extract_mcp.yaml",
    "log_mcp.yaml",
    "metadata_mcp.yaml",
    "metrics_mcp.yaml",
    "recording_rule_mcp.yaml",
    "relation_mcp.yaml",
    "unified_mcp.yaml",
)

CONFIRMATION_OPERATIONS = frozenset(
    {
        "apply_recording_rule",
        "create_alarm_notice_group",
        "create_alarm_shield",
        "create_alarm_strategy",
        "create_bkdata_index_set",
        "create_custom_report",
        "create_dashboard",
        "create_log_extract_task",
        "create_recording_rule",
        "create_third_party_es",
        "delete_alarm_assign_group",
        "delete_recording_rule",
        "disable_alarm_shield",
        "fast_create_log_collector",
        "fast_update_log_collector",
        "get_log_extract_download_url",
        "save_alarm_assign_group",
        "search_log_extract_files",
        "update_alarm_action_config",
        "update_alarm_notice_group",
        "update_alarm_shield",
        "update_alarm_strategy",
        "update_bkdata_index_set",
        "update_custom_report",
        "update_dashboard",
        "update_log_collector_clean_config",
        "update_recording_rule",
        "update_third_party_es",
    }
)


def build_user_api_paths(source_root: Path) -> dict:
    """Generate public aliases without changing any MCP resource or application API."""
    paths = {}
    for filename in USER_API_SOURCE_FILES:
        source = source_root / filename
        if not source.exists():
            continue
        document = yaml.safe_load(source.read_text())
        for source_path, methods in document["paths"].items():
            if not source_path.startswith("/mcp/"):
                raise ValueError(f"Unexpected user API source path: {source_path}")
            for method, source_operation in methods.items():
                name = source_operation["operationId"]
                if name == "apm_mcp_calculate_by_range":
                    name = "calculate_by_range"
                if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                    raise ValueError(f"Invalid user API name: {name}")
                operation = deepcopy(source_operation)
                operation["operationId"] = f"user_{name}"
                operation["tags"] = [USER_API_TAG]
                operation["summary"] = f"用户态-{source_operation.get('summary') or name}"
                if name not in FACADE_OPERATIONS:
                    schema = _normalize_public_schema(name, _extract_input_schema(source_operation))
                    if name in CONFIRMATION_OPERATIONS:
                        schema.setdefault("properties", {})["confirm"] = {
                            "type": "boolean",
                            "enum": [True],
                            "description": "Must be true after explicit user confirmation. 用户明确确认后必须传 true。",
                        }
                        schema["required"] = list(dict.fromkeys([*schema.get("required", []), "confirm"]))
                    operation.pop("parameters", None)
                    operation.pop("requestBody", None)
                    if method.lower() == "get":
                        operation["parameters"] = [
                            {
                                "name": key,
                                "in": "query",
                                "required": key in schema.get("required", []),
                                "schema": value,
                            }
                            for key, value in schema.get("properties", {}).items()
                        ]
                    else:
                        operation["requestBody"] = {
                            "required": True,
                            "content": {"application/json": {"schema": schema}},
                        }
                resource = operation["x-bk-apigateway-resource"]
                resource["isPublic"] = True
                resource["allowApplyPermission"] = False
                resource["matchSubpath"] = False
                resource["backend"].update(
                    method=method.lower(), path=f"{USER_API_BACKEND_PREFIX}{name}/", matchSubpath=False
                )
                resource["authConfig"] = {
                    "userVerifiedRequired": True,
                    "appVerifiedRequired": False,
                    "resourcePermissionRequired": False,
                    "oauth2PersonalClientEnabled": True,
                }
                path = f"{USER_API_PREFIX}{name}/"
                if method in paths.setdefault(path, {}):
                    raise ValueError(f"Duplicate user API: {method} {path}")
                paths[path][method] = operation
    return paths


@lru_cache(maxsize=1)
def user_api_routes(source_root: str) -> dict:
    """Match exact reviewed methods and backend paths, including GET's HEAD alias."""
    return {
        (method.upper(), operation["x-bk-apigateway-resource"]["backend"]["path"].rstrip("/")): (
            path.removeprefix(USER_API_PREFIX).strip("/")
        )
        for path, methods in build_user_api_paths(Path(source_root)).items()
        for method, operation in methods.items()
    }


def resolve_user_api(source_root: str, method: str, path: str) -> str | None:
    method = "GET" if method.upper() == "HEAD" else method.upper()
    path = re.sub(r"\.[a-z0-9]+$", "", path.rstrip("/"))
    return user_api_routes(source_root).get((method, path))
