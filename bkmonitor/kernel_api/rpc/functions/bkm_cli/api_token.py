"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from hashlib import sha256
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from bkmonitor.utils.request import get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.admin.common import (
    normalize_optional_bool,
    normalize_pagination,
    paginate_queryset,
)

FUNC_QUERY_API_TOKENS = "bkm_cli.query_api_tokens"
FUNC_MANAGE_API_TOKEN = "bkm_cli.manage_api_token"

QUERY_OPERATIONS = {"capabilities", "list", "detail"}
MUTATION_OPERATIONS = {"grant", "update", "revoke"}
API_MUTABLE_FIELDS = {"allow_all_biz", "biz_ids"}

WORKFLOW_MANAGED_TYPES = {AuthType.AsCode, AuthType.Grafana, AuthType.Entity, AuthType.User}
EXTENDED_SHARE_TYPES = ("rum", "scene_collect", "scene_custom_event", "scene_custom_metric")


def _normalize_text(value: Any, field_name: str, *, required: bool = False, max_length: int | None = None) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise CustomException(message=f"{field_name} 为必填项")
    if max_length is not None and len(text) > max_length:
        raise CustomException(message=f"{field_name} 长度不能超过 {max_length}")
    return text


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    if isinstance(value, bool):
        raise CustomException(message=f"{field_name} 必须是整数")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        digits = text[1:] if text.startswith(("-", "+")) else text
        if digits.isdigit():
            return int(text)
    raise CustomException(message=f"{field_name} 必须是整数")


def _get_bk_tenant_id(params: dict[str, Any], *, required: bool = False) -> str:
    value = _normalize_text(params.get("bk_tenant_id"), "bk_tenant_id", required=required, max_length=64)
    if value:
        return value
    return get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID


def _normalize_business_namespaces(params: dict[str, Any], *, required: bool) -> list[str] | None:
    if params.get("allow_all_biz") is True:
        return ["biz#all"]
    if "biz_ids" not in params:
        if "allow_all_biz" in params or required:
            raise CustomException(message="biz_ids 不能为空，或将 allow_all_biz 设置为 true")
        return None

    value = params.get("biz_ids")
    if isinstance(value, str):
        value = value.replace("\n", ",").split(",")
    if not isinstance(value, list | tuple | set):
        raise CustomException(message="biz_ids 必须是整数列表")

    biz_ids: list[int] = []
    for item in value:
        if item in (None, ""):
            continue
        biz_id = _normalize_int(item, "biz_ids", required=True)
        if biz_id == 0:
            raise CustomException(message="biz_ids 不能包含 0")
        if biz_id not in biz_ids:
            biz_ids.append(biz_id)
    if not biz_ids:
        raise CustomException(message="biz_ids 不能为空，或将 allow_all_biz 设置为 true")
    return [f"biz#{biz_id}" for biz_id in biz_ids]


def _serialize_token(token: ApiAuthToken) -> dict[str, Any]:
    params = token.params if isinstance(token.params, dict) else {}
    app_code = params.get("app_code")
    namespaces = token.namespaces if isinstance(token.namespaces, list) else []
    biz_ids: list[int] = []
    for namespace in namespaces:
        if not isinstance(namespace, str) or not namespace.startswith("biz#"):
            continue
        try:
            biz_ids.append(int(namespace[4:]))
        except ValueError:
            continue

    return {
        "id": token.id,
        "bk_tenant_id": token.bk_tenant_id,
        "name": token.name,
        "type": token.type,
        "namespaces": namespaces,
        "allow_all_biz": "biz#all" in namespaces,
        "biz_ids": biz_ids,
        "app_code": app_code if token.type == AuthType.API and isinstance(app_code, str) else None,
        "params_keys": sorted(str(key) for key in params),
        "credential_present": bool(token.token),
        "expire_time": token.expire_time,
        "is_enabled": token.is_enabled,
        "is_deleted": token.is_deleted,
        "create_user": token.create_user,
        "create_time": token.create_time,
        "update_user": token.update_user,
        "update_time": token.update_time,
    }


def _type_capabilities() -> list[dict[str, Any]]:
    items = []
    for token_type, label in ApiAuthToken.AUTH_TYPE_CHOICES:
        if token_type == AuthType.API:
            owner = "bkm_cli"
            operations = ["list", "detail", "grant", "update", "revoke"]
        elif token_type in WORKFLOW_MANAGED_TYPES:
            owner = "business_workflow"
            operations = ["list", "detail", "revoke"]
        else:
            owner = "share_workflow"
            operations = ["list", "detail", "revoke"]
        items.append({"type": token_type, "label": label, "owner": owner, "operations": operations})
    for token_type in EXTENDED_SHARE_TYPES:
        items.append(
            {
                "type": token_type,
                "label": token_type,
                "owner": "share_workflow",
                "operations": ["list", "detail", "revoke"],
            }
        )
    return items


def _get_token(*, token_id: int, bk_tenant_id: str, for_update: bool = False) -> ApiAuthToken:
    database = ApiAuthToken.objects.db
    queryset = ApiAuthToken.origin_objects.using(database)
    if for_update:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(id=token_id, bk_tenant_id=bk_tenant_id)
    except ApiAuthToken.DoesNotExist as error:
        raise CustomException(message=f"ApiAuthToken 不存在: {token_id}") from error


def _get_api_app_code(token: ApiAuthToken) -> str:
    params = token.params if isinstance(token.params, dict) else {}
    app_code = params.get("app_code")
    if not isinstance(app_code, str) or not app_code.strip():
        raise CustomException(message=f"API Token 记录缺少有效 app_code，不能安全变更: {token.id}")
    return app_code.strip()


def _get_other_active_api_token_ids(token: ApiAuthToken, *, app_code: str, database: str) -> list[int]:
    return list(
        ApiAuthToken.origin_objects.using(database)
        .select_for_update()
        .filter(
            bk_tenant_id=token.bk_tenant_id,
            type=AuthType.API,
            params__app_code=app_code,
            is_deleted=False,
        )
        .exclude(pk=token.pk)
        .values_list("id", flat=True)[:2]
    )


def _raise_on_duplicate_active_api_tokens(token: ApiAuthToken, *, app_code: str, database: str) -> None:
    duplicate_ids = _get_other_active_api_token_ids(token, app_code=app_code, database=database)
    if duplicate_ids:
        raise CustomException(message=f"应用 {app_code} 存在其他有效的 type=api 记录 {duplicate_ids}，请先治理重复记录")


def _default_api_token_name(*, app_code: str, bk_tenant_id: str) -> str:
    suffix = sha256(f"{bk_tenant_id}\0{app_code}".encode()).hexdigest()[:8]
    return f"{app_code[:50]}_{suffix}_api"


@KernelRPCRegistry.register(
    FUNC_QUERY_API_TOKENS,
    summary="查询 API Token 管理记录",
    description="查询 ApiAuthToken 全类型能力、列表或详情；默认 type=api，永不返回原始 token 和完整 params。",
    params_schema={
        "operation": "必填，capabilities/list/detail",
        "bk_tenant_id": "可选，优先显式值，其次请求上下文，最后 system",
        "type": "list 可选，默认 api；all 表示全部类型",
        "id": "detail 必填；list 可选",
        "include_deleted": "list 可选，是否包含已撤回记录",
        "page": "list 可选，默认 1",
        "page_size": "list 可选，默认 20，最大 100",
    },
    example_params={"operation": "list", "bk_tenant_id": "system", "type": "api"},
)
def query_api_tokens(params: dict[str, Any]) -> dict[str, Any]:
    operation = _normalize_text(params.get("operation"), "operation", required=True)
    if operation not in QUERY_OPERATIONS:
        raise CustomException(message=f"operation 仅支持: {sorted(QUERY_OPERATIONS)}")
    if operation == "capabilities":
        return {
            "operation": operation,
            "enforcement_mode": "compatibility",
            "strict_mode": "disabled_by_policy",
            "items": _type_capabilities(),
        }

    bk_tenant_id = _get_bk_tenant_id(params)
    token_id = _normalize_int(params.get("id"), "id", required=operation == "detail")
    if operation == "detail":
        return {
            "operation": operation,
            "token": _serialize_token(_get_token(token_id=token_id, bk_tenant_id=bk_tenant_id)),
        }

    include_deleted = normalize_optional_bool(params.get("include_deleted"), "include_deleted") is True
    database = ApiAuthToken.objects.db
    manager = ApiAuthToken.origin_objects if include_deleted else ApiAuthToken.objects
    queryset = manager.using(database).filter(bk_tenant_id=bk_tenant_id)

    token_type = _normalize_text(params.get("type") or AuthType.API, "type", max_length=32)
    if token_type != "all":
        queryset = queryset.filter(type=token_type)
    if token_id is not None:
        queryset = queryset.filter(id=token_id)
    name = _normalize_text(params.get("name"), "name", max_length=64)
    if name:
        queryset = queryset.filter(name__contains=name)
    app_code = _normalize_text(params.get("app_code"), "app_code", max_length=64)
    if app_code:
        queryset = queryset.filter(params__app_code=app_code)
    namespace = _normalize_text(params.get("namespace"), "namespace", max_length=64)
    if namespace:
        namespace = f"biz#{namespace}" if namespace.lstrip("-").isdigit() else namespace
        queryset = queryset.filter(namespaces__contains=namespace)
    is_enabled = normalize_optional_bool(params.get("is_enabled"), "is_enabled")
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled)

    page, page_size = normalize_pagination(params)
    tokens, total = paginate_queryset(queryset.order_by("-update_time", "id"), page=page, page_size=page_size)
    return {
        "operation": operation,
        "items": [_serialize_token(token) for token in tokens],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _require_mutation_confirmation(params: dict[str, Any]) -> str:
    if "dry_run" in params:
        raise CustomException(message="API Token 管理不支持 dry_run；请先查询现状并取得人工确认")
    if params.get("confirmed") is not True:
        raise CustomException(message="写操作必须先取得人工确认，并传入 confirmed=true")
    return _normalize_text(params.get("operator"), "operator", required=True, max_length=32)


def _grant_api_token(params: dict[str, Any], *, bk_tenant_id: str, operator: str) -> dict[str, Any]:
    token_type = _normalize_text(params.get("type") or AuthType.API, "type", max_length=32)
    if token_type != AuthType.API:
        raise CustomException(message="grant/update 仅支持 type=api；其他类型由既有业务流程创建")
    if "is_enabled" in params or "expire_time" in params:
        raise CustomException(message="type=api 不支持直接设置 is_enabled/expire_time；撤回请使用 revoke")
    if "name" in params:
        raise CustomException(message="type=api 的 name 由租户和 app_code 确定生成，不支持自定义")

    app_code = _normalize_text(params.get("app_code"), "app_code", required=True, max_length=64)
    namespaces = _normalize_business_namespaces(params, required=True)
    name = _default_api_token_name(app_code=app_code, bk_tenant_id=bk_tenant_id)

    database = ApiAuthToken.objects.db
    try:
        with transaction.atomic(using=database):
            exists = (
                ApiAuthToken.origin_objects.using(database)
                .select_for_update()
                .filter(
                    bk_tenant_id=bk_tenant_id,
                    type=AuthType.API,
                    params__app_code=app_code,
                    is_deleted=False,
                )
                .exists()
            )
            if exists:
                raise CustomException(message=f"应用 {app_code} 已存在有效的 type=api 授权，请查询后执行 update")

            token = ApiAuthToken(
                bk_tenant_id=bk_tenant_id,
                name=name,
                type=AuthType.API,
                namespaces=namespaces,
                params={"app_code": app_code},
                is_enabled=True,
            )
            token.save(using=database)
            ApiAuthToken.origin_objects.using(database).filter(pk=token.pk).update(
                create_user=operator,
                update_user=operator,
            )
            token.refresh_from_db(using=database)
    except IntegrityError as error:
        raise CustomException(message="ApiAuthToken 保存失败，name 或 token 可能已存在") from error

    return {"operation": "grant", "changed": True, "token": _serialize_token(token)}


def _update_api_token(params: dict[str, Any], *, bk_tenant_id: str, operator: str) -> dict[str, Any]:
    token_type = _normalize_text(params.get("type") or AuthType.API, "type", max_length=32)
    if token_type != AuthType.API:
        raise CustomException(message="grant/update 仅支持 type=api；其他类型由既有业务流程创建")
    if "is_enabled" in params or "expire_time" in params:
        raise CustomException(message="type=api 不支持直接设置 is_enabled/expire_time；撤回请使用 revoke")
    if "app_code" in params:
        raise CustomException(message="app_code 创建后不可变；如需治理新应用，请新建独立授权记录")
    if "name" in params:
        raise CustomException(message="type=api 的 name 是并发唯一性保护键，创建后不可变")
    if not API_MUTABLE_FIELDS.intersection(params):
        raise CustomException(message=f"update 至少需要一个变更字段: {sorted(API_MUTABLE_FIELDS)}")

    token_id = _normalize_int(params.get("id"), "id", required=True)
    database = ApiAuthToken.objects.db
    try:
        with transaction.atomic(using=database):
            token = _get_token(token_id=token_id, bk_tenant_id=bk_tenant_id, for_update=True)
            if token.type != AuthType.API:
                raise CustomException(message=f"grant/update 仅支持 type=api，当前记录类型为 {token.type}")
            if token.is_deleted:
                raise CustomException(message=f"ApiAuthToken 已撤回，不能继续更新: {token_id}")
            app_code = _get_api_app_code(token)
            _raise_on_duplicate_active_api_tokens(token, app_code=app_code, database=database)

            namespaces = _normalize_business_namespaces(params, required=False)
            if namespaces is not None:
                token.namespaces = namespaces
                token.is_enabled = True

            token.save(using=database)
            ApiAuthToken.origin_objects.using(database).filter(pk=token.pk).update(update_user=operator)
            token.refresh_from_db(using=database)
    except IntegrityError as error:
        raise CustomException(message="ApiAuthToken 保存失败，name 或 token 可能已存在") from error

    return {"operation": "update", "changed": True, "token": _serialize_token(token)}


def _revoke_api_token(params: dict[str, Any], *, bk_tenant_id: str, operator: str) -> dict[str, Any]:
    token_id = _normalize_int(params.get("id"), "id", required=True)
    database = ApiAuthToken.objects.db
    with transaction.atomic(using=database):
        token = _get_token(token_id=token_id, bk_tenant_id=bk_tenant_id, for_update=True)
        if token.type == AuthType.API:
            app_code = _get_api_app_code(token)
            _raise_on_duplicate_active_api_tokens(token, app_code=app_code, database=database)
            # 兼容模式下，无授权记录的应用会被放行。API 类型撤回时必须保留空范围记录，
            # 否则软删除会把已治理应用重新变成未治理应用，导致撤回失效。
            changed = bool(token.namespaces) or token.is_enabled or token.is_deleted
            values = {
                "namespaces": [],
                "is_deleted": False,
                "is_enabled": False,
                "update_user": operator,
                "update_time": timezone.now(),
            }
        else:
            changed = not token.is_deleted or token.is_enabled
            values = {
                "is_deleted": True,
                "is_enabled": False,
                "update_user": operator,
                "update_time": timezone.now(),
            }
        if changed:
            ApiAuthToken.origin_objects.using(database).filter(pk=token.pk).update(**values)
            token.refresh_from_db(using=database)
    return {"operation": "revoke", "changed": changed, "token": _serialize_token(token)}


@KernelRPCRegistry.register(
    FUNC_MANAGE_API_TOKEN,
    summary="管理 API Token 授权记录",
    description=(
        "执行 grant/update/revoke。写操作必须先由人工确认并传 confirmed=true 和 operator；"
        "grant/update 仅支持 type=api，revoke 支持现存全部类型；"
        "API 类型撤回会保留空业务范围记录以维持兼容模式下的撤回语义；不提供 dry-run。"
    ),
    params_schema={
        "operation": "必填，grant/update/revoke",
        "confirmed": "必填，必须为 true，表示已取得人工确认",
        "operator": "必填，最近更新人",
        "bk_tenant_id": "必填，明确的写入租户 ID",
        "id": "update/revoke 必填，授权记录 ID",
        "type": "grant/update 可选，只允许 api",
        "app_code": "grant 必填；创建后不可变",
        "allow_all_biz": "grant/update 可选，授权全部业务",
        "biz_ids": "grant 必填，或 allow_all_biz=true；update 可选",
    },
    example_params={
        "operation": "grant",
        "confirmed": False,
        "operator": "admin",
        "bk_tenant_id": "system",
        "app_code": "demo-app",
        "biz_ids": [2],
    },
)
def manage_api_token(params: dict[str, Any]) -> dict[str, Any]:
    operation = _normalize_text(params.get("operation"), "operation", required=True)
    if operation not in MUTATION_OPERATIONS:
        raise CustomException(message=f"operation 仅支持: {sorted(MUTATION_OPERATIONS)}")
    operator = _require_mutation_confirmation(params)
    bk_tenant_id = _get_bk_tenant_id(params, required=True)

    if operation == "grant":
        return _grant_api_token(params, bk_tenant_id=bk_tenant_id, operator=operator)
    if operation == "update":
        return _update_api_token(params, bk_tenant_id=bk_tenant_id, operator=operator)
    return _revoke_api_token(params, bk_tenant_id=bk_tenant_id, operator=operator)


BkmCliOpRegistry.register(
    op_id="query-api-tokens",
    func_name=FUNC_QUERY_API_TOKENS,
    summary="查询 API Token 管理记录",
    description="查询 ApiAuthToken 全类型能力、列表或详情，默认聚焦 type=api；不返回原始凭据。",
    capability_level="admin",
    risk_level="readonly",
    requires_confirmation=False,
    audit_tags=["api-token", "admin", "readonly"],
    params_schema={"operation": "capabilities/list/detail", "type": "api/all/具体类型", "id": "detail 必填"},
    example_params={"operation": "list", "type": "api"},
)

BkmCliOpRegistry.register(
    op_id="manage-api-token",
    func_name=FUNC_MANAGE_API_TOKEN,
    summary="授权、变更或撤回 API Token",
    description="API Token 管理写操作；必须先取得人工确认，数据库记录 update_user 作为最近更新人。",
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["api-token", "admin", "mutation", "human-confirmation"],
    params_schema={
        "operation": "grant/update/revoke",
        "confirmed": "boolean，必须为 true",
        "operator": "string，最近更新人",
        "bk_tenant_id": "string，必须显式指定",
    },
    example_params={
        "operation": "grant",
        "confirmed": False,
        "operator": "admin",
        "bk_tenant_id": "system",
        "app_code": "demo-app",
        "biz_ids": [2],
    },
)
