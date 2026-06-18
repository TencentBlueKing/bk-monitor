"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from django.db.models import Count, Q
from django.core.serializers.json import DjangoJSONEncoder

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException

SAFETY_LEVEL_READ = "read"
SAFETY_LEVEL_WRITE = "write"
SAFETY_LEVEL_DESTRUCTIVE = "destructive"
PAGE_LIST_TENANT_SCHEMA = "可选，租户 ID；缺省或空表示全租户查询"
REQUIRED_TENANT_SCHEMA = "必填，租户 ID"


def normalize_bk_tenant_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def get_bk_tenant_id(params: dict[str, Any]) -> str:
    return str(params.get("bk_tenant_id") or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID


def get_page_list_bk_tenant_id(params: dict[str, Any]) -> str | None:
    return normalize_bk_tenant_id(params.get("bk_tenant_id"))


def require_bk_tenant_id(params: dict[str, Any]) -> str:
    bk_tenant_id = normalize_bk_tenant_id(params.get("bk_tenant_id"))
    if not bk_tenant_id:
        raise CustomException(message="bk_tenant_id 为必填项")
    return bk_tenant_id


def filter_by_bk_tenant_id(queryset: Any, bk_tenant_id: str | None):
    return queryset.filter(bk_tenant_id=bk_tenant_id) if bk_tenant_id else queryset


def tenant_filter_kwargs(bk_tenant_id: str | None) -> dict[str, Any]:
    return {"bk_tenant_id": bk_tenant_id} if bk_tenant_id else {}


def tenant_resource_key(bk_tenant_id: str | None, resource_id: Any) -> tuple[str | None, Any]:
    return bk_tenant_id, resource_id


def instance_tenant_resource_key(instance: Any, resource_field: str) -> tuple[str | None, Any]:
    return tenant_resource_key(getattr(instance, "bk_tenant_id", None), getattr(instance, resource_field, None))


def get_scoped_map_value(mapping: dict[Any, Any], bk_tenant_id: str | None, resource_id: Any) -> Any:
    scoped_key = tenant_resource_key(bk_tenant_id, resource_id)
    if scoped_key in mapping:
        return mapping[scoped_key]
    return mapping.get(resource_id)


def filter_by_tenant_resource_pairs(
    queryset: Any,
    resource_field: str,
    pairs: Iterable[tuple[str | None, Any]],
    *,
    tenant_field: str = "bk_tenant_id",
) -> Any:
    normalized_pairs = [
        (bk_tenant_id, resource_id)
        for bk_tenant_id, resource_id in pairs
        if bk_tenant_id not in (None, "") and resource_id not in (None, "")
    ]
    if not normalized_pairs:
        return queryset.none()

    query = Q()
    for bk_tenant_id, resource_id in normalized_pairs:
        query |= Q(**{tenant_field: bk_tenant_id, resource_field: resource_id})
    return queryset.filter(query)


def normalize_positive_int(value: Any, field_name: str, *, default: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    try:
        normalized_value = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error

    if normalized_value < 1:
        raise CustomException(message=f"{field_name} 必须大于等于 1")

    return min(normalized_value, maximum)


def normalize_pagination(
    params: dict[str, Any], *, default_page_size: int = 20, max_page_size: int = 100
) -> tuple[int, int]:
    page = normalize_positive_int(params.get("page"), "page", default=1, maximum=10**9)
    page_size = normalize_positive_int(
        params.get("page_size"), "page_size", default=default_page_size, maximum=max_page_size
    )
    return page, page_size


def normalize_ordering(ordering: Any, allowed_fields: set[str], *, default: str) -> str:
    if ordering in (None, ""):
        return default
    if not isinstance(ordering, str):
        raise CustomException(message="ordering 必须是字符串")

    normalized_ordering = ordering.strip()
    field_name = normalized_ordering[1:] if normalized_ordering.startswith("-") else normalized_ordering
    if field_name not in allowed_fields:
        allowed_text = ", ".join(sorted(allowed_fields))
        raise CustomException(message=f"不支持按 {field_name} 排序，可选字段: {allowed_text}")
    return normalized_ordering


def normalize_optional_bool(value: Any, field_name: str) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value in {"true", "1", "yes", "y"}:
            return True
        if normalized_value in {"false", "0", "no", "n"}:
            return False
    raise CustomException(message=f"{field_name} 必须是布尔值")


def normalize_include(value: Any, allowed_values: set[str], *, default: Iterable[str] = ()) -> set[str]:
    if value in (None, ""):
        return set(default)

    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = value
    else:
        raise CustomException(message="include 必须是字符串或列表")

    includes = {str(item).strip() for item in raw_values if str(item).strip()}
    unsupported_values = includes - allowed_values
    if unsupported_values:
        allowed_text = ", ".join(sorted(allowed_values))
        unsupported_text = ", ".join(sorted(unsupported_values))
        raise CustomException(message=f"不支持的 include: {unsupported_text}，可选值: {allowed_text}")
    return includes


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(to_json_safe(key)): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, set | frozenset):
        return [to_json_safe(item) for item in sorted(value, key=str)]

    serialized_value = serialize_value(value)
    if serialized_value is not value:
        return to_json_safe(serialized_value)

    try:
        return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False))
    except TypeError:
        return str(value)


def serialize_model(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {field: serialize_value(getattr(instance, field, None)) for field in fields}


def paginate_queryset(queryset, *, page: int, page_size: int) -> tuple[list[Any], int]:
    total = queryset.count()
    offset = (page - 1) * page_size
    return list(queryset[offset : offset + page_size]), total


def build_response(
    *,
    operation: str,
    func_name: str,
    bk_tenant_id: str | None,
    data: dict[str, Any],
    warnings: list[dict[str, Any]] | None = None,
    safety_level: str = SAFETY_LEVEL_READ,
) -> dict[str, Any]:
    return to_json_safe(
        {
            "data": data,
            "warnings": warnings or [],
            "meta": {
                "operation": operation,
                "func_name": func_name,
                "safety_level": safety_level,
                "effective_bk_tenant_id": bk_tenant_id,
                "tenant_scope": "single" if bk_tenant_id else "all",
            },
        }
    )


def count_by_field(model_cls: Any, *, group_field: str, values: Iterable[Any], **filters: Any) -> dict[Any, int]:
    normalized_values = [value for value in values if value not in (None, "")]
    if not normalized_values:
        return {}

    queryset = model_cls.objects.filter(**filters, **{f"{group_field}__in": normalized_values})
    pk_field = model_cls._meta.pk.name
    return {item[group_field]: item["total"] for item in queryset.values(group_field).annotate(total=Count(pk_field))}


def count_by_tenant_and_field(
    model_cls: Any,
    *,
    group_field: str,
    values: Iterable[Any],
    **filters: Any,
) -> dict[tuple[str | None, Any], int]:
    normalized_values = [value for value in values if value not in (None, "")]
    if not normalized_values:
        return {}

    queryset = model_cls.objects.filter(**filters, **{f"{group_field}__in": normalized_values})
    pk_field = model_cls._meta.pk.name
    return {
        tenant_resource_key(item["bk_tenant_id"], item[group_field]): item["total"]
        for item in queryset.values("bk_tenant_id", group_field).annotate(total=Count(pk_field))
    }


def _mask_sensitive_fields(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: "***" if k.lower() == "password" else _mask_sensitive_fields(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_mask_sensitive_fields(item) for item in data]
    return data


def serialize_option(option: Any) -> dict[str, Any]:
    try:
        value = option.get_value()
    except Exception:
        value = option.value

    return {
        "name": option.name,
        "value": serialize_value(value),
        "value_type": option.value_type,
        "creator": option.creator,
        "create_time": serialize_value(option.create_time),
    }
