"""Load the BKLog startup credential envelope once, without changing os.environ.

This module must remain independent of Django/blueapps: application identity is
needed before either framework loads settings. Disabled deployments do not import
the KMS SDK or read its files.
"""

import json
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


class KMSConfigurationError(RuntimeError):
    """A startup failure whose message contains field names, never secret values."""


@lru_cache(maxsize=1)
def credentials():
    enabled = os.getenv("ENABLE_KMS", "false").lower()
    if enabled in ("false", "0", "off", ""):
        return None
    if enabled not in ("true", "1", "on"):
        raise KMSConfigurationError("ENABLE_KMS must be a boolean")
    try:
        from bk_kms import decrypt

        envelope = Path(os.environ["KMS_ENVELOPE_FILE"]).read_text(encoding="utf-8").strip()
        private_key = Path(os.environ["KMS_PRIVATE_KEY_FILE"]).read_text(encoding="utf-8").strip()
        result = json.loads(decrypt(envelope=envelope, private_key=private_key))
    except Exception:
        # Neither SDK exceptions nor JSON errors may print credential contents.
        raise KMSConfigurationError("Cannot load or decrypt KMS startup credentials") from None

    fields = {
        "bkapp_id_secret": ("app_code", "app_secret"),
        "mysql": ("username", "password"),
        "rabbitmq": ("username", "password"),
        "redis": ("password",),
        "bkrepo": ("username", "password"),
        "bcs": ("token",),
        "encryption": ("bk_crypto_key",),
    }
    for group, names in fields.items():
        value = result.get(group) if isinstance(result, dict) else None
        if group != "encryption":
            value = value.get("default") if isinstance(value, dict) else None
        for name in names:
            if not isinstance(value, dict) or not isinstance(value.get(name), str):
                raise KMSConfigurationError(f"Missing or invalid KMS field: {group}.{name}")
    for group, name in (
        ("bkapp_id_secret", "app_code"),
        ("bkapp_id_secret", "app_secret"),
        ("mysql", "username"),
        ("rabbitmq", "username"),
        ("bcs", "token"),
    ):
        if not result[group]["default"][name]:
            raise KMSConfigurationError(f"Empty required KMS field: {group}.{name}")
    # envFrom/extraEnv must not leave an alternative plaintext credential source.
    protected = (
        "APP_TOKEN",
        "BKPAAS_APP_SECRET",
        "DB_USERNAME",
        "DB_PASSWORD",
        "RABBITMQ_USER",
        "RABBITMQ_PASSWORD",
        "CELERY_BROKER_URL",
        "CELERY_BROKER_READ_URL",
        "CELERY_BROKER_WRITE_URL",
        "REDIS_PASSWORD",
        "BKAPP_REDIS_PASSWORD",
        "BK_BKLOG_REDIS_PASSWORD",
        "BKREPO_USERNAME",
        "BKREPO_PASSWORD",
        "BKAPP_BKREPO_USERNAME",
        "BKAPP_BKREPO_PASSWORD",
        "BKAPP_BCS_API_GATEWAY_TOKEN",
        "BKPAAS_BK_CRYPTO_KEY",
    )
    for name in protected:
        if os.environ.get(name):
            raise KMSConfigurationError(f"KMS conflicts with plaintext environment field: {name}")
    expected_app = os.getenv("APP_ID") or os.getenv("BKPAAS_APP_ID")
    if not expected_app or result["bkapp_id_secret"]["default"]["app_code"] != expected_app:
        raise KMSConfigurationError("KMS application identity does not match APP_ID/BKPAAS_APP_ID")
    # Empty Redis/MySQL passwords and an empty optional crypto key are valid
    # values. Missing fields are not equivalent to explicitly empty strings.
    return result


def value(group, field, legacy=None):
    data = credentials()
    if data is None:
        return legacy
    return data[group][field] if group == "encryption" else data[group]["default"][field]


def _broker_credentials(raw, username, password):
    """Replace authentication while preserving Celery URL/failover topology."""
    if isinstance(raw, list | tuple):
        return type(raw)(_broker_credentials(item, username, password) for item in raw)
    if not isinstance(raw, str) or not raw:
        raise ValueError
    if ";" in raw:
        return ";".join(_broker_credentials(item, username, password) for item in raw.split(";"))
    broker = urlsplit(raw)
    if broker.scheme not in ("amqp", "amqps", "pyamqp"):
        raise ValueError
    hostname = broker.hostname or ""
    host = f"[{hostname}]" if ":" in hostname else hostname
    if broker.port is not None:
        host += f":{broker.port}"
    userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}"
    return urlunsplit(broker._replace(netloc=f"{userinfo}@{host}"))


def apply_settings(settings):
    """Apply credentials after environment/local overlays and DB reconstruction."""
    # Environment/local overlays may replace the whole BKCRYPTO dictionary.
    # Restore the project cipher defaults after overlays, including KMS-off,
    # while respecting explicitly configured custom cipher classes.
    if "BKCRYPTO" in settings:
        from apps.utils.crypto import LEGACY_SYMMETRIC_CIPHER_CLASSES, ensure_crypto_field_copy_compatibility

        ensure_crypto_field_copy_compatibility()
        cipher_classes = settings["BKCRYPTO"].setdefault(
            "SYMMETRIC_CIPHER_CLASSES", dict(LEGACY_SYMMETRIC_CIPHER_CLASSES)
        )
        if isinstance(cipher_classes, Mapping):
            from bkcrypto.symmetric.ciphers.aes import AESSymmetricCipher

            aes_class = cipher_classes.get("AES")
            # Explicit SDK defaults need the same historical key handling as
            # omitted defaults. Preserve real custom classes without importing
            # their modules early, and avoid mutating an overlay's shared map.
            if aes_class is AESSymmetricCipher or (
                isinstance(aes_class, str)
                and aes_class
                in (
                    "bkcrypto.symmetric.ciphers.AESSymmetricCipher",
                    "bkcrypto.symmetric.ciphers.aes.AESSymmetricCipher",
                )
            ):
                settings["BKCRYPTO"]["SYMMETRIC_CIPHER_CLASSES"] = {
                    **cipher_classes,
                    "AES": LEGACY_SYMMETRIC_CIPHER_CLASSES["AES"],
                }
    data = credentials()
    if data is None:
        return
    settings.update(
        APP_CODE=value("bkapp_id_secret", "app_code"),
        APP_ID=value("bkapp_id_secret", "app_code"),
        SECRET_KEY=value("bkapp_id_secret", "app_secret"),
        APP_TOKEN=value("bkapp_id_secret", "app_secret"),
        BKPAAS_BK_CRYPTO_KEY=value("encryption", "bk_crypto_key"),
        BCS_API_GATEWAY_TOKEN=value("bcs", "token"),
        BKREPO_USERNAME=value("bkrepo", "username"),
        BKREPO_PASSWORD=value("bkrepo", "password"),
        REDIS_PASSWD=value("redis", "password"),
    )
    if os.getenv("USE_BKREPO", "").lower() == "true":
        if not settings["BKREPO_USERNAME"] or not settings["BKREPO_PASSWORD"]:
            raise KMSConfigurationError("Empty required KMS field: bkrepo credentials")
    settings["DATABASES"]["default"].update(USER=value("mysql", "username"), PASSWORD=value("mysql", "password"))
    # Both single-node and Sentinel caches use OPTIONS.PASSWORD for Redis data
    # authentication; Sentinel authentication keeps its existing configuration.
    for cache in settings.get("CACHES", {}).values():
        if cache.get("BACKEND") in (
            "django_redis.cache.RedisCache",
            "django_prometheus.cache.backends.redis.RedisCache",
        ):
            options = cache.setdefault("OPTIONS", {})
            options["PASSWORD"] = value("redis", "password")
            pool_kwargs = options.get("CONNECTION_POOL_KWARGS", {})
            if "password" in pool_kwargs:
                # ConnectionFactory merges these after OPTIONS.PASSWORD.
                pool_kwargs["password"] = value("redis", "password") or None
            # redis-py gives URL credentials/query parameters precedence over
            # OPTIONS.PASSWORD. Remove password sources but keep topology,
            # ACL username, DB, TLS and Sentinel query parameters intact.
            location = cache.get("LOCATION")
            locations = location if isinstance(location, list | tuple) else [location]
            cleaned = []
            for url in locations:
                if url is None:
                    continue
                parsed = urlsplit(url)
                netloc = parsed.netloc
                if "@" in netloc:
                    userinfo, host = netloc.rsplit("@", 1)
                    username = userinfo.split(":", 1)[0]
                    netloc = f"{username}@{host}" if username else host
                query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "password"]
                cleaned.append(urlunsplit(parsed._replace(netloc=netloc, query=urlencode(query))))
            if location is not None:
                cache["LOCATION"] = type(location)(cleaned) if isinstance(location, list | tuple) else cleaned[0]

    # Blueapps builds its default URL without escaping vhost. Escape that raw
    # value before URL/failover parsing, including literal /, ?, # and ;.
    vhost = os.getenv("RABBITMQ_VHOST")
    generated = "amqp://{user}:{password}@{host}:{port}/{vhost}".format(
        user=os.getenv("RABBITMQ_USER"),
        password=os.getenv("RABBITMQ_PASSWORD"),
        host=os.getenv("RABBITMQ_HOST"),
        port=os.getenv("RABBITMQ_PORT"),
        vhost=vhost,
    )
    for name in (
        "BROKER_URL",
        "BROKER_READ_URL",
        "BROKER_WRITE_URL",
        "CELERY_BROKER_URL",
        "CELERY_BROKER_READ_URL",
        "CELERY_BROKER_WRITE_URL",
    ):
        if name != "BROKER_URL" and not settings.get(name):
            continue  # Preserve Celery's optional read/write fallback.
        try:
            raw = settings[name]
            if vhost is not None and raw == generated:
                raw = generated.removesuffix(vhost) + quote(vhost, safe="")
            settings[name] = _broker_credentials(raw, value("rabbitmq", "username"), value("rabbitmq", "password"))
        except (KeyError, ValueError, TypeError):
            raise KMSConfigurationError(f"KMS requires a valid RabbitMQ {name}") from None

    # Validate the actual business cipher before the first ORM access. Do not
    # let SymmetricTextField's tolerant read path hide an unusable key/backend.
    try:
        from bkcrypto.contrib.basic.ciphers import get_symmetric_cipher
        from bkcrypto.contrib.django.settings import CryptoSettings

        crypto = CryptoSettings(user_settings=settings["BKCRYPTO"])
        cipher_type = crypto.SYMMETRIC_CIPHER_TYPE
        config = crypto.SYMMETRIC_CIPHERS["default"]
        common = dict(config.common or {})
        key = settings["BKPAAS_BK_CRYPTO_KEY"] or settings["SECRET_KEY"]
        common["key"] = key
        get_symmetric_cipher(
            cipher_type,
            common=common,
            cipher_options=config.cipher_options,
            symmetric_cipher_classes=crypto.SYMMETRIC_CIPHER_CLASSES,
        )
    except Exception:
        raise KMSConfigurationError("Invalid KMS business encryption key or unavailable cipher backend") from None
