"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import re
from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id, normalize_pagination
from metadata import config
from metadata.utils import consul_tools

FUNC_CONSUL_KEY_LIST = "admin.consul.key_list"
FUNC_CONSUL_VALUE_GET = "admin.consul.value_get"
MAX_RELATIVE_PATH_LENGTH = 1024
MAX_VALUE_SIZE_BYTES = 1024 * 1024
SENSITIVE_TEXT_PATTERN = re.compile(
    r"((?:^|[^a-z0-9])(?:token|secret|password|passwd|cookie|authorization|credential|api[_-]?key|"
    r"private[_-]?key|access[_-]?key|signing[_-]?key|encryption[_-]?key|decoded[_-]?key|key)"
    r"\s*[:=]\s*[\"']?)([^\s,;\"'}\]\n]+)",
    re.IGNORECASE,
)


def _normalize_relative_path(value: Any, field_name: str, *, allow_empty: bool) -> str:
    if value in (None, ""):
        if allow_empty:
            return ""
        raise CustomException(message=f"{field_name} 为必填项")
    if not isinstance(value, str):
        raise CustomException(message=f"{field_name} 必须是字符串")

    normalized = value.strip()
    if not normalized:
        if allow_empty:
            return ""
        raise CustomException(message=f"{field_name} 为必填项")
    if len(normalized) > MAX_RELATIVE_PATH_LENGTH:
        raise CustomException(message=f"{field_name} 长度不能超过 {MAX_RELATIVE_PATH_LENGTH}")
    if normalized.startswith("/"):
        raise CustomException(message=f"{field_name} 必须是 Metadata 根路径下的相对路径")

    segments = normalized.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise CustomException(message=f"{field_name} 不能包含空路径段、. 或 ..")
    return "/".join(segments)


def _compose_consul_path(relative_path: str) -> tuple[str, str]:
    root_path = config.CONSUL_PATH.rstrip("/")
    full_path = root_path if not relative_path else f"{root_path}/{relative_path}"
    if full_path != root_path and not full_path.startswith(f"{root_path}/"):
        raise CustomException(message="查询路径超出 Metadata Consul 根路径")
    return root_path, full_path


def _normalize_consul_key(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CustomException(message="Consul 返回了非 UTF-8 key") from error
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return (
        "token" in normalized
        or "secret" in normalized
        or "password" in normalized
        or "passwd" in normalized
        or "credential" in normalized
        or "cookie" in normalized
        or "authorization" in normalized
        or "authheader" in normalized
        or normalized == "headers"
        or normalized == "key"
        or normalized.endswith("key")
        or normalized.endswith("apikey")
        or normalized.endswith("privatekey")
    )


def _redact_sensitive_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _is_sensitive_key(str(key)) and not isinstance(item, bool)
            else _redact_sensitive_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive_value(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_TEXT_PATTERN.sub(r"\1[REDACTED]", value)
    return value


def _serialize_value(raw_value: Any, *, include_sensitive: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if raw_value is None:
        value_bytes = b""
    elif isinstance(raw_value, bytes):
        value_bytes = raw_value
    elif isinstance(raw_value, bytearray):
        value_bytes = bytes(raw_value)
    elif isinstance(raw_value, str):
        value_bytes = raw_value.encode("utf-8")
    else:
        value_bytes = str(raw_value).encode("utf-8")

    result: dict[str, Any] = {
        "value_size_bytes": len(value_bytes),
        "value_format": None,
        "value": None,
        "content_omitted": False,
        "content_omitted_reason": None,
    }
    warnings: list[dict[str, Any]] = []

    if len(value_bytes) > MAX_VALUE_SIZE_BYTES:
        result.update(
            {
                "content_omitted": True,
                "content_omitted_reason": "too_large",
            }
        )
        warnings.append(
            {
                "code": "CONSUL_VALUE_TOO_LARGE",
                "message": "Consul value 超过 1 MiB，已省略内容",
                "details": {"value_size_bytes": len(value_bytes)},
            }
        )
        return result, warnings

    try:
        value_text = value_bytes.decode("utf-8")
    except UnicodeDecodeError:
        result["value_format"] = "binary"
        if include_sensitive:
            result["value"] = base64.b64encode(value_bytes).decode("ascii")
        else:
            result.update(
                {
                    "content_omitted": True,
                    "content_omitted_reason": "binary_redacted",
                }
            )
            warnings.append(
                {
                    "code": "CONSUL_BINARY_VALUE_REDACTED",
                    "message": "二进制 Consul value 在普通查看模式下不返回内容",
                }
            )
        return result, warnings

    try:
        parsed_value = json.loads(value_text)
        result["value"] = parsed_value if include_sensitive else _redact_sensitive_value(parsed_value)
        result["value_format"] = "json"
    except json.JSONDecodeError:
        result["value"] = value_text if include_sensitive else _redact_sensitive_value(value_text)
        result["value_format"] = "text"
    return result, warnings


@KernelRPCRegistry.register(
    FUNC_CONSUL_KEY_LIST,
    summary="Admin 分页查询 Metadata Consul key",
    description=(
        "仅查询当前环境 metadata.config.CONSUL_PATH 根路径下的 key 名；"
        "prefix 必须是相对路径，接口使用 Consul keys=True，不递归读取 value。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID，仅用于统一 envelope",
        "prefix": "可选，Metadata Consul 根路径下的相对 key 前缀；空值表示根路径",
        "page": "可选，页码，默认 1",
        "page_size": "可选，每页数量，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "prefix": "v1/default/data_id", "page": 1, "page_size": 20},
)
def list_consul_keys(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    prefix = _normalize_relative_path(params.get("prefix"), "prefix", allow_empty=True)
    page, page_size = normalize_pagination(params, default_page_size=20, max_page_size=100)
    root_path, full_prefix = _compose_consul_path(prefix)

    _, raw_keys = consul_tools.HashConsul().list_keys(full_prefix)
    root_prefix = f"{root_path}/"
    relative_paths: list[str] = []
    ignored_key_count = 0
    for raw_key in raw_keys or []:
        key = _normalize_consul_key(raw_key)
        if key == root_path:
            continue
        if not key.startswith(root_prefix):
            ignored_key_count += 1
            continue
        relative_path = key[len(root_prefix) :]
        if relative_path:
            relative_paths.append(relative_path)

    relative_paths = sorted(set(relative_paths))
    total = len(relative_paths)
    offset = (page - 1) * page_size
    warnings = []
    if ignored_key_count:
        warnings.append(
            {
                "code": "CONSUL_OUT_OF_SCOPE_KEYS_IGNORED",
                "message": "Consul 返回了 Metadata 根路径之外的 key，已忽略",
                "details": {"ignored_key_count": ignored_key_count},
            }
        )

    return build_response(
        operation="consul.key_list",
        func_name=FUNC_CONSUL_KEY_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "root_path": root_path,
            "prefix": prefix,
            "items": [{"relative_path": path} for path in relative_paths[offset : offset + page_size]],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONSUL_VALUE_GET,
    summary="Admin 查询单个 Metadata Consul value",
    description=(
        "精确查询当前环境 metadata.config.CONSUL_PATH 根路径下的单个 key；"
        "path 必须是相对路径。include_sensitive=true 仅供管理端受审计地读取原始敏感内容。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID，仅用于统一 envelope",
        "path": "必填，Metadata Consul 根路径下的相对 key",
        "include_sensitive": "可选，是否读取二进制原始内容；默认 false",
    },
    example_params={"bk_tenant_id": "system", "path": "v1/default/data_id/1001", "include_sensitive": False},
)
def get_consul_value(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    relative_path = _normalize_relative_path(params.get("path"), "path", allow_empty=False)
    include_sensitive = params.get("include_sensitive", False)
    if not isinstance(include_sensitive, bool):
        raise CustomException(message="include_sensitive 必须是布尔值")

    root_path, full_path = _compose_consul_path(relative_path)
    consul_index, entry = consul_tools.HashConsul().get(full_path)
    if entry is None:
        data = {
            "root_path": root_path,
            "relative_path": relative_path,
            "exists": False,
            "consul_index": consul_index,
            "create_index": None,
            "modify_index": None,
            "lock_index": None,
            "flags": None,
            "session": None,
            "value_size_bytes": None,
            "value_format": None,
            "value": None,
            "content_omitted": False,
            "content_omitted_reason": None,
        }
        warnings: list[dict[str, Any]] = []
    else:
        value_data, warnings = _serialize_value(entry.get("Value"), include_sensitive=include_sensitive)
        data = {
            "root_path": root_path,
            "relative_path": relative_path,
            "exists": True,
            "consul_index": consul_index,
            "create_index": entry.get("CreateIndex"),
            "modify_index": entry.get("ModifyIndex"),
            "lock_index": entry.get("LockIndex"),
            "flags": entry.get("Flags"),
            "session": entry.get("Session"),
            **value_data,
        }

    return build_response(
        operation="consul.value_get",
        func_name=FUNC_CONSUL_VALUE_GET,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings,
    )
