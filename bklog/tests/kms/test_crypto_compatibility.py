"""Run with BKLOG_CRYPTO2_PYTHON pointing to a separate 2.0.0 environment."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).with_name("crypto_worker.py")


@pytest.mark.parametrize(
    "cipher,mode,key_size,crypto_key,encoding,plaintext",
    [
        ("AES", "CTR", 16, "", "utf-8", "旧密文:@/%\\\n arbitrary length"),
        ("AES", "CTR", 16, "密钥-测试值" * 8, "utf-8", "多字节截断"),
        ("AES", "CBC", 24, "explicit-key-" * 8, "utf-8", "0123456789abcdef"),
        ("AES", "CBC", 32, "explicit-key-" * 8, "utf-8", "0123456789abcdef"),
        ("AES", "CBC", 16, "", "utf-8", "0123456789abcdef"),
        ("AES", "CFB", 16, "", "utf-8", "CFB8 compatibility"),
        ("AES", "GCM", 16, "", "utf-8", "GCM with tag"),
        ("AES", "CTR", 16, "clé-" * 8, "latin-1", "latin-key"),
        ("SM4", "CTR", 16, "", "utf-8", "国密互读"),
        ("SM4", "CBC", 16, "", "utf-8", "0123456789abcdef"),
    ],
)
@pytest.mark.parametrize("alias", ["default", "archive"])
def test_two_way_orm(tmp_path, cipher, mode, key_size, crypto_key, encoding, plaintext, alias):
    old_python = os.environ["BKLOG_CRYPTO2_PYTHON"]
    case = dict(
        alias=alias,
        db=str(tmp_path / "orm.sqlite"),
        app_secret="app-secret-kept-exactly-" * 3,
        crypto_key=crypto_key,
        cipher=cipher,
        mode=mode,
        key_size=key_size,
        encoding=encoding,
        plaintext=plaintext,
    )
    for python, legacy, operation in [
        (old_python, True, "write"),
        (sys.executable, False, "read"),
        (old_python, True, "read"),
    ]:
        result = subprocess.run(
            [python, str(WORKER)],
            input=json.dumps(dict(case, legacy=legacy, operation=operation)),
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "OK"
