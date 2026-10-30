"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Load the monitor startup credential envelope (bk_monitor_monitor_runtime_config) once.

This module must stay independent of Django: the config package and config.tools read it
while settings are still being assembled. It never writes os.environ, and a disabled
deployment neither imports the KMS SDK nor reads its files.
"""

import json
import os
from functools import lru_cache
from pathlib import Path


class KMSConfigurationError(RuntimeError):
    """A startup failure whose message carries field names, never secret values."""


SCHEMA = {
    "bkapp_id_secret": {
        "saas": ("app_code", "app_secret"),
        "backend": ("app_code", "app_secret"),
        "base_config": ("app_code", "app_secret"),
    },
    "mysql": {"saas": ("username", "password"), "backend": ("username", "password")},
    "redis": {"monitor": ("password",), "bkbase": ("password",)},
    "redis_sentinel": {"monitor": ("password",)},
    "rabbitmq": {"saas": ("username", "password"), "backend": ("username", "password")},
    "elasticsearch": {"backend": ("username", "password"), "fta": ("username", "password")},
    "influxdb": {"default": ("username", "password")},
    "bkrepo": {"default": ("username", "password")},
    "bcs": {"default": ("token",)},
    "gse": {"default": ("slot_token",)},
    "consul": {"default": ("token", "tls_private_key_base64")},
}
ENCRYPTION_FIELDS = ("symmetric_key", "custom_report_aes_key")

NON_EMPTY = (
    ("bkapp_id_secret", "saas", "app_code"),
    ("bkapp_id_secret", "saas", "app_secret"),
    ("bkapp_id_secret", "backend", "app_code"),
    ("bkapp_id_secret", "backend", "app_secret"),
    ("bkapp_id_secret", "base_config", "app_code"),
    ("bkapp_id_secret", "base_config", "app_secret"),
    ("mysql", "saas", "username"),
    ("mysql", "backend", "username"),
    ("rabbitmq", "saas", "username"),
    ("rabbitmq", "backend", "username"),
    ("bcs", "default", "token"),
)

# Plaintext sources that the config readers would otherwise consume.
PROTECTED_ENV = (
    "APP_TOKEN",
    "APP_SECRET",
    "SECRET_KEY",
    "BKPAAS_APP_SECRET",
    "BK_MONITOR_APP_SECRET",
    "GCS_MYSQL_USER",
    "GCS_MYSQL_PASSWORD",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "DB_USERNAME",
    "DB_PASSWORD",
    "BKAPP_SAAS_DB_USER",
    "BKAPP_SAAS_DB_PASSWORD",
    "BK_PAAS_MYSQL_USER",
    "BK_PAAS_MYSQL_PASSWORD",
    "BK_MONITOR_MYSQL_USER",
    "BK_MONITOR_MYSQL_PASSWORD",
    "BKAPP_BACKEND_DB_USERNAME",
    "BKAPP_BACKEND_DB_PASSWORD",
    "REDIS_PASSWORD",
    "BK_MONITOR_REDIS_PASSWORD",
    "BK_MONITOR_REDIS_SENTINEL_PASSWORD",
    "BKBASE_REDIS_PASSWORD",
    "RABBITMQ_USER",
    "RABBITMQ_PASSWORD",
    "BK_BROKER_URL",
    "BK_MONITOR_RABBITMQ_USERNAME",
    "BK_MONITOR_RABBITMQ_PASSWORD",
    "BK_MONITOR_ES7_USER",
    "BK_MONITOR_ES7_PASSWORD",
    "BKAPP_FTA_ES7_USER",
    "BKAPP_FTA_ES7_PASSWORD",
    "BK_FTA_ES7_USER",
    "BK_FTA_ES7_PASSWORD",
    "BK_MONITOR_INFLUXDB_USER",
    "BK_MONITOR_INFLUXDB_PASSWORD",
    "BK_MONITOR_INFLUXDB_PASS",
    "INFLUXDB_BKMONITORV3_USER",
    "INFLUXDB_BKMONITORV3_PASS",
    "BKREPO_USERNAME",
    "BKREPO_PASSWORD",
    "BKAPP_BKREPO_USERNAME",
    "BKAPP_BKREPO_PASSWORD",
    "BKAPP_BCS_API_GATEWAY_TOKEN",
    "BK_BCS_API_GATEWAY_TOKEN",
    "GSE_SLOT_TOKEN",
    "BKAPP_BK_CRYPTO_KEY",
    "BKAPP_SYMMETRIC_CIPHER_KEY",
    "CUSTOM_REPORT_AES_KEY",
    "CONSUL_HTTP_TOKEN",
)

# settings.py turns BKAPP_SETTINGS_<NAME> into settings and prints the value.
PROTECTED_SETTINGS = (
    "SECRET_KEY",
    "APP_TOKEN",
    "SAAS_SECRET_KEY",
    "DATABASES",
    "CACHES",
    "REDIS_PASSWD",
    "REDIS_SENTINEL_PASS",
    "CACHE_REDIS_PASSWD",
    "CACHE_REDIS_SENTINEL_PASS",
    "REDIS_LOG_CONF",
    "REDIS_CACHE_CONF",
    "REDIS_CELERY_CONF",
    "REDIS_QUEUE_CONF",
    "REDIS_SERVICE_CONF",
    "RABBITMQ_USER",
    "RABBITMQ_PASS",
    "ES7_USER",
    "ES7_PASSWORD",
    "ELASTICSEARCH_DSL",
    "BACKEND_ES7_USER",
    "BACKEND_ES7_PASSWORD",
    "INFLUXDB_INIT_USER",
    "INFLUXDB_INIT_PASSWORD",
    "BKREPO_USERNAME",
    "BKREPO_PASSWORD",
    "STORAGES",
    "BCS_API_GATEWAY_TOKEN",
    "GSE_SLOT_TOKEN",
    "BKBASE_REDIS_PASSWORD",
    "BK_CRYPTO_KEY",
    "CUSTOM_REPORT_AES_KEY",
    "CONSUL_CLIENT_TOKEN",
    "BKCRYPTO",
)


def _validate(result):
    if not isinstance(result, dict):
        raise KMSConfigurationError("KMS payload must be a JSON object")
    for group, aliases in SCHEMA.items():
        for alias, names in aliases.items():
            item = result.get(group, {}).get(alias) if isinstance(result.get(group), dict) else None
            for name in names:
                if not isinstance(item, dict) or not isinstance(item.get(name), str):
                    raise KMSConfigurationError(f"Missing or invalid KMS field: {group}.{alias}.{name}")
    encryption = result.get("encryption")
    for name in ENCRYPTION_FIELDS:
        if not isinstance(encryption, dict) or not isinstance(encryption.get(name), str):
            raise KMSConfigurationError(f"Missing or invalid KMS field: encryption.{name}")
    for group, alias, name in NON_EMPTY:
        if not result[group][alias][name]:
            raise KMSConfigurationError(f"Empty required KMS field: {group}.{alias}.{name}")
    if os.getenv("USE_BKREPO", os.getenv("BKAPP_USE_BKREPO", "")).lower() == "true":
        for name in ("username", "password"):
            if not result["bkrepo"]["default"][name]:
                raise KMSConfigurationError(f"Empty required KMS field: bkrepo.default.{name}")
    if result["consul"]["default"]["tls_private_key_base64"]:
        raise KMSConfigurationError("KMS field consul.default.tls_private_key_base64 is not supported yet")


def _check_conflicts(result):
    for name in PROTECTED_ENV:
        if os.environ.get(name):
            raise KMSConfigurationError(f"KMS conflicts with plaintext environment field: {name}")
    for key in os.environ:
        upper_key = key.upper()
        if upper_key.startswith("BKAPP_SETTINGS_") and upper_key[len("BKAPP_SETTINGS_") :] in PROTECTED_SETTINGS:
            raise KMSConfigurationError(f"KMS conflicts with plaintext environment field: {key}")
    # Application codes are not secrets and stay in the environment; the envelope must match them.
    saas_code = os.getenv("BKPAAS_APP_ID") or os.getenv("APP_ID") or os.getenv("APP_CODE")
    if saas_code and saas_code != result["bkapp_id_secret"]["saas"]["app_code"]:
        raise KMSConfigurationError("KMS bkapp_id_secret.saas.app_code does not match the environment")
    backend_code = os.getenv("BK_MONITOR_APP_CODE")
    if backend_code and backend_code != result["bkapp_id_secret"]["backend"]["app_code"]:
        raise KMSConfigurationError("KMS bkapp_id_secret.backend.app_code does not match BK_MONITOR_APP_CODE")


@lru_cache(maxsize=1)
def credentials():
    flag = os.getenv("ENABLE_KMS", "false").lower()
    if flag in ("false", "0", "off", ""):
        return None
    if flag not in ("true", "1", "on"):
        raise KMSConfigurationError("ENABLE_KMS must be a boolean")
    try:
        from bk_kms import decrypt

        envelope = Path(os.environ["KMS_ENVELOPE_FILE"]).read_text(encoding="utf-8").strip()
        private_key = Path(os.environ["KMS_PRIVATE_KEY_FILE"]).read_text(encoding="utf-8").strip()
        result = json.loads(decrypt(envelope=envelope, private_key=private_key))
    except Exception:
        # Neither SDK exceptions nor JSON errors may echo credential contents.
        raise KMSConfigurationError("Cannot load or decrypt KMS startup credentials") from None
    _validate(result)
    _check_conflicts(result)
    return result


def enabled():
    return credentials() is not None


def value(group, alias, field=None):
    """Return an envelope value; only call after ``enabled()`` is true."""
    data = credentials()
    if group == "encryption":
        return data["encryption"][alias]
    return data[group][alias][field]


def apply_base_config():
    """Give bk-monitor-base the envelope identity instead of a plaintext config.yaml secret."""
    from bk_monitor_base.config import get_config

    blueking = get_config().blueking
    app_code = value("bkapp_id_secret", "base_config", "app_code")
    if "app_code" in blueking.model_fields_set and blueking.app_code != app_code:
        raise KMSConfigurationError("KMS bkapp_id_secret.base_config.app_code does not match bk-monitor-base config")
    blueking.app_code = app_code
    blueking.app_secret = value("bkapp_id_secret", "base_config", "app_secret")
