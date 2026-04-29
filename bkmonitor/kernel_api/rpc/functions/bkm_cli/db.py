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

from dataclasses import dataclass, field
from typing import Any

from django.utils.module_loading import import_string

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
ALLOWED_LOOKUPS = {"exact", "in", "contains", "startswith", "endswith", "gte", "lte", "isnull"}
DEFAULT_SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "app_secret",
    "bk_app_secret",
    "access_token",
    "refresh_token",
}


@dataclass
class ModelSpec:
    model_path: str
    fields: set[str] = field(default_factory=set)
    sensitive_fields: set[str] = field(default_factory=set)


ALLOWED_MODEL_SPECS: dict[str, ModelSpec] = {
    "metadata.models.bcs.cluster.BCSClusterInfo": ModelSpec(
        model_path="metadata.models.bcs.cluster.BCSClusterInfo",
        fields={"cluster_id", "bk_biz_id", "status", "bk_tenant_id", "project_id", "created_at", "updated_at"},
    ),
    "metadata.models.space.space.Space": ModelSpec(
        model_path="metadata.models.space.space.Space",
        fields={"space_type_id", "space_id", "space_uid", "space_name", "bk_tenant_id", "is_bcs_valid"},
    ),
    "metadata.models.space.space.SpaceResource": ModelSpec(
        model_path="metadata.models.space.space.SpaceResource",
        fields={"space_type_id", "space_id", "resource_type", "resource_id", "dimension_values", "bk_tenant_id"},
    ),
    "bkmonitor.models.bcs_cluster.BCSCluster": ModelSpec(
        model_path="bkmonitor.models.bcs_cluster.BCSCluster",
        fields={"bk_biz_id", "bcs_cluster_id", "name", "environment", "space_uid", "bk_tenant_id"},
    ),
    "bkmonitor.models.metric_list_cache.MetricListCache": ModelSpec(
        model_path="bkmonitor.models.metric_list_cache.MetricListCache",
        fields={"bk_biz_id", "result_table_id", "metric_field", "metric_field_name", "dimensions", "bk_tenant_id"},
    ),
    "bkmonitor.models.base.ReportItems": ModelSpec(
        model_path="bkmonitor.models.base.ReportItems",
        fields={"id", "name", "bk_biz_id", "frequency", "last_send_time", "is_enabled"},
    ),
    "bkmonitor.models.base.ReportContents": ModelSpec(
        model_path="bkmonitor.models.base.ReportContents",
        fields={"id", "report_id", "content", "create_time", "update_time"},
    ),
    "bkmonitor.models.base.ReportStatus": ModelSpec(
        model_path="bkmonitor.models.base.ReportStatus",
        fields={"id", "report_id", "send_status", "last_send_time", "create_time", "update_time"},
    ),
    "bkmonitor.models.fta.action.ActionInstance": ModelSpec(
        model_path="bkmonitor.models.fta.action.ActionInstance",
        fields={"id", "bk_biz_id", "status", "assignee", "strategy_id", "action_config_id", "create_time"},
        sensitive_fields={"ex_data", "alerts"},
    ),
    "bkmonitor.models.fta.action.ActionInstanceLog": ModelSpec(
        model_path="bkmonitor.models.fta.action.ActionInstanceLog",
        fields={"id", "action_instance_id", "level", "message", "create_time"},
    ),
}


def read_db_model(params: dict[str, Any]) -> dict[str, Any]:
    model_name = str(params.get("model") or "").strip()
    spec = _get_model_spec(model_name)
    model_cls = import_string(spec.model_path)
    limit = _normalize_limit(params.get("limit"))
    normalized_filter = _normalize_filter(params.get("filter") or {}, spec)
    selected_fields = _normalize_selected_fields(params.get("fields"), params.get("exclude_fields"), spec)

    queryset = model_cls.objects.all().filter(**normalized_filter)
    order_by = _normalize_order_by(params.get("order_by") or [], spec)
    if order_by:
        queryset = queryset.order_by(*order_by)

    rows = list(queryset[:limit])
    return {
        "model": model_name,
        "count": len(rows),
        "limit": limit,
        "fields": sorted(selected_fields),
        "items": [_serialize_instance(row, selected_fields) for row in rows],
    }


def _get_model_spec(model_name: str) -> ModelSpec:
    spec = ALLOWED_MODEL_SPECS.get(model_name)
    if spec is None:
        raise CustomException(message=f"模型不在 bkm-cli read-db-model 白名单: {model_name}")
    return spec


def _normalize_limit(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"limit 必须是整数: {value}") from error
    if limit <= 0:
        raise CustomException(message="limit 必须大于 0")
    if limit > MAX_LIMIT:
        raise CustomException(message=f"limit 超过硬上限 {MAX_LIMIT}: {limit}")
    return limit


def _normalize_filter(raw_filter: dict[str, Any], spec: ModelSpec) -> dict[str, Any]:
    if not isinstance(raw_filter, dict):
        raise CustomException(message="filter 必须是对象")

    normalized_filter: dict[str, Any] = {}
    for key, value in raw_filter.items():
        field_name, lookup = _split_lookup(key)
        _validate_field(field_name, spec)
        if lookup not in ALLOWED_LOOKUPS:
            raise CustomException(message=f"不支持的 lookup: {lookup}")
        normalized_key = field_name if lookup == "exact" else f"{field_name}__{lookup}"
        normalized_filter[normalized_key] = value
    return normalized_filter


def _split_lookup(key: str) -> tuple[str, str]:
    parts = str(key or "").split("__")
    if len(parts) == 1:
        return parts[0], "exact"
    return "__".join(parts[:-1]), parts[-1]


def _normalize_selected_fields(raw_fields: Any, raw_exclude_fields: Any, spec: ModelSpec) -> set[str]:
    blocked_fields = DEFAULT_SENSITIVE_FIELDS | spec.sensitive_fields
    selected_fields = set(spec.fields)

    if raw_fields:
        if not isinstance(raw_fields, list):
            raise CustomException(message="fields 必须是数组")
        selected_fields = set(str(field) for field in raw_fields)

    if raw_exclude_fields:
        if not isinstance(raw_exclude_fields, list):
            raise CustomException(message="exclude_fields 必须是数组")
        selected_fields -= {str(field) for field in raw_exclude_fields}

    safe_fields = selected_fields - blocked_fields
    for field_name in safe_fields:
        _validate_field(field_name, spec)

    return safe_fields


def _normalize_order_by(raw_order_by: list[Any], spec: ModelSpec) -> list[str]:
    if not isinstance(raw_order_by, list):
        raise CustomException(message="order_by 必须是数组")

    order_by: list[str] = []
    for raw_field in raw_order_by:
        field = str(raw_field or "").strip()
        if not field:
            continue
        field_name = field[1:] if field.startswith("-") else field
        _validate_field(field_name, spec)
        order_by.append(field)
    return order_by


def _validate_field(field_name: str, spec: ModelSpec) -> None:
    if field_name not in spec.fields:
        raise CustomException(message=f"字段不在 read-db-model 允许列表: {field_name}")


def _serialize_instance(instance: Any, selected_fields: set[str]) -> dict[str, Any]:
    return {field_name: getattr(instance, field_name) for field_name in sorted(selected_fields)}


KernelRPCRegistry.register_function(
    func_name="bkm_cli.read_db_model",
    summary="读取白名单 Django Model 记录",
    description="bkm-cli read-db-model 后端函数，仅允许读取服务端白名单内的 Django Model 字段。",
    handler=read_db_model,
    params_schema={
        "model": "白名单模型路径",
        "filter": "安全 ORM lookup 对象",
        "fields": "可选字段数组，必须在模型字段白名单内",
        "exclude_fields": "可选排除字段数组",
        "order_by": "可选排序字段数组",
        "limit": f"默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
    },
    example_params={
        "model": "metadata.models.space.space.Space",
        "filter": {"space_type_id": "bkcc", "space_id": "2"},
        "fields": ["space_uid", "space_name", "space_id"],
        "limit": 20,
    },
)

BkmCliOpRegistry.register(
    op_id="read-db-model",
    func_name="bkm_cli.read_db_model",
    summary="读取白名单 Django Model 记录",
    description="通过 monitor-api 服务桥读取白名单内的 Django ORM 模型记录。",
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["db", "readonly"],
    params_schema={
        "model": "string",
        "filter": "object",
        "fields": "string[]",
        "exclude_fields": "string[]",
        "order_by": "string[]",
        "limit": "integer",
    },
    example_params={
        "model": "metadata.models.space.space.Space",
        "filter": {"space_type_id": "bkcc", "space_id": "2"},
        "fields": ["space_uid", "space_name", "space_id"],
        "limit": 20,
    },
)
