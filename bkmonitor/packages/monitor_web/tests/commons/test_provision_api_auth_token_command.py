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
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import override_settings

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from constants.common import DEFAULT_TENANT_ID
from monitor_web.commons.token.service import get_or_create_business_token

pytestmark = pytest.mark.django_db(databases="__all__")

CMD = "provision_api_auth_token"
BK_BIZ_ID = 2


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=False)
def test_default_options_create_grafana_token_and_print_raw_token():
    stdout = StringIO()

    call_command(CMD, bk_biz_id=BK_BIZ_ID, stdout=stdout)

    auth_token = ApiAuthToken.objects.get(
        bk_tenant_id=DEFAULT_TENANT_ID,
        type=AuthType.Grafana,
        namespaces__contains=f"biz#{BK_BIZ_ID}",
    )
    assert stdout.getvalue().strip() == auth_token.token
    assert auth_token.name == f"{BK_BIZ_ID}_{AuthType.Grafana}"
    assert auth_token.create_user == "system"
    assert auth_token.expire_time is None


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=False)
def test_repeated_execution_returns_existing_token():
    first_stdout = StringIO()
    second_stdout = StringIO()

    call_command(CMD, bk_biz_id=BK_BIZ_ID, stdout=first_stdout)
    call_command(CMD, bk_biz_id=BK_BIZ_ID, operator="another-user", stdout=second_stdout)

    assert first_stdout.getvalue() == second_stdout.getvalue()
    assert (
        ApiAuthToken.objects.filter(
            bk_tenant_id=DEFAULT_TENANT_ID,
            type=AuthType.Grafana,
            namespaces__contains=f"biz#{BK_BIZ_ID}",
        ).count()
        == 1
    )
    assert ApiAuthToken.objects.get(type=AuthType.Grafana).create_user == "system"


def test_business_token_creation_recovers_from_unique_conflict(mocker):
    namespace = f"biz#{BK_BIZ_ID}"
    competing_token = ApiAuthToken.objects.create(
        name=f"{BK_BIZ_ID}_{AuthType.Grafana}",
        type=AuthType.Grafana,
        namespaces=[namespace],
        bk_tenant_id=DEFAULT_TENANT_ID,
    )
    empty_queryset = ApiAuthToken.objects.none()
    competing_queryset = ApiAuthToken.objects.filter(pk=competing_token.pk)
    mocker.patch.object(ApiAuthToken.objects, "filter", side_effect=[empty_queryset, competing_queryset])
    mocker.patch.object(ApiAuthToken.objects, "create", side_effect=IntegrityError("duplicate token name"))

    auth_token, created = get_or_create_business_token(
        bk_tenant_id=DEFAULT_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        token_type=AuthType.Grafana,
        operator="system",
    )

    assert auth_token.pk == competing_token.pk
    assert created is False


def test_business_token_creation_rolls_back_when_operator_update_fails(mocker):
    mocker.patch("django.db.models.query.QuerySet.update", side_effect=RuntimeError("update failed"))

    with pytest.raises(RuntimeError, match="update failed"):
        get_or_create_business_token(
            bk_tenant_id=DEFAULT_TENANT_ID,
            bk_biz_id=BK_BIZ_ID,
            token_type=AuthType.Grafana,
            operator="system",
        )

    assert not ApiAuthToken.origin_objects.filter(name=f"{BK_BIZ_ID}_{AuthType.Grafana}").exists()


def test_business_token_creation_uses_model_database_transaction(mocker):
    database = ApiAuthToken.objects.db
    atomic = mocker.patch(
        "monitor_web.commons.token.service.transaction.atomic",
        wraps=transaction.atomic,
    )

    get_or_create_business_token(
        bk_tenant_id=DEFAULT_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        token_type=AuthType.Grafana,
        operator="system",
    )

    atomic.assert_called_once_with(using=database)


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=False)
def test_json_output_and_explicit_operator():
    stdout = StringIO()

    call_command(CMD, bk_biz_id=BK_BIZ_ID, operator="operator", output="json", stdout=stdout)

    result = json.loads(stdout.getvalue())
    auth_token = ApiAuthToken.objects.get(token=result["token"])
    assert result == {
        "bk_biz_id": BK_BIZ_ID,
        "bk_tenant_id": DEFAULT_TENANT_ID,
        "created": True,
        "token": auth_token.token,
        "type": AuthType.Grafana,
    }
    assert auth_token.create_user == "operator"


@pytest.mark.parametrize("role", ["web", "worker"])
def test_command_rejects_non_api_role(role):
    with override_settings(ROLE=role), pytest.raises(CommandError, match="api role"):
        call_command(CMD, bk_biz_id=BK_BIZ_ID)


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=False)
def test_command_rejects_unsupported_token_type():
    with pytest.raises(CommandError, match="不支持的 Token 类型"):
        call_command(CMD, bk_biz_id=BK_BIZ_ID, type=AuthType.AsCode)


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=False)
def test_command_rejects_zero_business_id():
    with pytest.raises(CommandError, match="业务 ID 不能为 0"):
        call_command(CMD, bk_biz_id=0)


@override_settings(ROLE="api", ENABLE_MULTI_TENANT_MODE=True)
def test_command_reports_tenant_resolution_error(mocker):
    mocker.patch(
        "monitor_web.management.commands.provision_api_auth_token.bk_biz_id_to_bk_tenant_id",
        side_effect=ValueError("space not found"),
    )

    with pytest.raises(CommandError, match=f"无法确定业务 {BK_BIZ_ID} 所属租户"):
        call_command(CMD, bk_biz_id=BK_BIZ_ID)
