"""Subprocess probe: run the same SQLite ORM scenario under each real SDK."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from django.conf import settings
from bkcrypto.constants import SymmetricMode
from bkcrypto.contrib.django.init_configs import SymmetricKeyConfig

import importlib.util
import os

case = json.loads(sys.stdin.read())
alias = case.get("alias", "default")


def legacy_key(cipher_type):
    return SymmetricKeyConfig(key=case["crypto_key"] or case["app_secret"])


configuration = dict(
    SECRET_KEY=case["app_secret"],
    BKPAAS_BK_CRYPTO_KEY=case["crypto_key"],
    INSTALLED_APPS=[],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": case["db"]}},
    BKCRYPTO={
        "SYMMETRIC_CIPHER_TYPE": case["cipher"],
        "SYMMETRIC_CIPHERS": {
            alias: {
                "get_key_config": "__main__.legacy_key"
                if case["legacy"]
                else "apps.utils.aes.get_default_symmetric_key_config",
                "common": {
                    "key_size": case["key_size"],
                    "mode": SymmetricMode(case["mode"]),
                    "encoding": case.get("encoding", "utf-8"),
                },
            }
        },
    },
)
aes_class = case.get("aes_class")
if aes_class is not None:
    if aes_class == "class":
        from bkcrypto.symmetric.ciphers.aes import AESSymmetricCipher

        aes_class = "bkcrypto.symmetric.ciphers.AESSymmetricCipher" if case["legacy"] else AESSymmetricCipher
    configuration["BKCRYPTO"]["SYMMETRIC_CIPHER_CLASSES"] = {
        "AES": aes_class,
        "SM4": "bkcrypto.symmetric.ciphers.SM4SymmetricCipher",
    }
if not case["legacy"]:
    # Exercise the real final configuration stage with omitted or explicit
    # cipher classes, as supplied by environment/local settings overlays.
    path = Path(__file__).resolve().parents[2] / "config/kms.py"
    spec = importlib.util.spec_from_file_location("crypto_kms_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    kms_enabled = case.get("kms_enabled", False)
    os.environ["ENABLE_KMS"] = "true" if kms_enabled else "false"
    if kms_enabled:
        # Prove the envelope is actually consumed, rather than accidentally
        # retaining the same values supplied by the disabled configuration.
        configuration.update(SECRET_KEY="stale-overlay-secret", BKPAAS_BK_CRYPTO_KEY="stale-overlay-key")
        configuration["BROKER_URL"] = "amqp://localhost//"
    module.apply_settings(configuration)
    assert configuration["SECRET_KEY"] == case["app_secret"]
    assert configuration["BKPAAS_BK_CRYPTO_KEY"] == case["crypto_key"]
settings.configure(**configuration)
# Keep a deliberately different default alias, so archive must use its own options.
if alias != "default":
    settings.BKCRYPTO["SYMMETRIC_CIPHERS"]["default"] = {"get_key_config": "__main__.legacy_key"}
import django

django.setup()
from django.db import connection, models
from bkcrypto.contrib.django.fields import SymmetricTextField

basecrypt = case.get("consumer") == "basecrypt"
if basecrypt:
    from apps.utils.base_crypt import BaseCrypt


def stored_value(plaintext):
    return BaseCrypt().encrypt(plaintext.encode("utf-8")) if basecrypt else plaintext


class Credential(models.Model):
    value = models.TextField() if basecrypt else SymmetricTextField(using=alias)

    class Meta:
        app_label = "kms_probe"


if case["operation"] == "write":
    with connection.schema_editor() as editor:
        editor.create_model(Credential)
    Credential.objects.create(value=stored_value(case["plaintext"]))
else:
    actual = Credential.objects.get(pk=1).value
    if basecrypt:
        actual = BaseCrypt().decrypt(actual)
    assert actual == case["plaintext"], "ORM did not return the original plaintext"
    if case["operation"] != "read_only":
        Credential.objects.filter(pk=1).update(value=stored_value(case.get("replacement", case["plaintext"])))
with connection.cursor() as cursor:
    cursor.execute("SELECT value FROM kms_probe_credential")
    raw = cursor.fetchone()[0]
assert raw != case["plaintext"]
if not basecrypt:
    assert raw.startswith(case["cipher"].lower() + "_str:::")
print("OK")
