"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

config/kms.py loaded on its own: it must not depend on Django or the config package.
"""

import importlib.util
import json
import os
import sys

import pytest

from config.kms import PROTECTED_ENV
from tests.kms.helpers import BKMONITOR_DIR, PAYLOAD, new_private_key, payload, write_kms_files

SECRETS = ("saas-secret-", "backend-secret-", "saas-db-pass", "redis-pass")
CLEARED_ENV = ("APP_ID", "APP_CODE", "BKPAAS_APP_ID", "BK_MONITOR_APP_CODE", "USE_BKREPO", "BKAPP_USE_BKREPO")


@pytest.fixture
def load_kms(monkeypatch):
    for name in list(os.environ):
        if name.upper().startswith(("ENABLE_KMS", "KMS_", "BKAPP_SETTINGS_")) or name in CLEARED_ENV + PROTECTED_ENV:
            monkeypatch.delenv(name, raising=False)

    def load(**env):
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        spec = importlib.util.spec_from_file_location("kms_under_test", BKMONITOR_DIR / "config" / "kms.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return load


def assert_fails(module, message):
    with pytest.raises(module.KMSConfigurationError) as error:
        module.credentials()
    assert message in str(error.value)
    assert not any(secret in str(error.value) for secret in SECRETS)


def test_disabled_reads_nothing_and_skips_sdk(load_kms, monkeypatch):
    monkeypatch.delitem(sys.modules, "bk_kms", raising=False)
    module = load_kms(KMS_ENVELOPE_FILE="/nonexistent/envelope", KMS_PRIVATE_KEY_FILE="/nonexistent/key")
    assert module.credentials() is None
    assert module.enabled() is False
    assert "bk_kms" not in sys.modules


def test_invalid_switch_value(load_kms):
    assert_fails(load_kms(ENABLE_KMS="yes"), "ENABLE_KMS must be a boolean")


def test_valid_envelope(load_kms, tmp_path):
    module = load_kms(
        **write_kms_files(tmp_path, PAYLOAD), APP_CODE="bk_monitorv3", BK_MONITOR_APP_CODE="bk_bkmonitorv3"
    )
    assert module.value("mysql", "backend", "password") == "backend-db-pass"
    assert module.value("encryption", "custom_report_aes_key") == "custom-report-key"


def test_mismatched_private_key(load_kms, tmp_path):
    files = write_kms_files(tmp_path, PAYLOAD, key=new_private_key(), envelope_key=new_private_key())
    assert_fails(load_kms(**files), "Cannot load or decrypt KMS startup credentials")


def test_missing_file(load_kms, tmp_path):
    files = write_kms_files(tmp_path, PAYLOAD)
    (tmp_path / "private-key").unlink()
    assert_fails(load_kms(**files), "Cannot load or decrypt KMS startup credentials")


def test_payload_must_be_an_object(load_kms, tmp_path):
    assert_fails(load_kms(**write_kms_files(tmp_path, json.dumps(["x"]))), "KMS payload must be a JSON object")


def test_encryption_field_required(load_kms, tmp_path):
    files = write_kms_files(tmp_path, payload(**{"encryption.custom_report_aes_key": None}))
    assert_fails(load_kms(**files), "Missing or invalid KMS field: encryption.custom_report_aes_key")


def test_non_string_field_rejected(load_kms, tmp_path):
    files = write_kms_files(tmp_path, payload(**{"redis.monitor.password": 123}))
    assert_fails(load_kms(**files), "Missing or invalid KMS field: redis.monitor.password")


def test_consul_tls_key_not_supported(load_kms, tmp_path):
    files = write_kms_files(tmp_path, payload(**{"consul.default.tls_private_key_base64": "LS0t"}))
    assert_fails(load_kms(**files), "consul.default.tls_private_key_base64 is not supported yet")


def test_empty_bkrepo_allowed_without_bkrepo(load_kms, tmp_path):
    data = payload(**{"bkrepo.default.username": "", "bkrepo.default.password": ""})
    assert load_kms(**write_kms_files(tmp_path, data)).enabled() is True


def test_empty_optional_credentials_allowed(load_kms, tmp_path):
    data = payload(
        **{
            "redis.monitor.password": "",
            "redis_sentinel.monitor.password": "",
            "elasticsearch.fta.password": "",
            "gse.default.slot_token": "",
            "consul.default.token": "",
        }
    )
    assert load_kms(**write_kms_files(tmp_path, data)).enabled() is True


def test_saas_app_code_must_match_environment(load_kms, tmp_path):
    module = load_kms(**write_kms_files(tmp_path, PAYLOAD), BKPAAS_APP_ID="other_app")
    assert_fails(module, "bkapp_id_secret.saas.app_code does not match the environment")


def test_settings_override_conflict_is_case_insensitive(load_kms, tmp_path):
    module = load_kms(**write_kms_files(tmp_path, PAYLOAD), bkapp_settings_bk_crypto_key="x")
    assert_fails(module, "KMS conflicts with plaintext environment field")
