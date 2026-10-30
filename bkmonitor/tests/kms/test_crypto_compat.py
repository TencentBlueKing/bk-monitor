"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Encrypted fields across bkcrypto 2.x/4.x and KMS off/on with the same keys.

Set BKMONITOR_CRYPTO2_PYTHON to an interpreter with bk-crypto-python-sdk 2.x to include the
historical-ciphertext steps; without it only the current SDK steps run.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.kms.helpers import BKMONITOR_DIR, base_env, last_json, payload, write_kms_files

WORKER = str(Path(__file__).with_name("crypto_worker.py"))
CRYPTO2_PYTHON = os.environ.get("BKMONITOR_CRYPTO2_PYTHON")
APP_SECRET = "historical-app-secret-" * 2


def run_worker(tmp_path, args, python=None, kms=None, **env_extra):
    env = base_env(tmp_path, role="web", APP_CODE="bk_monitorv3", **env_extra)
    env["PYTHONPATH"] = os.pathsep.join([str(BKMONITOR_DIR), env["PYTHONPATH"]])
    if kms is not None:
        kms_dir = tmp_path / "kms"
        kms_dir.mkdir(exist_ok=True)
        env.update(write_kms_files(kms_dir, kms))
    else:
        env["APP_TOKEN"] = APP_SECRET
    completed = subprocess.run(
        [python or sys.executable, WORKER, str(tmp_path / "secrets.sqlite3"), *args],
        cwd=BKMONITOR_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    return last_json(completed.stdout)


def kms_payload(symmetric_key=""):
    return payload(
        **{
            "bkapp_id_secret.saas.app_secret": APP_SECRET,
            "encryption.symmetric_key": symmetric_key,
        }
    )


def assert_read(result):
    assert result["rows"] > 0
    assert result["mismatches"] == []
    assert result["ciphertext_unchanged"] is True


KEY_SOURCES = {
    # Key from SECRET_KEY (AES_X_KEY_FIELD of the web role), the default for existing deployments.
    "app_secret": {},
    # SPECIFY_AES_KEY takes precedence over the application secret.
    "specify_aes_key": {"BKAPP_SETTINGS_SPECIFY_AES_KEY": "specified-aes-key"},
}


@pytest.mark.parametrize("cipher", ["AES", "SM4"])
@pytest.mark.parametrize("source", KEY_SOURCES)
def test_historical_ciphertext_survives_upgrade_and_kms_switch(tmp_path, cipher, source):
    extra = {"BKAPP_SYMMETRIC_CIPHER_TYPE": cipher, **KEY_SOURCES[source]}

    if CRYPTO2_PYTHON:
        assert run_worker(tmp_path, ["write", "legacy"], python=CRYPTO2_PYTHON, **extra)["bkcrypto"].startswith("2.")
    else:
        run_worker(tmp_path, ["write", "legacy"], **extra)

    assert_read(run_worker(tmp_path, ["read", "legacy"], **extra))
    assert_read(run_worker(tmp_path, ["read", "legacy"], kms=kms_payload(), **extra))
    run_worker(tmp_path, ["write", "kms"], kms=kms_payload(), **extra)
    assert_read(run_worker(tmp_path, ["read", "kms"], **extra))
    if CRYPTO2_PYTHON:
        assert_read(run_worker(tmp_path, ["read", "kms"], python=CRYPTO2_PYTHON, **extra))
        assert_read(run_worker(tmp_path, ["read", "legacy"], python=CRYPTO2_PYTHON, **extra))


@pytest.mark.parametrize("cipher", ["AES", "SM4"])
def test_symmetric_key_switch_keeps_ciphertext_readable(tmp_path, cipher):
    extra = {"BKAPP_SYMMETRIC_CIPHER_TYPE": cipher}
    run_worker(tmp_path, ["write", "crypto_key"], BKAPP_BK_CRYPTO_KEY="business-key", **extra)
    assert_read(run_worker(tmp_path, ["read", "crypto_key"], kms=kms_payload("business-key"), **extra))
    run_worker(tmp_path, ["write", "crypto_key_kms"], kms=kms_payload("business-key"), **extra)
    assert_read(run_worker(tmp_path, ["read", "crypto_key_kms"], BKAPP_BK_CRYPTO_KEY="business-key", **extra))

    # The configured key is really used: the application-secret key cannot read these rows.
    result = run_worker(tmp_path, ["read", "crypto_key"], **extra)
    assert result["mismatches"] == list(range(result["rows"]))


@pytest.mark.parametrize("cipher", ["AES", "SM4"])
def test_field_copy_and_table_rebuild(tmp_path, cipher):
    result = run_worker(tmp_path, ["fields"], BKAPP_SYMMETRIC_CIPHER_TYPE=cipher)
    assert result == {"ciphertext_preserved": True, "readable": True, "bkcrypto": result["bkcrypto"]}
    if CRYPTO2_PYTHON:
        (tmp_path / "legacy").mkdir()
        legacy = run_worker(tmp_path / "legacy", ["fields"], python=CRYPTO2_PYTHON, BKAPP_SYMMETRIC_CIPHER_TYPE=cipher)
        assert legacy["ciphertext_preserved"] and legacy["readable"]
