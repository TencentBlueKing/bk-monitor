"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest
from django.db import transaction

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


def _create_token(*, name: str, token_type: str, app_code: str | None = None) -> ApiAuthToken:
    params = {"app_code": app_code} if app_code else {"private": "value"}
    token = ApiAuthToken.objects.create(
        bk_tenant_id="system",
        name=name,
        type=token_type,
        namespaces=["biz#2"],
        params=params,
    )
    return token


def test_api_token_ops_are_registered():
    query_op = BkmCliOpRegistry.resolve("query-api-tokens")
    manage_op = BkmCliOpRegistry.resolve("manage-api-token")

    assert query_op.func_name == "bkm_cli.query_api_tokens"
    assert query_op.risk_level == "readonly"
    assert query_op.requires_confirmation is False
    assert manage_op.func_name == "bkm_cli.manage_api_token"
    assert manage_op.risk_level == "mutation"
    assert manage_op.requires_confirmation is True
    assert KernelRPCRegistry.get_function_detail(query_op.func_name) is not None
    assert KernelRPCRegistry.get_function_detail(manage_op.func_name) is not None


def test_capabilities_cover_model_types_and_only_api_can_be_granted():
    from kernel_api.rpc.functions.bkm_cli.api_token import query_api_tokens

    result = query_api_tokens({"operation": "capabilities"})
    capabilities = {item["type"]: item for item in result["items"]}

    assert set(capabilities) == {
        *{item[0] for item in ApiAuthToken.AUTH_TYPE_CHOICES},
        "rum",
        "scene_collect",
        "scene_custom_event",
        "scene_custom_metric",
    }
    assert capabilities[AuthType.API]["operations"] == ["list", "detail", "grant", "update", "revoke"]
    assert capabilities[AuthType.Grafana]["operations"] == ["list", "detail", "revoke"]
    assert capabilities[AuthType.User]["operations"] == ["list", "detail", "revoke"]


def test_query_tenant_prefers_explicit_value_then_request_context(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import api_token

    monkeypatch.setattr(api_token, "get_request_tenant_id", lambda peaceful: "request-tenant")

    assert api_token._get_bk_tenant_id({"bk_tenant_id": "explicit-tenant"}) == "explicit-tenant"
    assert api_token._get_bk_tenant_id({}) == "request-tenant"


@pytest.mark.parametrize("value", [7.5, True, "7.5"])
def test_token_id_rejects_fractional_boolean_and_decimal_string(value):
    from kernel_api.rpc.functions.bkm_cli import api_token

    with pytest.raises(CustomException, match="必须是整数"):
        api_token._normalize_int(value, "id", required=True)


@pytest.mark.parametrize("biz_ids", [[1.5], [True], [0]])
def test_business_namespaces_reject_fractional_boolean_and_zero_ids(biz_ids):
    from kernel_api.rpc.functions.bkm_cli import api_token

    with pytest.raises(CustomException, match="biz_ids"):
        api_token._normalize_business_namespaces({"biz_ids": biz_ids}, required=True)


@pytest.mark.django_db(databases="__all__")
def test_query_defaults_to_api_and_never_returns_raw_token_or_params():
    from kernel_api.rpc.functions.bkm_cli.api_token import query_api_tokens

    api_token = _create_token(name="demo-api", token_type=AuthType.API, app_code="demo-app")
    _create_token(name="demo-grafana", token_type=AuthType.Grafana)

    result = query_api_tokens({"bk_tenant_id": "system", "operation": "list"})

    assert result["total"] == 1
    assert result["items"][0]["id"] == api_token.id
    assert result["items"][0]["app_code"] == "demo-app"
    assert "token" not in result["items"][0]
    assert "params" not in result["items"][0]


@pytest.mark.django_db(databases="__all__")
def test_query_all_types_and_revoked_detail_are_supported():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token, query_api_tokens

    api_token = _create_token(name="all-api", token_type=AuthType.API, app_code="all-app")
    grafana_token = _create_token(name="all-grafana", token_type=AuthType.Grafana)

    result = query_api_tokens({"bk_tenant_id": "system", "operation": "list", "type": "all"})
    assert {item["id"] for item in result["items"]} == {api_token.id, grafana_token.id}

    manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "revoke",
            "id": grafana_token.id,
            "operator": "admin",
            "confirmed": True,
        }
    )
    detail = query_api_tokens({"bk_tenant_id": "system", "operation": "detail", "id": grafana_token.id})
    assert detail["token"]["is_deleted"] is True
    assert detail["token"]["is_enabled"] is False
    assert detail["token"]["update_user"] == "admin"


@pytest.mark.parametrize(
    "params",
    [
        {"operation": "grant", "operator": "admin", "app_code": "demo", "biz_ids": [2]},
        {"operation": "grant", "confirmed": True, "app_code": "demo", "biz_ids": [2]},
    ],
)
def test_mutation_requires_confirmation_and_operator(params):
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException):
        manage_api_token({"bk_tenant_id": "system", **params})


def test_mutation_rejects_dry_run():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException, match="不支持 dry_run"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "grant",
                "operator": "admin",
                "confirmed": True,
                "dry_run": True,
                "app_code": "demo",
                "biz_ids": [2],
            }
        )


@pytest.mark.django_db(databases="__all__")
def test_grant_api_token_records_operator_and_uses_model_database(mocker):
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    database = ApiAuthToken.objects.db
    atomic = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.api_token.transaction.atomic",
        wraps=transaction.atomic,
    )

    result = manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "grant",
            "operator": "alice",
            "confirmed": True,
            "app_code": "demo-app",
            "biz_ids": [2, -4779],
        }
    )

    token = ApiAuthToken.objects.get(id=result["token"]["id"])
    assert result["changed"] is True
    assert result["token"]["namespaces"] == ["biz#2", "biz#-4779"]
    assert "token" not in result["token"]
    assert token.type == AuthType.API
    assert token.params == {"app_code": "demo-app"}
    assert token.create_user == "alice"
    assert token.update_user == "alice"
    atomic.assert_called_once_with(using=database)


@pytest.mark.django_db(databases="__all__")
def test_update_api_token_changes_business_scope_and_latest_operator():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    token = _create_token(name="update-api", token_type=AuthType.API, app_code="update-app")
    manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "revoke",
            "id": token.id,
            "operator": "alice",
            "confirmed": True,
        }
    )
    result = manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "update",
            "id": token.id,
            "operator": "bob",
            "confirmed": True,
            "allow_all_biz": True,
        }
    )

    token.refresh_from_db()
    assert result["changed"] is True
    assert token.namespaces == ["biz#all"]
    assert token.is_enabled is True
    assert token.is_deleted is False
    assert token.update_user == "bob"


def test_update_rejects_app_code_change():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException, match="app_code 创建后不可变"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "update",
                "id": 1,
                "operator": "admin",
                "confirmed": True,
                "app_code": "new-app",
            }
        )


@pytest.mark.parametrize("operation", ["grant", "update"])
def test_grant_and_update_reject_custom_name(operation):
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    params = {
        "bk_tenant_id": "system",
        "operation": operation,
        "operator": "admin",
        "confirmed": True,
        "name": "custom-name",
    }
    if operation == "grant":
        params.update({"app_code": "demo-app", "biz_ids": [2]})
    else:
        params.update({"id": 1, "biz_ids": [2]})

    with pytest.raises(CustomException, match="name"):
        manage_api_token(params)


@pytest.mark.django_db(databases="__all__")
def test_revoke_api_token_keeps_empty_scope_record_for_compatibility_mode(monkeypatch):
    from kernel_api.middlewares import authentication
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    token = _create_token(name="revoke-api", token_type=AuthType.API, app_code="revoke-app")
    result = manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "revoke",
            "id": token.id,
            "operator": "carol",
            "confirmed": True,
        }
    )

    token.refresh_from_db()
    assert result["changed"] is True
    assert token.namespaces == []
    assert token.is_deleted is False
    assert token.is_enabled is False
    assert token.update_user == "carol"

    monkeypatch.setattr(authentication, "APP_CODE_TOKENS", {})
    monkeypatch.setattr(authentication, "APP_CODE_UPDATE_TIME", {})
    assert authentication.is_match_api_token(SimpleNamespace(biz_id=2), "system", "revoke-app") is False
    assert authentication.is_match_api_token(SimpleNamespace(biz_id=2), "system", "ungoverned-app") is True
    assert authentication.is_match_api_token(SimpleNamespace(biz_id=None), "system", "revoke-app") is True


@pytest.mark.django_db(databases="__all__")
def test_api_authorization_cache_is_isolated_by_tenant(monkeypatch):
    from kernel_api.middlewares import authentication

    _create_token(name="system-api", token_type=AuthType.API, app_code="shared-app")
    tenant_token = ApiAuthToken.objects.create(
        bk_tenant_id="tencent",
        name="tencent-api",
        type=AuthType.API,
        namespaces=["biz#3"],
        params={"app_code": "shared-app"},
    )

    monkeypatch.setattr(authentication, "APP_CODE_TOKENS", {})
    monkeypatch.setattr(authentication, "APP_CODE_UPDATE_TIME", {})

    assert authentication.is_match_api_token(SimpleNamespace(biz_id=2), "system", "shared-app") is True
    assert (
        authentication.is_match_api_token(SimpleNamespace(biz_id=2), tenant_token.bk_tenant_id, "shared-app") is False
    )
    assert authentication.is_match_api_token(SimpleNamespace(biz_id=3), tenant_token.bk_tenant_id, "shared-app") is True
    assert authentication.is_match_api_token(SimpleNamespace(biz_id=2), "system", "shared-app") is True


@pytest.mark.django_db(databases="__all__")
def test_revoke_deleted_api_token_rejects_another_active_record():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    deleted = _create_token(name="deleted-api", token_type=AuthType.API, app_code="duplicate-app")
    ApiAuthToken.origin_objects.filter(pk=deleted.pk).update(is_deleted=True, is_enabled=False)
    _create_token(name="active-api", token_type=AuthType.API, app_code="duplicate-app")

    with pytest.raises(CustomException, match="其他有效的 type=api 记录"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "revoke",
                "id": deleted.id,
                "operator": "admin",
                "confirmed": True,
            }
        )


@pytest.mark.django_db(databases="__all__")
def test_revoke_deleted_api_token_restores_empty_scope_sentinel_without_conflict():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    token = _create_token(name="deleted-only-api", token_type=AuthType.API, app_code="deleted-only-app")
    ApiAuthToken.origin_objects.filter(pk=token.pk).update(is_deleted=True, is_enabled=False)

    manage_api_token(
        {
            "bk_tenant_id": "system",
            "operation": "revoke",
            "id": token.id,
            "operator": "admin",
            "confirmed": True,
        }
    )

    token.refresh_from_db()
    assert token.is_deleted is False
    assert token.is_enabled is False
    assert token.namespaces == []


@pytest.mark.django_db(databases="__all__")
def test_grant_rejects_duplicate_active_api_app_code():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    _create_token(name="duplicate-api", token_type=AuthType.API, app_code="duplicate-app")

    with pytest.raises(CustomException, match="已存在"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "grant",
                "operator": "admin",
                "confirmed": True,
                "app_code": "duplicate-app",
                "biz_ids": [2],
            }
        )


def test_grant_and_update_reject_non_api_type():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException, match="仅支持 type=api"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "grant",
                "type": AuthType.Grafana,
                "operator": "admin",
                "confirmed": True,
                "app_code": "grafana-app",
                "biz_ids": [2],
            }
        )


def test_mutation_requires_explicit_tenant():
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException, match="bk_tenant_id 为必填项"):
        manage_api_token(
            {
                "operation": "grant",
                "operator": "admin",
                "confirmed": True,
                "app_code": "demo-app",
                "biz_ids": [2],
            }
        )


@pytest.mark.parametrize("field", ["is_enabled", "expire_time"])
def test_grant_rejects_status_and_expiration_fields_not_enforced_by_authentication(field):
    from kernel_api.rpc.functions.bkm_cli.api_token import manage_api_token

    with pytest.raises(CustomException, match="不支持直接设置"):
        manage_api_token(
            {
                "bk_tenant_id": "system",
                "operation": "grant",
                "operator": "admin",
                "confirmed": True,
                "app_code": "demo-app",
                "biz_ids": [2],
                field: False if field == "is_enabled" else "2030-01-01T00:00:00Z",
            }
        )
