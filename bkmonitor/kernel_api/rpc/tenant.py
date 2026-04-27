"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource.exceptions import CustomException
from metadata import models
from metadata.models.space.utils import reformat_table_id


def inject_bk_tenant_id(params: dict[str, Any]) -> dict[str, Any]:
    normalized_params = dict(params or {})
    explicit_bk_tenant_id = str(normalized_params.get("bk_tenant_id") or "").strip()
    if explicit_bk_tenant_id:
        normalized_params["bk_tenant_id"] = explicit_bk_tenant_id
        return normalized_params

    inferred_bk_tenant_id = infer_bk_tenant_id(normalized_params)
    if inferred_bk_tenant_id:
        normalized_params["bk_tenant_id"] = inferred_bk_tenant_id
    return normalized_params


def infer_bk_tenant_id(params: dict[str, Any]) -> str | None:
    identifier_tenants: list[tuple[str, str]] = []

    for field_name, values in _collect_identifier_values(params).items():
        if not values:
            continue

        tenant_ids = _query_tenant_ids(field_name, values)
        if not tenant_ids:
            continue

        if len(tenant_ids) > 1:
            raise CustomException(
                message=(f"无法根据 {field_name} 唯一反查 bk_tenant_id，命中了多个租户: {sorted(tenant_ids)}")
            )

        identifier_tenants.append((field_name, next(iter(tenant_ids))))

    if not identifier_tenants:
        return None

    unique_tenant_ids = {tenant_id for _, tenant_id in identifier_tenants}
    if len(unique_tenant_ids) > 1:
        details = ", ".join(f"{field_name} -> {tenant_id}" for field_name, tenant_id in identifier_tenants)
        raise CustomException(message=f"根据传入参数反查到多个不同租户，请补充 bk_tenant_id 明确指定：{details}")

    return next(iter(unique_tenant_ids))


def _collect_identifier_values(params: dict[str, Any]) -> dict[str, list[Any]]:
    return {
        "bk_biz_id": _normalize_int_list(params.get("bk_biz_id")),
        "bk_biz_ids": _normalize_int_list(params.get("bk_biz_ids")),
        "space_uid": _normalize_string_list(params.get("space_uid")),
        "space_uids": _normalize_string_list(params.get("space_uids")),
        "bk_data_id": _normalize_int_list(params.get("bk_data_id")),
        "bk_data_ids": _normalize_int_list(params.get("bk_data_ids")),
        "table_id": _normalize_table_id_list(params.get("table_id")),
        "table_ids": _normalize_table_id_list(params.get("table_ids")),
        "time_series_group_id": _normalize_int_list(params.get("time_series_group_id")),
        "time_series_group_ids": _normalize_int_list(params.get("time_series_group_ids")),
    }


def _query_tenant_ids(field_name: str, values: list[Any]) -> set[str]:
    if field_name in {"bk_biz_id", "bk_biz_ids"}:
        tenant_ids: set[str] = set()
        for value in values:
            try:
                tenant_ids.add(bk_biz_id_to_bk_tenant_id(int(value)))
            except (TypeError, ValueError) as error:
                raise CustomException(message=f"无法根据 {field_name}={value} 反查 bk_tenant_id: {error}") from error
        return tenant_ids

    if field_name in {"space_uid", "space_uids"}:
        query = Q()
        has_condition = False
        for value in values:
            try:
                space_type_id, space_id = str(value).split("__", 1)
            except ValueError:
                continue
            if not space_type_id or not space_id:
                continue
            query |= Q(space_type_id=space_type_id, space_id=space_id)
            has_condition = True

        if not has_condition:
            return set()

        return set(models.Space.objects.filter(query).values_list("bk_tenant_id", flat=True).distinct())

    if field_name in {"bk_data_id", "bk_data_ids"}:
        return set(
            models.DataSource.objects.filter(bk_data_id__in=values).values_list("bk_tenant_id", flat=True).distinct()
        )

    if field_name in {"table_id", "table_ids"}:
        query_values = {str(value).strip() for value in values if str(value).strip()}
        query_values.update(reformat_table_id(value) for value in list(query_values))
        return set(
            models.ResultTable.objects.filter(table_id__in=sorted(query_values))
            .values_list("bk_tenant_id", flat=True)
            .distinct()
        )

    if field_name in {"time_series_group_id", "time_series_group_ids"}:
        return set(
            models.TimeSeriesGroup.objects.filter(time_series_group_id__in=values)
            .values_list("bk_tenant_id", flat=True)
            .distinct()
        )

    return set()


def _normalize_int_list(value: Any) -> list[int]:
    if value is None or value == "":
        return []

    raw_values = value if isinstance(value, list | tuple | set) else [value]
    normalized_values: list[int] = []
    for item in raw_values:
        if item is None or item == "":
            continue
        try:
            normalized_values.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalized_values


def _normalize_table_id_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []

    raw_values = value if isinstance(value, list | tuple | set) else [value]
    normalized_values: list[str] = []
    for item in raw_values:
        table_id = str(item or "").strip()
        if not table_id:
            continue
        normalized_values.append(table_id)
    return normalized_values


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []

    raw_values = value if isinstance(value, list | tuple | set) else [value]
    normalized_values: list[str] = []
    for item in raw_values:
        normalized_item = str(item or "").strip()
        if not normalized_item:
            continue
        normalized_values.append(normalized_item)
    return normalized_values
