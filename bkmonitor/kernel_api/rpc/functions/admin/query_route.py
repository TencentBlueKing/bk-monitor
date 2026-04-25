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
from typing import Any

from django.conf import settings

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id
from metadata import models
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
    SPACE_UID_HYPHEN,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import reformat_table_id
from metadata.utils.redis_tools import RedisTools

FUNC_QUERY_ROUTE_QUERY = "admin.query_route.query"
FUNC_QUERY_ROUTE_REFRESH = "admin.query_route.refresh"
REFRESH_TARGET_SPACE = "space"
REFRESH_TARGET_TABLE = "table"
REFRESH_TARGET_DATA_LABEL = "data_label"
REFRESH_TARGET_VALUES = {REFRESH_TARGET_SPACE, REFRESH_TARGET_TABLE, REFRESH_TARGET_DATA_LABEL}

SUMMARY_FIELDS = [
    "storage_type",
    "storage_id",
    "storage_name",
    "cluster_name",
    "db",
    "measurement",
    "source_type",
    "data_label",
    "bk_data_id",
    "bcs_cluster_id",
    "measurement_type",
]


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    """Normalize comma-separated strings and list-like values into a deduplicated string list."""
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = value
    else:
        raise CustomException(message=f"{field_name} 必须是字符串或列表")

    values: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        for part in str(item).split(","):
            normalized_value = part.strip()
            if not normalized_value or normalized_value in seen:
                continue
            values.append(normalized_value)
            seen.add(normalized_value)
    return values


def _resolve_space_identity(params: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    space_uid = str(params.get("space_uid") or "").strip()
    space_type_id = str(params.get("space_type_id") or "").strip()
    space_id = str(params.get("space_id") or "").strip()

    if space_uid:
        parts = space_uid.split(SPACE_UID_HYPHEN, 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise CustomException(message=f"space_uid 格式非法，应为 space_type_id{SPACE_UID_HYPHEN}space_id")
        uid_space_type_id, uid_space_id = parts
        if space_type_id and space_type_id != uid_space_type_id:
            raise CustomException(message="space_uid 与 space_type_id 不一致")
        if space_id and space_id != uid_space_id:
            raise CustomException(message="space_uid 与 space_id 不一致")
        return space_uid, uid_space_type_id, uid_space_id

    if bool(space_type_id) != bool(space_id):
        raise CustomException(message="space_type_id 与 space_id 必须同时传入")
    if space_type_id and space_id:
        return f"{space_type_id}{SPACE_UID_HYPHEN}{space_id}", space_type_id, space_id
    return None, None, None


def _compose_tenant_field(raw_field: str, bk_tenant_id: str) -> str:
    if settings.ENABLE_MULTI_TENANT_MODE:
        return f"{raw_field}|{bk_tenant_id}"
    return raw_field


def _compose_result_table_field(table_id: str, bk_tenant_id: str) -> tuple[str, str]:
    normalized_table_id = reformat_table_id(table_id)
    return normalized_table_id, _compose_tenant_field(normalized_table_id, bk_tenant_id)


def _loads_json_value(value: Any, *, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else value
    return value


def _format_filter_groups(filters: Any) -> list[dict[str, Any]]:
    """Represent each filter object as one AND group; multiple objects mean OR."""
    if not isinstance(filters, list):
        return []

    groups: list[dict[str, Any]] = []
    for filter_object in filters:
        if not isinstance(filter_object, dict):
            groups.append({"operator": "AND", "conditions": [], "raw": filter_object})
            continue

        conditions = []
        for field_name, value in filter_object.items():
            conditions.append(
                {
                    "field": field_name,
                    "operator": "in" if isinstance(value, list | tuple | set) else "eq",
                    "value": list(value) if isinstance(value, set) else value,
                }
            )
        groups.append({"operator": "AND", "conditions": conditions, "raw": filter_object})
    return groups


def _serialize_space_route(space_uid: str | None, redis_field: str | None) -> dict[str, Any] | None:
    if not space_uid or not redis_field:
        return None

    raw_value = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, redis_field)
    route_data = _loads_json_value(raw_value, default={})
    if not isinstance(route_data, dict):
        route_data = {}

    items = []
    for table_id, route_config in route_data.items():
        route_config = route_config if isinstance(route_config, dict) else {"raw": route_config}
        filters = route_config.get("filters", [])
        items.append(
            {
                "table_id": table_id,
                "filters": filters,
                "filter_groups": _format_filter_groups(filters),
                "raw": route_config,
            }
        )

    return {
        "space_uid": space_uid,
        "redis_hash_key": SPACE_TO_RESULT_TABLE_KEY,
        "redis_field": redis_field,
        "exists": raw_value is not None,
        "total": len(items),
        "items": items,
    }


def _serialize_data_label_routes(data_labels: list[str], bk_tenant_id: str) -> list[dict[str, Any]]:
    redis_fields = [_compose_tenant_field(data_label, bk_tenant_id) for data_label in data_labels]
    raw_values = RedisTools.hmget(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_fields)

    routes = []
    for data_label, redis_field, raw_value in zip(data_labels, redis_fields, raw_values, strict=False):
        table_ids = _loads_json_value(raw_value, default=[])
        if not isinstance(table_ids, list):
            table_ids = []
        routes.append(
            {
                "data_label": data_label,
                "redis_hash_key": DATA_LABEL_TO_RESULT_TABLE_KEY,
                "redis_field": redis_field,
                "exists": raw_value is not None,
                "total": len(table_ids),
                "table_ids": table_ids,
            }
        )
    return routes


def _build_detail_summary(detail: dict[str, Any]) -> dict[str, Any]:
    return {field: detail.get(field) for field in SUMMARY_FIELDS if field in detail}


def _serialize_result_table_details(table_ids: list[str], bk_tenant_id: str) -> list[dict[str, Any]]:
    normalized_pairs = [_compose_result_table_field(table_id, bk_tenant_id) for table_id in table_ids]
    redis_fields = [redis_field for _, redis_field in normalized_pairs]
    raw_values = RedisTools.hmget(RESULT_TABLE_DETAIL_KEY, redis_fields)

    details = []
    for table_id, (normalized_table_id, redis_field), raw_value in zip(
        table_ids, normalized_pairs, raw_values, strict=False
    ):
        detail = _loads_json_value(raw_value, default={})
        if not isinstance(detail, dict):
            detail = {"raw_value": detail}
        fields = detail.get("fields") if isinstance(detail, dict) else []
        fields = fields if isinstance(fields, list) else []
        details.append(
            {
                "table_id": table_id,
                "normalized_table_id": normalized_table_id,
                "redis_hash_key": RESULT_TABLE_DETAIL_KEY,
                "redis_field": redis_field,
                "exists": raw_value is not None,
                "field_count": len(fields),
                "fields": fields,
                "summary": _build_detail_summary(detail),
                "detail": detail,
            }
        )
    return details


def _normalize_query(params: dict[str, Any], bk_tenant_id: str) -> dict[str, Any]:
    space_uid, space_type_id, space_id = _resolve_space_identity(params)
    table_ids = _normalize_string_list(params.get("table_ids"), "table_ids")
    data_label_value = params.get("data_labels")
    if data_label_value in (None, ""):
        data_label_value = params.get("data_label")
    data_labels = _normalize_string_list(data_label_value, "data_labels")
    field_names = _normalize_string_list(params.get("field_names"), "field_names")
    return {
        "bk_tenant_id": bk_tenant_id,
        "space_uid": space_uid,
        "space_type_id": space_type_id,
        "space_id": space_id,
        "table_ids": table_ids,
        "data_labels": data_labels,
        "field_names": field_names,
    }


def _normalize_refresh_targets(params: dict[str, Any], query: dict[str, Any]) -> set[str]:
    targets = set(_normalize_string_list(params.get("refresh_targets"), "refresh_targets"))
    if not targets:
        targets = set()
        if query["space_uid"]:
            targets.add(REFRESH_TARGET_SPACE)
        if query["table_ids"]:
            targets.add(REFRESH_TARGET_TABLE)
            targets.add(REFRESH_TARGET_DATA_LABEL)
        if query["data_labels"]:
            targets.add(REFRESH_TARGET_DATA_LABEL)

    unsupported_targets = targets - REFRESH_TARGET_VALUES
    if unsupported_targets:
        allowed_text = ", ".join(sorted(REFRESH_TARGET_VALUES))
        unsupported_text = ", ".join(sorted(unsupported_targets))
        raise CustomException(message=f"不支持的 refresh_targets: {unsupported_text}，可选值: {allowed_text}")
    if REFRESH_TARGET_SPACE in targets and not query["space_uid"]:
        raise CustomException(message="刷新 space 路由时必须指定 space_uid")
    if REFRESH_TARGET_TABLE in targets and not query["table_ids"]:
        raise CustomException(message="刷新表详情路由时必须指定 table_ids")
    if REFRESH_TARGET_DATA_LABEL in targets and not (query["data_labels"] or query["table_ids"]):
        raise CustomException(message="刷新 data_label 路由时必须指定 data_labels 或 table_ids")
    return targets


@KernelRPCRegistry.register(
    FUNC_QUERY_ROUTE_QUERY,
    summary="Admin 查询 Redis 查询路由",
    description=(
        "诊断 SPACE_TO_RESULT_TABLE、DATA_LABEL_TO_RESULT_TABLE、RESULT_TABLE_DETAIL 三类 Redis 查询路由；"
        "只按明确 field 使用 hget/hmget，不做 hgetall 全量扫描。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "space_uid": "可选，空间 UID，例如 bkcc__2；与 space_type_id + space_id 二选一",
        "space_type_id": "可选，空间类型；需与 space_id 同时传入",
        "space_id": "可选，空间 ID；需与 space_type_id 同时传入",
        "table_ids": "可选，结果表 ID，支持字符串、逗号分隔字符串或列表",
        "data_labels": "可选，数据标签，支持字符串、逗号分隔字符串或列表；兼容 data_label",
        "field_names": "可选，字段名，支持字符串、逗号分隔字符串或列表",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2", "table_ids": "system.cpu"},
)
def query_routes(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    query = _normalize_query(params, bk_tenant_id)

    redis_space_field = _compose_tenant_field(query["space_uid"], bk_tenant_id) if query["space_uid"] else None
    space_route = _serialize_space_route(query["space_uid"], redis_space_field)
    data_label_routes = _serialize_data_label_routes(query["data_labels"], bk_tenant_id)
    result_table_details = _serialize_result_table_details(query["table_ids"], bk_tenant_id)

    return build_response(
        operation="query_route.query",
        func_name=FUNC_QUERY_ROUTE_QUERY,
        bk_tenant_id=bk_tenant_id,
        data={
            "query": query,
            "space_route": space_route,
            "data_label_routes": data_label_routes,
            "result_table_details": result_table_details,
        },
    )


def _get_space_for_refresh(space_type_id: str, space_id: str, bk_tenant_id: str) -> Any:
    space_model = getattr(models, "Space")
    try:
        return space_model.objects.get(space_type_id=space_type_id, space_id=space_id, bk_tenant_id=bk_tenant_id)
    except space_model.DoesNotExist as error:
        raise CustomException(message=f"未找到空间: {space_type_id}{SPACE_UID_HYPHEN}{space_id}") from error


def _mark_refresh_result(
    refresh_results: dict[str, Any], route_name: str, targets: list[str], *, success: bool, error: str | None = None
) -> None:
    refresh_results[route_name] = {
        "targets": targets,
        "success": success,
        "error": error,
    }


@KernelRPCRegistry.register(
    FUNC_QUERY_ROUTE_REFRESH,
    summary="Admin 主动刷新 Redis 查询路由",
    description=(
        "按指定 space_uid、table_ids、data_labels 刷新查询路由并发布变更；刷新时 is_publish=True，"
        "多租户下使用入参 bk_tenant_id 校验目标。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "space_uid": "可选，空间 UID，例如 bkcc__2；与 space_type_id + space_id 二选一",
        "space_type_id": "可选，空间类型；需与 space_id 同时传入",
        "space_id": "可选，空间 ID；需与 space_type_id 同时传入",
        "table_ids": "可选，结果表 ID，支持字符串、逗号分隔字符串或列表",
        "data_labels": "可选，数据标签，支持字符串、逗号分隔字符串或列表；兼容 data_label",
        "refresh_targets": "可选，刷新目标: space / table / data_label；不传时兼容旧行为，按入参自动推断",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2", "table_ids": ["system.cpu"]},
)
def refresh_routes(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    query = _normalize_query(params, bk_tenant_id)
    refresh_targets = _normalize_refresh_targets(params, query)
    table_ids = query["table_ids"]
    data_labels = query["data_labels"]
    if not refresh_targets:
        raise CustomException(message="至少需要指定 space_uid、table_ids 或 data_labels 中的一项")

    refresh_results: dict[str, Any] = {}
    warnings: list[dict[str, Any]] = []
    route_client = SpaceTableIDRedis()

    if REFRESH_TARGET_SPACE in refresh_targets and query["space_uid"]:
        space = _get_space_for_refresh(query["space_type_id"], query["space_id"], bk_tenant_id)
        try:
            route_client.push_space_table_ids(space.space_type_id, space.space_id, is_publish=True)
            _mark_refresh_result(refresh_results, "space_to_result_table", [query["space_uid"]], success=True)
        except Exception as error:  # pylint: disable=broad-except
            _mark_refresh_result(
                refresh_results, "space_to_result_table", [query["space_uid"]], success=False, error=str(error)
            )
            warnings.append({"code": "SPACE_ROUTE_REFRESH_FAILED", "message": str(error)})

    if REFRESH_TARGET_TABLE in refresh_targets and table_ids:
        try:
            route_client.push_table_id_detail(
                table_id_list=table_ids,
                include_es_table_ids=True,
                is_publish=True,
                bk_tenant_id=bk_tenant_id,
            )
            _mark_refresh_result(refresh_results, "result_table_detail", table_ids, success=True)
        except Exception as error:  # pylint: disable=broad-except
            _mark_refresh_result(refresh_results, "result_table_detail", table_ids, success=False, error=str(error))
            warnings.append({"code": "RESULT_TABLE_DETAIL_REFRESH_FAILED", "message": str(error)})

    if REFRESH_TARGET_DATA_LABEL in refresh_targets and (data_labels or table_ids):
        try:
            route_client.push_data_label_table_ids(
                data_label_list=data_labels or None,
                table_id_list=table_ids or None,
                is_publish=True,
                bk_tenant_id=bk_tenant_id,
            )
            _mark_refresh_result(
                refresh_results,
                "data_label_to_result_table",
                data_labels or table_ids,
                success=True,
            )
        except Exception as error:  # pylint: disable=broad-except
            _mark_refresh_result(
                refresh_results,
                "data_label_to_result_table",
                data_labels or table_ids,
                success=False,
                error=str(error),
            )
            warnings.append({"code": "DATA_LABEL_ROUTE_REFRESH_FAILED", "message": str(error)})

    return build_response(
        operation="query_route.refresh",
        func_name=FUNC_QUERY_ROUTE_REFRESH,
        bk_tenant_id=bk_tenant_id,
        data={"query": query, "refresh_results": refresh_results},
        warnings=warnings,
    )
