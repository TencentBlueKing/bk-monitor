"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Synthetic startup credentials, real RSA/AES envelopes and clean subprocess environments for KMS tests.
"""

import base64
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BKMONITOR_DIR = Path(__file__).resolve().parents[2]
BASE_SRC_DIR = BKMONITOR_DIR.parent / "bk-monitor-base" / "src"

PAYLOAD = {
    "bkapp_id_secret": {
        "saas": {"app_code": "bk_monitorv3", "app_secret": "saas-secret-" * 3},
        "backend": {"app_code": "bk_bkmonitorv3", "app_secret": "backend-secret-" * 3},
        "base_config": {"app_code": "bk_monitorv3", "app_secret": "base-secret-" * 3},
    },
    "mysql": {
        "saas": {"username": "saas-db-user", "password": "saas-db-pass"},
        "backend": {"username": "backend-db-user", "password": "backend-db-pass"},
    },
    "redis": {"monitor": {"password": "redis-pass"}, "bkbase": {"password": "bkbase-redis-pass"}},
    "redis_sentinel": {"monitor": {"password": "sentinel-pass"}},
    "rabbitmq": {
        "saas": {"username": "saas-mq-user", "password": "saas-mq-pass"},
        "backend": {"username": "backend-mq-user", "password": "backend-mq-pass"},
    },
    "elasticsearch": {
        "backend": {"username": "es-backend-user", "password": "es-backend-pass"},
        "fta": {"username": "es-fta-user", "password": "es-fta-pass"},
    },
    "influxdb": {"default": {"username": "influx-user", "password": "influx-pass"}},
    "bkrepo": {"default": {"username": "repo-user", "password": "repo-pass"}},
    "bcs": {"default": {"token": "bcs-token"}},
    "gse": {"default": {"slot_token": "gse-slot-token"}},
    "encryption": {"symmetric_key": "", "custom_report_aes_key": "custom-report-key"},
    "consul": {"default": {"token": "consul-token", "tls_private_key_base64": ""}},
}


def payload(**overrides):
    """Deep-copied payload; overrides use dotted paths such as ``bcs.default.token``."""
    data = copy.deepcopy(PAYLOAD)
    for path, value in overrides.items():
        *parents, leaf = path.split(".")
        node = data
        for part in parents:
            node = node[part]
        if value is None:
            node.pop(leaf)
        else:
            node[leaf] = value
    return data


def new_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def private_key_text(key):
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return base64.b64encode(pem).decode()


def envelope(text, key):
    data_key, iv = os.urandom(16), os.urandom(16)
    encryptor = Cipher(algorithms.AES(data_key), modes.CTR(iv)).encryptor()
    encrypted_key = key.public_key().encrypt(
        data_key, rsa_padding.OAEP(mgf=rsa_padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )

    def encode(value):
        return base64.b64encode(value).decode()

    body = {
        "asymmetric_type": "RSA",
        "symmetric_type": "AES",
        "symmetric_mode": "CTR",
        "encrypted_key": encode(encrypted_key),
        "ciphertext": encode(iv + encryptor.update(text.encode()) + encryptor.finalize()),
    }
    return encode(json.dumps(body).encode())


def write_kms_files(directory, data, key=None, envelope_key=None):
    """Write envelope/private-key files; ``envelope_key`` lets a test pair them with a different key."""
    key = key or new_private_key()
    directory = Path(directory)
    text = data if isinstance(data, str) else json.dumps(data)
    (directory / "envelope").write_text(envelope(text, envelope_key or key))
    (directory / "private-key").write_text(private_key_text(key))
    return {
        "ENABLE_KMS": "true",
        "KMS_ENVELOPE_FILE": str(directory / "envelope"),
        "KMS_PRIVATE_KEY_FILE": str(directory / "private-key"),
    }


def base_env(tmp_path, role="web", **extra):
    """A clean environment carrying only non-secret deployment settings."""
    config_yaml = Path(tmp_path) / "base-config.yaml"
    if not config_yaml.exists():
        config_yaml.write_text("blueking:\n  app_code: bk_monitorv3\n  api_url: http://bkapi.example.com/\n")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(BASE_SRC_DIR),
        "DJANGO_SETTINGS_MODULE": "settings",
        # production loads config.prod like the chart; config.dev hardcodes a local database.
        "DJANGO_CONF_MODULE": f"config.{role}.production.enterprise",
        "BKAPP_DEPLOY_PLATFORM": "enterprise",
        "USE_DYNAMIC_SETTINGS": "0",
        "BK_COMPONENT_API_URL": "http://bkapi.example.com/",
        "BK_PAAS_HOST": "http://paas.example.com",
        "BK_MONITOR_BASE_CONFIG_YAML_FILE": str(config_yaml),
        "BKAPPS_BKMONITOR_LOG_PATH": str(tmp_path),
    }
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run_python(code, env, python=None, cwd=BKMONITOR_DIR, timeout=180):
    return subprocess.run(
        [python or sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def last_json(output):
    """Parse the last JSON line printed by a worker, ignoring settings/logging noise."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON result in output:\n{output}")
