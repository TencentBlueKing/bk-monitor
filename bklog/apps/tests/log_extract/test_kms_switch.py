"""Verify real envelope switching through ORM reads and writes across restarts."""

import base64
import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.tests.log_extract.kms_helpers import PAYLOAD, envelope

BKLOG_ROOT = Path(__file__).resolve().parents[3]
WORKER = BKLOG_ROOT / "tests/kms/crypto_worker.py"


class KMSSwitchTest(unittest.TestCase):
    def test_same_key_switch_preserves_stored_credentials(self):
        # CI exercises off/on/off on the installed SDK. Local compatibility
        # runs additionally write/read with an isolated, real SDK 2.x runtime.
        legacy_python = os.getenv("BKLOG_CRYPTO2_PYTHON")
        baseline_python = legacy_python or sys.executable
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        for cipher in ("AES", "SM4"):
            for crypto_key in ("", "密钥-keep-same-" * 8):
                with (
                    self.subTest(cipher=cipher, explicit_key=bool(crypto_key)),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    payload = copy.deepcopy(PAYLOAD)
                    payload["encryption"]["bk_crypto_key"] = crypto_key
                    (root / "envelope").write_text(envelope(json.dumps(payload), private_key), encoding="utf-8")
                    (root / "private-key").write_text(base64.b64encode(pem).decode(), encoding="utf-8")
                    # Isolate business credentials, but retain the interpreter's
                    # loader paths (actions/setup-python needs LD_LIBRARY_PATH).
                    env = {
                        **{
                            name: os.environ[name]
                            for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH")
                            if name in os.environ
                        },
                        "PATH": os.environ.get("PATH", os.defpath),
                        "PYTHONDONTWRITEBYTECODE": "1",
                        "BKPAAS_APP_ID": payload["bkapp_id_secret"]["default"]["app_code"],
                        "KMS_ENVELOPE_FILE": str(root / "envelope"),
                        "KMS_PRIVATE_KEY_FILE": str(root / "private-key"),
                    }
                    case = {
                        "db": str(root / "credentials.sqlite"),
                        "app_secret": payload["bkapp_id_secret"]["default"]["app_secret"],
                        "crypto_key": crypto_key,
                        "cipher": cipher,
                        "mode": "CTR",
                        "key_size": 16,
                        "encoding": "utf-8",
                    }
                    initial = "historical credential 密钥 @/%"
                    enabled_write = "written with KMS enabled 开启"
                    disabled_write = "written after KMS disabled 关闭"
                    phases = [
                        (baseline_python, bool(legacy_python), False, "write", initial, None),
                        (sys.executable, False, False, "read_only", initial, None),
                        (sys.executable, False, True, "read_only", initial, None),
                        (sys.executable, False, True, "read", initial, enabled_write),
                        (sys.executable, False, False, "read_only", enabled_write, None),
                        (sys.executable, False, False, "read", enabled_write, disabled_write),
                        (baseline_python, bool(legacy_python), False, "read_only", disabled_write, None),
                    ]
                    for index, (python, legacy, enabled, operation, plaintext, replacement) in enumerate(phases):
                        before = self._ciphertext(case["db"]) if index else None
                        data = dict(case, legacy=legacy, kms_enabled=enabled, operation=operation, plaintext=plaintext)
                        if replacement is not None:
                            data["replacement"] = replacement
                        result = subprocess.run(
                            [python, str(WORKER)],
                            input=json.dumps(data),
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        self.assertEqual(result.returncode, 0, f"phase {index}: {result.stderr}")
                        self.assertEqual(result.stdout.strip(), "OK")
                        if operation == "read_only":
                            self.assertEqual(self._ciphertext(case["db"]), before, "Startup/read rewrote ciphertext")

    @staticmethod
    def _ciphertext(database):
        with sqlite3.connect(database) as connection:
            return connection.execute("SELECT value FROM kms_probe_credential").fetchone()[0]
