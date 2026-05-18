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

from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_DESTRUCTIVE,
    SAFETY_LEVEL_WRITE,
    build_response,
    get_bk_tenant_id,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
)

FUNC_API_AUTH_TOKEN_LIST = "admin.api_auth_token.list"
FUNC_API_AUTH_TOKEN_DETAIL = "admin.api_auth_token.detail"
FUNC_API_AUTH_TOKEN_CREATE = "admin.api_auth_token.create"
FUNC_API_AUTH_TOKEN_UPDATE = "admin.api_auth_token.update"
FUNC_API_AUTH_TOKEN_DELETE = "admin.api_auth_token.delete"

OPERATION_API_AUTH_TOKEN_LIST = "api_auth_token.list"
OPERATION_API_AUTH_TOKEN_DETAIL = "api_auth_token.detail"
OPERATION_API_AUTH_TOKEN_CREATE = "api_auth_token.create"
OPERATION_API_AUTH_TOKEN_UPDATE = "api_auth_token.update"
OPERATION_API_AUTH_TOKEN_DELETE = "api_auth_token.delete"

ORDERING_FIELDS = {"id", "name", "create_time", "update_time", "expire_time"}
API_AUTH_TOKEN_FIELDS = [
    "id",
    "bk_tenant_id",
    "name",
    "token",
    "namespaces",
    "type",
    "params",
    "expire_time",
    "is_enabled",
    "is_deleted",
    "create_user",
    "create_time",
    "update_user",
    "update_time",
]


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _normalize_text(
    value: Any, field_name: str, *, required: bool = False, max_length: int | None = None
) -> str | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    text = str(value).strip()
    if not text:
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    if max_length is not None and len(text) > max_length:
        raise CustomException(message=f"{field_name} 长度不能超过 {max_length}")
    return text


def _normalize_namespaces(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value.split(",")
        value = parsed_value
    if not isinstance(value, list | tuple | set):
        raise CustomException(message="namespaces 必须是字符串列表")

    namespaces = [str(item).strip() for item in value if str(item).strip()]
    if not namespaces:
        raise CustomException(message="namespaces 不能为空")
    return namespaces


def _normalize_biz_ids(value: Any) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values = value.replace("\n", ",").split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = value
    else:
        raise CustomException(message="biz_ids 必须是整数列表")

    biz_ids: list[int] = []
    for item in raw_values:
        if item in (None, ""):
            continue
        try:
            biz_id = int(item)
        except (TypeError, ValueError) as error:
            raise CustomException(message=f"biz_ids 只能包含整数: {item}") from error
        biz_ids.append(biz_id)
    return biz_ids


def _normalize_authorized_namespaces(params: dict[str, Any], *, current: list[str] | None = None) -> list[str]:
    if params.get("allow_all_biz") is True:
        return ["biz#all"]
    if "biz_ids" in params:
        biz_ids = _normalize_biz_ids(params.get("biz_ids"))
        if not biz_ids:
            raise CustomException(message="biz_ids 不能为空，或启用 allow_all_biz")
        return [f"biz#{bk_biz_id}" for bk_biz_id in biz_ids]
    if "namespaces" in params:
        return _normalize_namespaces(params.get("namespaces"))
    return current or []


def _normalize_params(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise CustomException(message="params 必须是 JSON 对象") from error
    if not isinstance(value, dict):
        raise CustomException(message="params 必须是 JSON 对象")
    return value


def _normalize_expire_time(value: Any):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise CustomException(message="expire_time 必须是日期时间字符串")

    expire_time = parse_datetime(value.strip())
    if expire_time is None:
        raise CustomException(message="expire_time 必须是合法日期时间字符串")
    if timezone.is_naive(expire_time):
        expire_time = timezone.make_aware(expire_time, timezone.get_current_timezone())
    return expire_time


def _serialize_api_auth_token(token: ApiAuthToken) -> dict[str, Any]:
    item = serialize_model(token, API_AUTH_TOKEN_FIELDS)
    params = item["params"] if isinstance(item.get("params"), dict) else {}
    namespaces = item["namespaces"] if isinstance(item.get("namespaces"), list) else []
    biz_ids = []
    for namespace in namespaces:
        if not isinstance(namespace, str) or not namespace.startswith("biz#"):
            continue
        biz_id = namespace[4:]
        try:
            biz_ids.append(int(biz_id))
        except ValueError:
            continue

    item.update(
        {
            "app_code": params.get("app_code"),
            "applicant": item.get("create_user"),
            "allow_all_biz": "biz#all" in namespaces,
            "biz_ids": biz_ids,
        }
    )
    return item


def _build_api_token_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = ApiAuthToken.objects.filter(bk_tenant_id=bk_tenant_id, type=AuthType.API)

    token_id = _normalize_int(params.get("id"), "id")
    if token_id is not None:
        queryset = queryset.filter(id=token_id)
    name = _normalize_text(params.get("name"), "name")
    if name:
        queryset = queryset.filter(name__contains=name)
    namespace = _normalize_text(params.get("namespace"), "namespace")
    if namespace:
        if namespace.isdigit():
            namespace = f"biz#{namespace}"
        queryset = queryset.filter(namespaces__contains=namespace)
    app_code = _normalize_text(params.get("app_code"), "app_code")
    if app_code:
        queryset = queryset.filter(params__app_code=app_code)
    applicant = _normalize_text(params.get("applicant") or params.get("create_user"), "applicant")
    if applicant:
        queryset = queryset.filter(create_user__contains=applicant)
    is_enabled = normalize_optional_bool(params.get("is_enabled"), "is_enabled")
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled)
    return queryset


def _get_api_token_or_raise(params: dict[str, Any], bk_tenant_id: str) -> ApiAuthToken:
    token_id = _normalize_int(params.get("id"), "id", required=True)
    try:
        return ApiAuthToken.objects.get(bk_tenant_id=bk_tenant_id, type=AuthType.API, id=token_id)
    except ApiAuthToken.DoesNotExist as error:
        raise CustomException(message=f"ApiAuthToken 不存在或不是 type=api: {token_id}") from error


def _apply_mutation_payload(token: ApiAuthToken, params: dict[str, Any], *, creating: bool) -> ApiAuthToken:
    app_code = _normalize_text(
        params.get("app_code") or token.params.get("app_code"), "app_code", required=creating, max_length=64
    )
    if creating or "create_user" in params or "applicant" in params:
        token.create_user = _normalize_text(
            params.get("create_user") or params.get("applicant"),
            "applicant",
            required=creating,
            max_length=32,
        )
    if creating or "name" in params or "app_code" in params:
        token.name = _normalize_text(params.get("name"), "name", max_length=64) or f"{app_code}_api"
    if creating or "namespaces" in params or "biz_ids" in params or "allow_all_biz" in params:
        token.namespaces = _normalize_authorized_namespaces(params, current=token.namespaces)
    if creating or "params" in params:
        token.params = _normalize_params(params.get("params"))
    if app_code:
        token.params = {**token.params, "app_code": app_code}
    if "expire_time" in params:
        token.expire_time = _normalize_expire_time(params.get("expire_time"))
    if "is_enabled" in params:
        token.is_enabled = normalize_optional_bool(params.get("is_enabled"), "is_enabled")
    token.type = AuthType.API
    return token


@KernelRPCRegistry.register(
    FUNC_API_AUTH_TOKEN_LIST,
    summary="Admin 查询 type=api 的 ApiAuthToken 列表",
    description="查询 ApiAuthToken 管理列表，只返回 type=api 的记录，支持受控过滤、白名单排序和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "可选，应用授权 ID 精确匹配",
        "name": "可选，授权名称包含匹配",
        "app_code": "可选，按 params.app_code 精确匹配",
        "applicant": "可选，按申请人 create_user 包含匹配",
        "namespace": "可选，namespaces 包含匹配",
        "is_enabled": "可选，是否启用",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "app_code": "demo-app", "page": 1, "page_size": 20},
)
def list_api_auth_tokens(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="-update_time")

    queryset = _build_api_token_queryset(params, bk_tenant_id).order_by(ordering, "id")
    tokens, total = paginate_queryset(queryset, page=page, page_size=page_size)

    return build_response(
        operation=OPERATION_API_AUTH_TOKEN_LIST,
        func_name=FUNC_API_AUTH_TOKEN_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_api_auth_token(token) for token in tokens],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_API_AUTH_TOKEN_DETAIL,
    summary="Admin 查询 type=api 的 ApiAuthToken 详情",
    description="按 ID 查询 ApiAuthToken 详情，后端强制限定 type=api。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，应用授权 ID"},
    example_params={"bk_tenant_id": "system", "id": 1},
)
def get_api_auth_token_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    token = _get_api_token_or_raise(params, bk_tenant_id)

    return build_response(
        operation=OPERATION_API_AUTH_TOKEN_DETAIL,
        func_name=FUNC_API_AUTH_TOKEN_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"token": _serialize_api_auth_token(token)},
    )


@KernelRPCRegistry.register(
    FUNC_API_AUTH_TOKEN_CREATE,
    summary="Admin 新增 type=api 的 ApiAuthToken",
    description=(
        "新增 ApiAuthToken，后端强制写入 type=api；app_code 写入 params.app_code，"
        "name 默认使用 {app_code}_api，create_user 表示实际申请人。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "app_code": "必填，申请授权的应用 app_code",
        "applicant": "必填，实际申请人，会写入 create_user",
        "name": "可选，授权名称，默认 {app_code}_api",
        "allow_all_biz": "可选，是否授权全部业务；true 时 namespaces 固定为 ['biz#all']",
        "biz_ids": "可选，业务 ID 列表；allow_all_biz=false 时必填",
        "params": "可选，额外 JSON 对象，后端会写入 app_code",
        "expire_time": "可选，日期时间字符串",
        "is_enabled": "可选，是否启用",
    },
    example_params={"bk_tenant_id": "system", "app_code": "demo-app", "applicant": "admin", "biz_ids": [2]},
)
def create_api_auth_token(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    token = ApiAuthToken(bk_tenant_id=bk_tenant_id, type=AuthType.API)
    token = _apply_mutation_payload(token, params, creating=True)
    applicant = token.create_user

    try:
        token.save()
        ApiAuthToken.origin_objects.filter(pk=token.pk).update(create_user=applicant)
        token.create_user = applicant
    except IntegrityError as error:
        raise CustomException(message=f"ApiAuthToken 保存失败，name 或 token 可能已存在: {error}") from error

    return build_response(
        operation=OPERATION_API_AUTH_TOKEN_CREATE,
        func_name=FUNC_API_AUTH_TOKEN_CREATE,
        bk_tenant_id=bk_tenant_id,
        data={"token": _serialize_api_auth_token(token)},
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_API_AUTH_TOKEN_UPDATE,
    summary="Admin 变更 type=api 的 ApiAuthToken",
    description="按 ID 变更 ApiAuthToken，后端强制限定 type=api，且不会把记录改成其他类型。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，应用授权 ID",
        "app_code": "可选，申请授权的应用 app_code；变更后会同步 name 默认值和 params.app_code",
        "applicant": "可选，实际申请人，会写入 create_user",
        "name": "可选，授权名称；不传但传 app_code 时默认 {app_code}_api",
        "allow_all_biz": "可选，是否授权全部业务；true 时 namespaces 固定为 ['biz#all']",
        "biz_ids": "可选，业务 ID 列表；allow_all_biz=false 时使用该列表生成 namespaces",
        "params": "可选，额外 JSON 对象，后端会保留 app_code",
        "expire_time": "可选，日期时间字符串，空值表示不过期",
        "is_enabled": "可选，是否启用",
    },
    example_params={"bk_tenant_id": "system", "id": 1, "app_code": "demo-app", "biz_ids": [2, 3]},
)
def update_api_auth_token(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    token = _get_api_token_or_raise(params, bk_tenant_id)
    token = _apply_mutation_payload(token, params, creating=False)

    try:
        token.save()
    except IntegrityError as error:
        raise CustomException(message=f"ApiAuthToken 保存失败，name 或 token 可能已存在: {error}") from error

    return build_response(
        operation=OPERATION_API_AUTH_TOKEN_UPDATE,
        func_name=FUNC_API_AUTH_TOKEN_UPDATE,
        bk_tenant_id=bk_tenant_id,
        data={"token": _serialize_api_auth_token(token)},
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_API_AUTH_TOKEN_DELETE,
    summary="Admin 删除 type=api 的 ApiAuthToken",
    description="按 ID 软删除应用授权记录，后端强制限定 type=api，并同步禁用该授权。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，应用授权 ID",
    },
    example_params={"bk_tenant_id": "system", "id": 1},
)
def delete_api_auth_token(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    token = _get_api_token_or_raise(params, bk_tenant_id)
    token.is_enabled = False
    token.is_deleted = True

    try:
        token.save(update_fields=["is_enabled", "is_deleted", "update_user", "update_time"])
    except IntegrityError as error:
        raise CustomException(message=f"ApiAuthToken 删除失败: {error}") from error

    return build_response(
        operation=OPERATION_API_AUTH_TOKEN_DELETE,
        func_name=FUNC_API_AUTH_TOKEN_DELETE,
        bk_tenant_id=bk_tenant_id,
        data={"token": _serialize_api_auth_token(token)},
        safety_level=SAFETY_LEVEL_DESTRUCTIVE,
    )
