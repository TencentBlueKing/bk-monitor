"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Full settings assembly per role in a subprocess: envelope values must reach the settings and the client
objects that consume them, and KMS-off must keep the original environment sources.
"""

import pytest

from tests.kms.helpers import PAYLOAD, base_env, last_json, payload, run_python, write_kms_files

PROBE = r"""
import json, sys
import settings as s
from kombu import Connection
from config.celery.config import Config
from bkmonitor.utils.consul import BKConsul
from bk_monitor_base.config import get_config

broker = Connection(Config.broker_url)
dbs = {alias: [db.get("USER"), db.get("PASSWORD")] for alias, db in s.DATABASES.items()}
result = {
    "bk_kms_imported": "bk_kms" in sys.modules,
    "role": s.ROLE,
    "app_code": s.APP_CODE,
    "secret_key": s.SECRET_KEY,
    "backend_app_code": s.BACKEND_APP_CODE,
    "base_app_code": get_config().blueking.app_code,
    "base_app_secret": get_config().blueking.app_secret,
    "databases": dbs,
    "celery_broker": [broker.userid, broker.password],
    "es7_fta": [s.ES7_USER, s.ES7_PASSWORD],
    "es_dsl_auth": list(s.ELASTICSEARCH_DSL["default"]["http_auth"] or []),
    "backend_es7": [s.BACKEND_ES7_HOST, s.BACKEND_ES7_REST_PORT, s.BACKEND_ES7_USER, s.BACKEND_ES7_PASSWORD],
    "influxdb_init": [s.INFLUXDB_INIT_IP_LIST, s.INFLUXDB_INIT_PORT, s.INFLUXDB_INIT_USER, s.INFLUXDB_INIT_PASSWORD],
    "bkrepo": [getattr(s, "BKREPO_USERNAME", None), getattr(s, "BKREPO_PASSWORD", None)],
    "bcs_token": s.BCS_API_GATEWAY_TOKEN,
    "gse_slot_token": s.GSE_SLOT_TOKEN,
    "bk_crypto_key": s.BK_CRYPTO_KEY,
    "custom_report_aes_key": s.CUSTOM_REPORT_AES_KEY,
    "consul_token": BKConsul().token,
}
if s.ROLE in ("worker", "api"):
    result.update(
        rabbitmq=[s.RABBITMQ_USER, s.RABBITMQ_PASS],
        redis=[s.REDIS_PASSWD, s.REDIS_SENTINEL_PASS, s.CACHE_REDIS_PASSWD, s.CACHE_REDIS_SENTINEL_PASS],
        redis_confs={name: getattr(s, name)["password"] for name in ("REDIS_LOG_CONF", "REDIS_CACHE_CONF", "REDIS_CELERY_CONF", "REDIS_SERVICE_CONF")},
        cache_sentinel=s.REDIS_CACHE_CONF["sentinel_password"],
        bkbase_redis=s.BKBASE_REDIS_PASSWORD,
    )
print(json.dumps(result))
"""

DEPLOYMENT = {
    # Non-secret settings that the chart keeps rendering when KMS is enabled.
    "APP_CODE": "bk_monitorv3",
    "BK_MONITOR_APP_CODE": "bk_bkmonitorv3",
    "BK_MONITOR_REDIS_MODE": "standalone",
    "BK_MONITOR_REDIS_HOST": "redis.example",
    "BK_MONITOR_REDIS_PORT": "6379",
    "RABBITMQ_HOST": "mq.example",
    "RABBITMQ_PORT": "5672",
    "RABBITMQ_VHOST": "bk_monitorv3",
    "BK_MONITOR_RABBITMQ_HOST": "mq.example",
    "BK_MONITOR_ES7_HOST": "es.example",
    "BK_MONITOR_ES7_REST_PORT": "9200",
    "BK_INFLUXDB_BKMONITORV3_IP0": "influx-0.example",
    "BK_INFLUXDB_BKMONITORV3_IP1": "influx-1.example",
    "BK_MONITOR_INFLUXDB_PORT": "8086",
    "USE_BKREPO": "true",
    "BKREPO_ENDPOINT_URL": "http://bkrepo.example",
    "BKREPO_PROJECT": "bkmonitor",
    "BKREPO_BUCKET": "bkmonitor",
    "BKAPP_GRAFANA_DB_USER": "grafana-user",
    "BKAPP_GRAFANA_DB_PASSWORD": "grafana-pass",
}


def run_settings(tmp_path, role, data=None, **extra):
    env = base_env(tmp_path, role=role, **DEPLOYMENT)
    if data is not None:
        env.update(write_kms_files(tmp_path, data))
    env.update({k: str(v) for k, v in extra.items()})
    return run_python(PROBE, env)


def probe(tmp_path, role, data=None, **extra):
    completed = run_settings(tmp_path, role, data, **extra)
    assert completed.returncode == 0, completed.stderr[-4000:]
    return last_json(completed.stdout)


@pytest.mark.parametrize("role", ["web", "worker", "api"])
def test_envelope_reaches_settings_and_clients(tmp_path, role):
    result = probe(tmp_path, role, PAYLOAD)
    identity = PAYLOAD["bkapp_id_secret"]["saas" if role == "web" else "backend"]

    assert result["bk_kms_imported"] is True
    assert result["app_code"] == identity["app_code"]
    assert result["secret_key"] == identity["app_secret"]
    assert result["backend_app_code"] == PAYLOAD["bkapp_id_secret"]["backend"]["app_code"]
    assert result["base_app_secret"] == PAYLOAD["bkapp_id_secret"]["base_config"]["app_secret"]

    mysql = PAYLOAD["mysql"]
    databases = result["databases"]
    assert databases["default"] == [mysql["saas"]["username"], mysql["saas"]["password"]]
    assert databases["monitor_api"] == [mysql["backend"]["username"], mysql["backend"]["password"]]
    # settings.py copies these aliases after assembly; they must carry the same credentials.
    assert databases["old_monitor_saas"] == databases["default"]
    assert databases["old_monitor_backend"] == databases["monitor_api"]
    assert databases["backend_alert"] == databases["monitor_api"]
    # Grafana's database account is out of scope and keeps its plaintext source.
    assert databases["bk_dataview"] == ["grafana-user", "grafana-pass"]

    mq = PAYLOAD["rabbitmq"]
    assert result["celery_broker"] == [mq["saas"]["username"], mq["saas"]["password"]]
    es = PAYLOAD["elasticsearch"]
    assert result["es7_fta"] == [es["fta"]["username"], es["fta"]["password"]]
    assert result["es_dsl_auth"] == result["es7_fta"]
    assert result["backend_es7"] == ["es.example", "9200", es["backend"]["username"], es["backend"]["password"]]
    influx = PAYLOAD["influxdb"]["default"]
    assert result["influxdb_init"] == [
        ["influx-0.example", "influx-1.example"],
        "8086",
        influx["username"],
        influx["password"],
    ]
    repo = PAYLOAD["bkrepo"]["default"]
    assert result["bkrepo"] == [repo["username"], repo["password"]]
    assert result["bcs_token"] == PAYLOAD["bcs"]["default"]["token"]
    assert result["gse_slot_token"] == PAYLOAD["gse"]["default"]["slot_token"]
    assert result["bk_crypto_key"] == ""
    assert result["custom_report_aes_key"] == PAYLOAD["encryption"]["custom_report_aes_key"]
    assert result["consul_token"] == PAYLOAD["consul"]["default"]["token"]

    if role in ("worker", "api"):
        redis = PAYLOAD["redis"]["monitor"]["password"]
        sentinel = PAYLOAD["redis_sentinel"]["monitor"]["password"]
        assert result["rabbitmq"] == [mq["backend"]["username"], mq["backend"]["password"]]
        assert result["redis"][:3] == [redis, sentinel, redis]
        assert set(result["redis_confs"].values()) == {redis}
        # Standalone mode: the chart renders no sentinel password variable, so the cache keeps None.
        assert result["cache_sentinel"] is None
        assert result["bkbase_redis"] == PAYLOAD["redis"]["bkbase"]["password"]


def test_sentinel_mode_keeps_cache_sentinel_password(tmp_path):
    result = probe(tmp_path, "worker", PAYLOAD, BK_MONITOR_REDIS_MODE="sentinel")
    assert result["cache_sentinel"] == PAYLOAD["redis_sentinel"]["monitor"]["password"]


def test_symmetric_key_reaches_settings(tmp_path):
    result = probe(tmp_path, "web", payload(**{"encryption.symmetric_key": "explicit-business-key"}))
    assert result["bk_crypto_key"] == "explicit-business-key"


def test_empty_consul_token_leaves_client_without_token(tmp_path):
    result = probe(tmp_path, "worker", payload(**{"consul.default.token": ""}))
    assert result["consul_token"] is None


@pytest.mark.parametrize(
    "name",
    [
        "BK_MONITOR_REDIS_PASSWORD",
        "BK_MONITOR_MYSQL_PASSWORD",
        "RABBITMQ_PASSWORD",
        "BKREPO_PASSWORD",
        "BKAPP_BCS_API_GATEWAY_TOKEN",
        "BKAPP_BK_CRYPTO_KEY",
        "CONSUL_HTTP_TOKEN",
        "BKAPP_SETTINGS_SECRET_KEY",
        "BKAPP_SETTINGS_DATABASES",
    ],
)
def test_plaintext_environment_conflicts_fail_closed(tmp_path, name):
    completed = run_settings(tmp_path, "worker", PAYLOAD, **{name: "plaintext-marker"})
    assert completed.returncode != 0
    assert f"KMS conflicts with plaintext environment field: {name}" in completed.stderr
    # The settings loop prints BKAPP_SETTINGS_* values; the KMS check must fail before it.
    assert "plaintext-marker" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "data, message",
    [
        (payload(**{"mysql.saas.password": None}), "Missing or invalid KMS field: mysql.saas.password"),
        (payload(**{"bcs.default.token": ""}), "Empty required KMS field: bcs.default.token"),
        (payload(**{"bkrepo.default.password": ""}), "Empty required KMS field: bkrepo.default.password"),
        (payload(**{"bkapp_id_secret.backend.app_code": "other_app"}), "bkapp_id_secret.backend.app_code"),
        ("not-json", "Cannot load or decrypt KMS startup credentials"),
    ],
)
def test_invalid_envelope_fails_closed(tmp_path, data, message):
    completed = run_settings(tmp_path, "worker", data)
    assert completed.returncode != 0
    assert message in completed.stderr
    for secret in ("saas-secret-", "backend-secret-", "redis-pass", "saas-db-pass"):
        assert secret not in completed.stdout + completed.stderr


def test_base_config_app_code_mismatch_fails_closed(tmp_path):
    (tmp_path / "base-config.yaml").write_text(
        "blueking:\n  app_code: other_app\n  api_url: http://bkapi.example.com/\n"
    )
    completed = run_settings(tmp_path, "web", PAYLOAD)
    assert completed.returncode != 0
    assert "bkapp_id_secret.base_config.app_code does not match bk-monitor-base config" in completed.stderr


@pytest.mark.parametrize("role", ["web", "worker"])
def test_kms_disabled_keeps_environment_sources(tmp_path, role):
    legacy = {
        "APP_TOKEN": "env-saas-secret",
        "BK_MONITOR_APP_SECRET": "env-backend-secret",
        "BKAPP_SAAS_DB_USER": "env-saas-db-user",
        "BKAPP_SAAS_DB_PASSWORD": "env-saas-db-pass",
        "BK_MONITOR_MYSQL_USER": "env-backend-db-user",
        "BK_MONITOR_MYSQL_PASSWORD": "env-backend-db-pass",
        "BK_MONITOR_REDIS_PASSWORD": "env-redis-pass",
        "RABBITMQ_USER": "env-saas-mq-user",
        "RABBITMQ_PASSWORD": "env-saas-mq-pass",
        "BK_MONITOR_RABBITMQ_USERNAME": "env-backend-mq-user",
        "BK_MONITOR_RABBITMQ_PASSWORD": "env-backend-mq-pass",
        "BK_MONITOR_ES7_USER": "env-es-user",
        "BK_MONITOR_ES7_PASSWORD": "env-es-pass",
        "BKAPP_FTA_ES7_USER": "env-fta-user",
        "BKAPP_FTA_ES7_PASSWORD": "env-fta-pass",
        "BK_MONITOR_INFLUXDB_USER": "env-influx-user",
        "BK_MONITOR_INFLUXDB_PASSWORD": "env-influx-pass",
        "BKREPO_USERNAME": "env-repo-user",
        "BKREPO_PASSWORD": "env-repo-pass",
        "BKAPP_BCS_API_GATEWAY_TOKEN": "env-bcs-token",
        "GSE_SLOT_TOKEN": "env-gse-token",
        "BKAPP_BK_CRYPTO_KEY": "env-crypto-key",
        "CUSTOM_REPORT_AES_KEY": "env-report-key",
        "BKBASE_REDIS_PASSWORD": "env-bkbase-pass",
    }
    result = probe(tmp_path, role, None, **legacy)

    assert result["bk_kms_imported"] is False
    assert result["secret_key"] == ("env-saas-secret" if role == "web" else "env-backend-secret")
    assert result["databases"]["default"] == ["env-saas-db-user", "env-saas-db-pass"]
    assert result["databases"]["monitor_api"] == ["env-backend-db-user", "env-backend-db-pass"]
    assert result["celery_broker"] == ["env-saas-mq-user", "env-saas-mq-pass"]
    assert result["es7_fta"] == ["env-fta-user", "env-fta-pass"]
    assert result["backend_es7"] == ["es.example", "9200", "env-es-user", "env-es-pass"]
    assert result["influxdb_init"][2:] == ["env-influx-user", "env-influx-pass"]
    assert result["bkrepo"] == ["env-repo-user", "env-repo-pass"]
    assert result["bcs_token"] == "env-bcs-token"
    assert result["gse_slot_token"] == "env-gse-token"
    assert result["bk_crypto_key"] == "env-crypto-key"
    assert result["custom_report_aes_key"] == "env-report-key"
    # Without a KMS token python-consul keeps reading CONSUL_HTTP_TOKEN itself.
    assert result["consul_token"] is None
    if role == "worker":
        assert result["rabbitmq"] == ["env-backend-mq-user", "env-backend-mq-pass"]
        assert result["redis"][0] == "env-redis-pass"
        assert result["bkbase_redis"] == "env-bkbase-pass"
