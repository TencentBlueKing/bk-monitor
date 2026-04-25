"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from django.db.models import Count

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException

SAFETY_LEVEL_READ = "read"


def get_bk_tenant_id(params: dict[str, Any]) -> str:
    return str(params.get("bk_tenant_id") or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID


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
    bk_tenant_id: str,
    data: dict[str, Any],
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "data": data,
        "warnings": warnings or [],
        "meta": {
            "operation": operation,
            "func_name": func_name,
            "safety_level": SAFETY_LEVEL_READ,
            "effective_bk_tenant_id": bk_tenant_id,
        },
    }


def count_by_field(model_cls: Any, *, group_field: str, values: Iterable[Any], **filters: Any) -> dict[Any, int]:
    normalized_values = [value for value in values if value not in (None, "")]
    if not normalized_values:
        return {}

    queryset = model_cls.objects.filter(**filters, **{f"{group_field}__in": normalized_values})
    pk_field = model_cls._meta.pk.name
    return {item[group_field]: item["total"] for item in queryset.values(group_field).annotate(total=Count(pk_field))}


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
