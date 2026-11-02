"""Exercise startup credential priority in the normal apps.tests CI suite."""

import base64
import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from celery import Celery
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.tests.log_extract.kms_helpers import PAYLOAD, envelope
from apps.utils.crypto import LEGACY_SYMMETRIC_CIPHER_CLASSES


class KMSPriorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.encrypted = envelope(json.dumps(PAYLOAD), key)
        cls.private_key = base64.b64encode(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        ).decode()

    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "envelope").write_text(self.encrypted)
        (root / "private-key").write_text(self.private_key)
        self.enterContext(
            patch.dict(
                os.environ,
                {
                    "ENABLE_KMS": "true",
                    "APP_ID": "bk_log_search",
                    "KMS_ENVELOPE_FILE": str(root / "envelope"),
                    "KMS_PRIVATE_KEY_FILE": str(root / "private-key"),
                    "RABBITMQ_USER": "old-user",
                    "RABBITMQ_PASSWORD": "old-password",
                    "RABBITMQ_HOST": "rabbit.local",
                    "RABBITMQ_PORT": "5672",
                    "RABBITMQ_VHOST": "bklog",
                },
            )
        )
        for name in ("CELERY_BROKER_URL", "CELERY_BROKER_READ_URL", "CELERY_BROKER_WRITE_URL"):
            os.environ.pop(name, None)
        path = Path(__file__).resolve().parents[3] / "config/kms.py"
        spec = importlib.util.spec_from_file_location("isolated_kms_priority", path)
        self.kms = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.kms)

    def settings(self):
        return {
            "BKCRYPTO": {
                "SYMMETRIC_CIPHER_CLASSES": dict(LEGACY_SYMMETRIC_CIPHER_CLASSES),
                "SYMMETRIC_CIPHERS": {"default": {}},
            },
            "SECRET_KEY": "old-secret",
            "BKPAAS_BK_CRYPTO_KEY": "old-key",
            "DATABASES": {"default": {"USER": "old-user", "PASSWORD": "old-password", "HOST": "mysql.local"}},
            "BROKER_URL": "amqp://old-user:old-password@rabbit.local:5672/bklog",
            "BKREPO_USERNAME": "old-user",
            "BKREPO_PASSWORD": "old-password",
            "BCS_API_GATEWAY_TOKEN": "old-token",
            "CACHES": {
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://:old-password@redis.local:6379/1?password=old-query",
                    "OPTIONS": {"PASSWORD": "old-password"},
                }
            },
        }

    def assert_connection(self, connection, host="rabbit.local", port=5672, vhost="bklog"):
        self.assertEqual(connection.userid, PAYLOAD["rabbitmq"]["default"]["username"])
        self.assertEqual(connection.password, PAYLOAD["rabbitmq"]["default"]["password"])
        self.assertEqual((connection.hostname, connection.port, connection.virtual_host), (host, port, vhost))

    def test_generated_broker_ignores_special_legacy_credentials(self):
        for old in ("old-password", "old#password", "old/password", "old;password", "old?password", "旧:@%\\\n"):
            for vhost in ("bklog", "team/项目;?#%"):
                with self.subTest(old=old, vhost=vhost):
                    os.environ.update(RABBITMQ_USER=old, RABBITMQ_PASSWORD=old, RABBITMQ_VHOST=vhost)
                    data = self.settings()
                    data["BROKER_URL"] = f"amqp://{old}:{old}@rabbit.local:5672/{vhost}"
                    self.kms.apply_settings(data)
                    with Celery("kms-priority", set_as_current=False) as app:
                        app.config_from_object(data)
                        self.assert_connection(app.connection_for_read(), vhost=vhost)
                        self.assert_connection(app.connection_for_write(), vhost=vhost)

    def test_envelope_wins_over_legacy_settings(self):
        from django_redis.pool import ConnectionFactory

        data = self.settings()
        self.kms.apply_settings(data)
        self.assertEqual(data["SECRET_KEY"], PAYLOAD["bkapp_id_secret"]["default"]["app_secret"])
        self.assertEqual(data["BKPAAS_BK_CRYPTO_KEY"], "")
        self.assertEqual(
            data["DATABASES"]["default"], {"USER": "db-user", "PASSWORD": "db-password", "HOST": "mysql.local"}
        )
        self.assertEqual((data["BKREPO_USERNAME"], data["BKREPO_PASSWORD"]), ("repo-user", "repo-password"))
        self.assertEqual(data["BCS_API_GATEWAY_TOKEN"], "bcs-token")
        cache = data["CACHES"]["default"]
        with patch.object(ConnectionFactory, "_pools", {}):
            client = ConnectionFactory(cache["OPTIONS"]).connect(cache["LOCATION"])
            self.assertIsNone(client.connection_pool.connection_kwargs.get("password"))

    def test_celery_environment_authentication_uses_envelope(self):
        for name in ("CELERY_BROKER_URL", "CELERY_BROKER_READ_URL", "CELERY_BROKER_WRITE_URL"):
            with self.subTest(name=name), patch.dict(os.environ):
                os.environ[name] = f"amqp://old:{quote('old#/?;', safe='')}@custom-rabbit:5673/custom-vhost"
                data = self.settings()
                self.kms.apply_settings(data)
                with Celery("kms-priority", set_as_current=False) as app:
                    app.config_from_object(data)
                    for direction, connection in (
                        ("READ", app.connection_for_read()),
                        ("WRITE", app.connection_for_write()),
                    ):
                        if name in ("CELERY_BROKER_URL", f"CELERY_BROKER_{direction}_URL"):
                            self.assert_connection(connection, "custom-rabbit", 5673, "custom-vhost")
                        else:
                            self.assert_connection(connection)

    def test_disabled_preserves_settings_and_environment(self):
        os.environ.update(
            ENABLE_KMS="false",
            KMS_ENVELOPE_FILE="/must/not/read",
            CELERY_BROKER_URL="amqp://legacy:legacy@legacy-rabbit//",
        )
        data = self.settings()
        expected, expected_env = copy.deepcopy(data), dict(os.environ)
        with patch.object(self.kms.Path, "read_text", side_effect=AssertionError("must not read envelope")):
            self.kms.apply_settings(data)
        self.assertEqual(data, expected)
        self.assertEqual(dict(os.environ), expected_env)
