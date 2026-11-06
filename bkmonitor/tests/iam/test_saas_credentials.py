from types import SimpleNamespace
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.backends.config import build_provider

import json
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from bkmonitor.iam.backends.v4.callback_client import build_callback_client
from bkmonitor.iam.backends.v3.provider import V3PermissionProvider
from bkmonitor.iam.backends.v4.provider import V4PermissionProvider
from config.tools.iam_credentials import get_saas_setting, saas_setting


def _options():
    return {
        "base_url": "https://iam.example.test",
        "credentials": {
            "app_code": saas_setting("SAAS_APP_CODE"),
            "app_secret": saas_setting("SAAS_SECRET_KEY"),
        },
        "system": {
            "id": "monitor",
            "name": "Monitor",
            "name_en": "Monitor",
            "clients": [saas_setting("SAAS_APP_CODE")],
            "provider_config": {"host": "https://monitor.example.test", "auth": "basic"},
        },
        "bk_tenant_id": "system",
    }


@pytest.mark.parametrize("provider_class", (V3PermissionProvider, V4PermissionProvider))
def test_clients_resolve_saas_identity_lazily_and_keep_tenants_separate(provider_class):
    schema = SimpleNamespace(actions={}, resource_types={}, roles={})

    version = "v3" if provider_class is V3PermissionProvider else "v4"
    module = f"bkmonitor.iam.backends.{version}.client"
    client_name = "V3Client" if version == "v3" else "V4Client"
    with patch(f"{module}.{client_name}") as constructor:
        constructor.side_effect = lambda *args, **kwargs: object()
        with override_settings(SAAS_APP_CODE="", SAAS_SECRET_KEY=""):
            with patch("bkmonitor.models.config.GlobalConfig.get", side_effect=AssertionError("eager credential read")):
                provider = build_provider(version, schema=schema, options=_options() if version == "v3" else None)
        constructor.assert_not_called()
        with override_settings(
            APP_CODE="backend-app", SECRET_KEY="backend-secret", SAAS_APP_CODE="saas-app", SAAS_SECRET_KEY="saas-secret"
        ):
            first = provider._get_client("tenant-a")
            assert provider._get_client("tenant-a") is first
            assert provider._get_client("tenant-b") is not first
            default_client = provider._get_client()
        with override_settings(SAAS_APP_CODE="saas-app", SAAS_SECRET_KEY="rotated-secret"):
            assert provider._get_client("tenant-a") is not first
            assert provider._get_client() is not default_client
        assert constructor.call_count == 5
        for index, call in enumerate(constructor.call_args_list):
            expected_secret = "saas-secret" if index < 3 else "rotated-secret"
            code, secret = call.args[:2] if version == "v3" else (call.args[0].app_code, call.args[0].app_secret)
            assert (code, secret) == ("saas-app", expected_secret)
            json.dumps({"app_code": code, "app_secret": secret})


def test_callback_snapshots_saas_credentials_and_refreshes_token_provider(monkeypatch):
    client = build_callback_client("system")
    with override_settings(SAAS_APP_CODE="saas-app", SAAS_SECRET_KEY="saas-secret"):
        first = client.options_loader("system")
        assert (first.app_code, first.app_secret) == ("saas-app", "saas-secret")
    with override_settings(SAAS_APP_CODE="saas-app", SAAS_SECRET_KEY="rotated-secret"):
        second = client.options_loader("system")
        assert first.app_secret == "saas-secret"
        assert second.app_secret == "rotated-secret"


@override_settings(SAAS_APP_CODE="", SAAS_SECRET_KEY="", APP_CODE="backend-app", SECRET_KEY="backend-secret")
def test_migrate_reads_saas_identity_from_global_config_without_dynamic_settings():
    values = {"SAAS_APP_CODE": "saved-saas", "SAAS_SECRET_KEY": "saved-secret"}
    with patch("bkmonitor.models.config.GlobalConfig.get", side_effect=lambda name, *args, **kwargs: values[name]):
        assert get_saas_setting("SAAS_APP_CODE") == "saved-saas"
        assert get_saas_setting("SAAS_SECRET_KEY") == "saved-secret"


@override_settings(SAAS_APP_CODE="", APP_CODE="backend-app")
def test_missing_saas_identity_never_falls_back_to_backend():
    with patch("bkmonitor.models.config.GlobalConfig.get", return_value=""):
        with pytest.raises(ImproperlyConfigured, match="SAAS_APP_CODE"):
            get_saas_setting("SAAS_APP_CODE")


def test_v3_callback_defers_saas_lookup_until_client_is_used():
    from bkmonitor.iam.permission import Permission

    with override_settings(SAAS_APP_CODE="", SAAS_SECRET_KEY=""):
        with patch("bkmonitor.models.config.GlobalConfig.get", side_effect=AssertionError("eager credential read")):
            client = Permission.get_iam_client("tenant-a")
    with override_settings(SAAS_APP_CODE="saas-app", SAAS_SECRET_KEY="saas-secret"):
        with patch("bkmonitor.iam.permission.V3Client") as constructor:
            client.health_check()
    assert constructor.call_args.args[:2] == ("saas-app", "saas-secret")
    assert constructor.call_args.kwargs["bk_tenant_id"] == "tenant-a"
