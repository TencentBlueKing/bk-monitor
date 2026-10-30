"""Use real RSA/AES envelopes; no network, Kubernetes or production secrets."""

import base64
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from apps.utils.crypto import LEGACY_SYMMETRIC_CIPHER_CLASSES

MODULE = Path(__file__).resolve().parents[2] / "config/kms.py"
spec = importlib.util.spec_from_file_location("kms_under_test", MODULE)
kms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kms)

PAYLOAD = {
    "bkapp_id_secret": {"default": {"app_code": "bk_log_search", "app_secret": "app-secret-" * 4}},
    "mysql": {"default": {"username": "db-user", "password": "db-password"}},
    "rabbitmq": {"default": {"username": "user:/@%", "password": "密钥:/@%?#\\\n"}},
    "redis": {"default": {"password": ""}},
    "bkrepo": {"default": {"username": "repo-user", "password": "repo-password"}},
    "bcs": {"default": {"token": "bcs-token"}},
    "encryption": {"bk_crypto_key": ""},
}


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def envelope(text, key, mode="CTR"):
    data_key, iv = os.urandom(16), os.urandom(16)
    raw = text.encode()
    if mode == "CBC":
        pad = padding.PKCS7(128).padder()
        raw = pad.update(raw) + pad.finalize()
    encrypt = Cipher(algorithms.AES(data_key), modes.CTR(iv) if mode == "CTR" else modes.CBC(iv)).encryptor()
    encrypted_key = key.public_key().encrypt(
        data_key, rsa_padding.OAEP(mgf=rsa_padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )

    def encode(value):
        return base64.b64encode(value).decode()

    return encode(
        json.dumps(
            dict(
                asymmetric_type="RSA",
                symmetric_type="AES",
                symmetric_mode=mode,
                encrypted_key=encode(encrypted_key),
                ciphertext=encode(iv + encrypt.update(raw) + encrypt.finalize()),
            )
        ).encode()
    )


@pytest.fixture
def configure(monkeypatch, tmp_path, private_key):
    kms.credentials.cache_clear()

    def setup(payload=PAYLOAD, mode="CTR"):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (tmp_path / "envelope").write_text(envelope(text, private_key, mode))
        pem = private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        (tmp_path / "private-key").write_text(base64.b64encode(pem).decode())
        for key, value in {
            "ENABLE_KMS": "true",
            "BKPAAS_APP_ID": "bk_log_search",
            "KMS_ENVELOPE_FILE": str(tmp_path / "envelope"),
            "KMS_PRIVATE_KEY_FILE": str(tmp_path / "private-key"),
        }.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("APP_ID", raising=False)
        kms.credentials.cache_clear()

    yield setup
    kms.credentials.cache_clear()


@pytest.mark.parametrize("mode", ["CTR", "CBC"])
def test_real_decryption_and_final_overlays(configure, mode):
    configure(mode=mode)
    before = dict(os.environ)
    assert kms.credentials() == PAYLOAD
    settings = {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {"HOST": "db", "USER": "stale", "PASSWORD": "stale"}},
        "BROKER_URL": "amqp://None:None@[::1]:5672/a%2Fb?heartbeat=60",
        "CACHES": {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "OPTIONS": {"PASSWORD": "stale", "SENTINEL_KWARGS": {"password": "unchanged"}},
            }
        },
    }
    kms.apply_settings(settings)
    assert settings["DATABASES"]["default"] == {"HOST": "db", "USER": "db-user", "PASSWORD": "db-password"}
    broker = urlsplit(settings["BROKER_URL"])
    assert unquote(broker.username) == PAYLOAD["rabbitmq"]["default"]["username"]
    assert unquote(broker.password) == PAYLOAD["rabbitmq"]["default"]["password"]
    assert (broker.hostname, broker.port, broker.path, broker.query) == ("::1", 5672, "/a%2Fb", "heartbeat=60")
    assert settings["CACHES"]["default"]["OPTIONS"] == {"PASSWORD": "", "SENTINEL_KWARGS": {"password": "unchanged"}}
    assert settings["BKPAAS_BK_CRYPTO_KEY"] == ""
    assert os.environ == before
    Path(os.environ["KMS_ENVELOPE_FILE"]).unlink()
    assert kms.credentials() == PAYLOAD  # startup snapshot; rotation requires restart


FIELDS = [
    (group, name) for group, item in PAYLOAD.items() for name in (item if group == "encryption" else item["default"])
]


@pytest.mark.parametrize("group,field", FIELDS)
@pytest.mark.parametrize("bad", ["missing", None, 123, False, {}])
def test_every_field_validated(configure, group, field, bad):
    payload = copy.deepcopy(PAYLOAD)
    item = payload[group] if group == "encryption" else payload[group]["default"]
    if bad == "missing":
        del item[field]
    else:
        item[field] = bad
    configure(payload)
    with pytest.raises(kms.KMSConfigurationError):
        kms.credentials()


@pytest.mark.parametrize("text", ["[]", "null", '"plaintext-secret"', "{broken secret json"])
def test_bad_json(configure, text):
    configure(text)
    with pytest.raises(kms.KMSConfigurationError) as error:
        kms.credentials()
    assert text not in str(error.value)


@pytest.mark.parametrize(
    "failure", ["missing_envelope", "missing_key", "wrong_key", "mismatched_key", "bad_envelope", "wrong_app"]
)
def test_fail_closed(configure, monkeypatch, failure):
    configure()
    if failure == "missing_envelope":
        Path(os.environ["KMS_ENVELOPE_FILE"]).unlink()
    elif failure == "missing_key":
        monkeypatch.delenv("KMS_PRIVATE_KEY_FILE")
    elif failure == "wrong_key":
        Path(os.environ["KMS_PRIVATE_KEY_FILE"]).write_text("DO_NOT_LOG_PRIVATE_KEY")
    elif failure == "mismatched_key":
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = other.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        Path(os.environ["KMS_PRIVATE_KEY_FILE"]).write_text(base64.b64encode(pem).decode())
    elif failure == "bad_envelope":
        Path(os.environ["KMS_ENVELOPE_FILE"]).write_text("DO_NOT_LOG_ENVELOPE")
    else:
        monkeypatch.setenv("BKPAAS_APP_ID", "wrong-app")
    monkeypatch.setenv("BKPAAS_APP_SECRET", "DO_NOT_FALL_BACK")
    with pytest.raises(kms.KMSConfigurationError) as error:
        kms.credentials()
    assert "DO_NOT" not in str(error.value)


@pytest.mark.parametrize("mode", ["false", "off", "0", ""])
def test_disabled_no_file_or_sdk(monkeypatch, mode):
    import builtins

    kms.credentials.cache_clear()
    monkeypatch.setenv("ENABLE_KMS", mode)
    monkeypatch.setenv("KMS_ENVELOPE_FILE", "/nonexistent")
    original = builtins.__import__

    def no_sdk(name, *args, **kwargs):
        assert name != "bk_kms"
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sdk)
    data = {"SECRET_KEY": "original"}
    kms.apply_settings(data)
    assert data == {"SECRET_KEY": "original"}
    assert kms.value("mysql", "password", "original") == "original"
    kms.credentials.cache_clear()


@pytest.mark.parametrize(
    "role",
    [
        "web",
        "api",
        "web-worker",
        "hworker",
        "web-beat",
        "async-worker",
        "oworker",
        "pworker",
        "db-migrate",
        "post-migrate",
        "builtin-collect",
    ],
)
@pytest.mark.parametrize("redis_mode", ["single", "sentinel"])
def test_real_settings_entrypoints(configure, monkeypatch, role, redis_mode):
    import subprocess
    import sys

    configure()
    root = MODULE.parents[2]
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(root / "bklog"), str(root)]),
        BKPAAS_MAJOR_VERSION="3",
        BK_PAAS2_URL="http://paas.local",
        BKPAAS_ENVIRONMENT="prod",
        DEPLOY_MODE="kubernetes",
        DB_NAME="bklog",
        DB_HOST="mysql.local",
        DB_PORT="3306",
        DB_PREFIX="MYSQL",
        RABBITMQ_VHOST="bklog",
        RABBITMQ_HOST="rabbit.local",
        RABBITMQ_PORT="5672",
        REDIS_HOST="redis.local",
        REDIS_PORT="6379",
        BKAPP_REDIS_MODE=redis_mode,
        BK_BKLOG_REDIS_MODE=redis_mode,
        BKAPP_IS_BKLOG_API="1" if role == "api" else "",
        USE_BKREPO="true",
        BKAPP_REDIS_SENTINEL_HOST="sentinel.local",
        BK_BKLOG_REDIS_SENTINEL_HOST="sentinel.local",
    )
    code = """
import os, sys
role = sys.argv[1]
sys.argv = (['manage.py', 'celery', 'beat' if role == 'web-beat' else 'worker']
            if role in ('web-worker', 'hworker', 'web-beat', 'async-worker', 'oworker', 'pworker')
            else ['manage.py', role])
from django.conf import settings
import settings as project
from config import get_env_or_raise
assert project.APP_CODE == project.APP_ID == 'bk_log_search'
assert project.SECRET_KEY == project.APP_TOKEN == 'app-secret-' * 4
assert get_env_or_raise('APP_TOKEN') == project.SECRET_KEY
assert project.DATABASES['default']['USER'] == 'db-user'
assert project.DATABASES['default']['PASSWORD'] == 'db-password'
assert project.BCS_API_GATEWAY_TOKEN == 'bcs-token'
assert project.BKREPO_USERNAME == 'repo-user'
assert project.BKPAAS_BK_CRYPTO_KEY == ''
assert project.REDIS_PASSWD == ''
assert bool(project.BKAPP_IS_BKLOG_API) == (role == 'api')
assert project.IS_CELERY == ('celery' in sys.argv)
assert project.IS_CELERY_BEAT == ('beat' in sys.argv)
assert project.CACHES['default']['OPTIONS']['PASSWORD'] == ''
from kombu import Connection
connection = Connection(project.BROKER_URL)
assert connection.userid == 'user:/@%'
assert connection.password == '密钥:/@%?#\\\\\\n'
assert connection.virtual_host == 'bklog'
from bkcrypto.contrib.django.ciphers import symmetric_cipher_manager
cipher = symmetric_cipher_manager.cipher()
assert cipher.decrypt(cipher.encrypt('historical-key-test')) == 'historical-key-test'
assert cipher.config.key == project.SECRET_KEY.encode()[:16]
assert 'BKPAAS_APP_SECRET' not in os.environ
print('OK')
"""
    result = subprocess.run([sys.executable, "-c", code, role], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")


@pytest.mark.parametrize("environment", ["prod", "stag", "dev"])
@pytest.mark.parametrize("deploy_mode", ["kubernetes", "standalone"])
def test_legacy_settings_entrypoints(monkeypatch, environment, deploy_mode):
    import subprocess
    import sys

    root = MODULE.parents[2]
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(root / "bklog"), str(root)]),
        ENABLE_KMS="false",
        BKPAAS_APP_ID="legacy-app",
        BKPAAS_APP_SECRET="legacy-secret-kept-exactly",
        BKPAAS_MAJOR_VERSION="3",
        BK_PAAS2_URL="http://paas.local",
        BKPAAS_ENVIRONMENT=environment,
        BKPAAS_BK_CRYPTO_KEY="",
        DEPLOY_MODE=deploy_mode,
        KMS_ENVELOPE_FILE="/must/not/read",
    )
    code = """
import sys
class NoSDK:
    def find_spec(self, fullname, *args):
        if fullname == 'bk_kms':
            raise AssertionError('disabled startup must not import KMS SDK')
sys.meta_path.insert(0, NoSDK())
import settings
assert settings.SECRET_KEY == 'legacy-secret-kept-exactly'
assert settings.APP_CODE == 'legacy-app'
print('OK')
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")


@pytest.mark.parametrize("vhost", ["/", "team/a", "项目?#%@/", "team;name"])
def test_broker_vhost_escaping(configure, monkeypatch, vhost):
    from kombu import Connection

    configure()
    monkeypatch.setenv("RABBITMQ_VHOST", vhost)
    monkeypatch.setenv("RABBITMQ_HOST", "rabbit.local")
    monkeypatch.setenv("RABBITMQ_PORT", "5672")
    data = {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {}},
        "BROKER_URL": f"amqp://None:None@rabbit.local:5672/{vhost}",
    }
    kms.apply_settings(data)
    assert Connection(data["BROKER_URL"]).virtual_host == vhost


@pytest.mark.parametrize("key", ["short", ""])
def test_invalid_business_key_blocks_startup(configure, key):
    payload = copy.deepcopy(PAYLOAD)
    payload["bkapp_id_secret"]["default"]["app_secret"] = "short"
    payload["encryption"]["bk_crypto_key"] = key
    configure(payload)
    data = {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {}},
        "BROKER_URL": "amqp://None:None@rabbit:5672//",
    }
    with pytest.raises(kms.KMSConfigurationError, match="business encryption"):
        kms.apply_settings(data)


@pytest.mark.parametrize(
    "field",
    [
        "APP_TOKEN",
        "BKPAAS_APP_SECRET",
        "DB_USERNAME",
        "DB_PASSWORD",
        "RABBITMQ_USER",
        "RABBITMQ_PASSWORD",
        "REDIS_PASSWORD",
        "BKREPO_PASSWORD",
        "BKPAAS_BK_CRYPTO_KEY",
    ],
)
def test_plaintext_environment_conflict(configure, monkeypatch, field):
    configure()
    monkeypatch.setenv(field, "DO_NOT_LOG")
    with pytest.raises(kms.KMSConfigurationError) as error:
        kms.credentials()
    assert field in str(error.value)
    assert "DO_NOT_LOG" not in str(error.value)


@pytest.mark.parametrize("field", ["CELERY_BROKER_URL", "CELERY_BROKER_READ_URL", "CELERY_BROKER_WRITE_URL"])
def test_celery_environment_override_rejected(configure, monkeypatch, field):
    configure()
    monkeypatch.setenv(field, "amqp://old-user:DO_NOT_LOG@old-host//")
    with pytest.raises(kms.KMSConfigurationError) as error:
        kms.credentials()
    assert field in str(error.value)
    assert "DO_NOT_LOG" not in str(error.value)


def test_celery_actual_connections_use_kms(configure):
    from celery import Celery

    configure()
    data = {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {}},
        "BROKER_URL": "amqp://old:old@rabbit:5672//",
    }
    kms.apply_settings(data)
    app = Celery("kms-regression")
    app.config_from_object(data)
    for connection in (app.connection_for_read(), app.connection_for_write()):
        assert connection.userid == PAYLOAD["rabbitmq"]["default"]["username"]
        assert connection.password == PAYLOAD["rabbitmq"]["default"]["password"]
        assert connection.hostname == "rabbit"
    app.close()


@pytest.mark.parametrize(
    "location",
    [
        "redis://:old@localhost:6379/3",
        "rediss://acl-user:old@localhost:6379/3?password=query-old&ssl_cert_reqs=none",
        ["redis://:old@localhost:6379/3?password=query-old", "redis://acl:old@localhost:6380/3"],
    ],
)
@pytest.mark.parametrize("password", ["", "new:/@%密钥"])
def test_real_redis_pool_password_precedence(configure, monkeypatch, location, password):
    from django_redis.pool import ConnectionFactory

    monkeypatch.setattr(ConnectionFactory, "_pools", {})
    payload = copy.deepcopy(PAYLOAD)
    payload["redis"]["default"]["password"] = password
    configure(payload)
    data = {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {}},
        "BROKER_URL": "amqp://old:old@rabbit:5672//",
        "CACHES": {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": location,
                "OPTIONS": {"PASSWORD": "old"},
            }
        },
    }
    kms.apply_settings(data)
    cache = data["CACHES"]["default"]
    urls = cache["LOCATION"] if isinstance(cache["LOCATION"], list) else [cache["LOCATION"]]
    for url in urls:
        params = ConnectionFactory(cache["OPTIONS"]).make_connection_params(url)
        pool = ConnectionFactory(cache["OPTIONS"]).get_connection_pool(params)
        assert pool.connection_kwargs["password"] == (password or None)
        assert pool.connection_kwargs["db"] == 3
        assert pool.connection_kwargs["host"] == "localhost"
        if "acl" in url:
            assert pool.connection_kwargs["username"] in ("acl", "acl-user")
    assert "old" not in str(cache["LOCATION"])


def broker_settings():
    return {
        "BKCRYPTO": {"SYMMETRIC_CIPHER_CLASSES": LEGACY_SYMMETRIC_CIPHER_CLASSES, "SYMMETRIC_CIPHERS": {"default": {}}},
        "DATABASES": {"default": {}},
        "BROKER_URL": "amqp://old:old@default-host:5672/default-vhost",
    }


@pytest.mark.parametrize("namespace,prefix", [(None, "BROKER_"), ("CELERY", "CELERY_BROKER_")])
@pytest.mark.parametrize("shape", ["single", "list", "tuple", "semicolon"])
def test_celery_settings_read_write_preserve_topology(configure, namespace, prefix, shape):
    from celery import Celery
    from kombu import Connection

    configure()
    data = broker_settings()
    if namespace:
        data[prefix + "URL"] = data["BROKER_URL"]
    originals = {}
    for role in ("READ", "WRITE"):
        urls = [
            f"amqp://old:old@{role.lower()}-host:5673/team%2F{role.lower()}?heartbeat=17",
            f"amqp://old:old@{role.lower()}-backup:5674/backup",
        ]
        originals[role] = urls[:1] if shape == "single" else urls
        data[prefix + role + "_URL"] = (
            urls[0]
            if shape == "single"
            else urls
            if shape == "list"
            else tuple(urls)
            if shape == "tuple"
            else ";".join(urls)
        )
    kms.apply_settings(data)
    app = Celery("read-write-settings-regression")
    app.config_from_object(data, namespace=namespace)
    for role, connection in (("READ", app.connection_for_read()), ("WRITE", app.connection_for_write())):
        assert connection.hostname == role.lower() + "-host"
        assert connection.port == 5673
        assert connection.virtual_host == "team/" + role.lower()
        assert connection.userid == PAYLOAD["rabbitmq"]["default"]["username"]
        assert connection.password == PAYLOAD["rabbitmq"]["default"]["password"]
        raw = data[prefix + role + "_URL"]
        if shape in ("list", "tuple"):
            assert isinstance(raw, list if shape == "list" else tuple)
        assert len(connection.alt or [raw]) == len(originals[role])
        for actual, original in zip(connection.alt or [raw], originals[role]):
            parsed = urlsplit(actual)
            previous = urlsplit(original)
            assert (parsed.hostname, parsed.port, parsed.path, parsed.query) == (
                previous.hostname,
                previous.port,
                previous.path,
                previous.query,
            )
            assert Connection(actual).password == PAYLOAD["rabbitmq"]["default"]["password"]
    app.close()


@pytest.mark.parametrize("empty", [None, "", []])
def test_celery_unset_read_write_still_fall_back(configure, empty):
    from celery import Celery

    configure()
    data = broker_settings()
    data.update(BROKER_READ_URL=copy.deepcopy(empty), BROKER_WRITE_URL=copy.deepcopy(empty))
    kms.apply_settings(data)
    assert data["BROKER_READ_URL"] == empty
    assert data["BROKER_WRITE_URL"] == empty
    assert "CELERY_BROKER_READ_URL" not in data
    app = Celery("broker-fallback")
    app.config_from_object(data)
    for connection in (app.connection_for_read(), app.connection_for_write()):
        assert connection.hostname == "default-host"
        assert connection.password == PAYLOAD["rabbitmq"]["default"]["password"]
    app.close()


@pytest.mark.parametrize("key", ["BROKER_READ_URL", "BROKER_WRITE_URL", "CELERY_BROKER_READ_URL"])
def test_invalid_read_write_url_fails_without_secret_disclosure(configure, key):
    configure()
    data = broker_settings()
    data[key] = "redis://:DO_NOT_LOG@wrong-backend/0"
    with pytest.raises(kms.KMSConfigurationError) as error:
        kms.apply_settings(data)
    assert key in str(error.value)
    assert "DO_NOT_LOG" not in str(error.value)


@pytest.mark.parametrize("password", ["", "kms:/@%密码"])
@pytest.mark.parametrize("sentinel", [False, True])
def test_redis_pool_kwargs_cannot_override_kms(configure, monkeypatch, password, sentinel):
    from django_redis.pool import ConnectionFactory
    from apps.utils.sentinel import SentinelConnectionFactory

    monkeypatch.setattr(ConnectionFactory, "_pools", {})
    payload = copy.deepcopy(PAYLOAD)
    payload["redis"]["default"]["password"] = password
    configure(payload)
    data = broker_settings()
    options = {
        "PASSWORD": "options-old",
        "CONNECTION_POOL_KWARGS": {"password": "kwargs-old", "max_connections": 7, "socket_timeout": 3},
    }
    location = "redis://:url-old@localhost:6379/3?password=query-old"
    if sentinel:
        options.update(SENTINELS=[("localhost", 26379)], SENTINEL_KWARGS={"password": "sentinel-keep"})
        location = "redis://mymaster/0?is_master=1&password=query-old"
    data["CACHES"] = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": location, "OPTIONS": options}}
    kms.apply_settings(data)
    factory = (SentinelConnectionFactory if sentinel else ConnectionFactory)(options)
    pool = factory.get_connection_pool(factory.make_connection_params(data["CACHES"]["default"]["LOCATION"]))
    assert pool.connection_kwargs["password"] == (password or None)
    assert pool.connection_kwargs["socket_timeout"] == 3
    assert pool.max_connections == 7
    assert options["CONNECTION_POOL_KWARGS"]["password"] == (password or None)
    if sentinel:
        assert options["SENTINEL_KWARGS"]["password"] == "sentinel-keep"
        assert factory._sentinel.connection_kwargs["password"] == (password or None)
        assert pool.service_name == "mymaster"
        assert pool.is_master


def test_kms_off_preserves_all_legacy_overrides(configure, monkeypatch):
    configure()
    monkeypatch.setenv("ENABLE_KMS", "false")
    data = broker_settings()
    data.update(
        BROKER_READ_URL="amqp://legacy:legacy@reader//",
        BROKER_WRITE_URL="amqp://legacy:legacy@writer//",
        CELERY_BROKER_READ_URL="amqp://legacy:legacy@other-reader//",
    )
    data["CACHES"] = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://:url-old@localhost/0?password=query-old",
            "OPTIONS": {
                "PASSWORD": "options-old",
                "CONNECTION_POOL_KWARGS": {"password": "kwargs-old", "max_connections": 7},
            },
        }
    }
    expected = copy.deepcopy(data)
    kms.apply_settings(data)
    assert data == expected


@pytest.mark.parametrize("name", ["BROKER_URL", "BROKER_READ_URL", "BROKER_WRITE_URL"])
def test_celery_implicit_host_defaults_preserved(configure, name):
    from celery import Celery
    from kombu import Connection

    configure()
    data = broker_settings()
    data[name] = "amqp://"
    previous = Connection(data[name])
    kms.apply_settings(data)
    app = Celery("implicit-host")
    app.config_from_object(data)
    connection = app.connection_for_write() if name == "BROKER_WRITE_URL" else app.connection_for_read()
    assert connection.hostname == previous.hostname
    assert connection.virtual_host == previous.virtual_host
    assert connection.userid == PAYLOAD["rabbitmq"]["default"]["username"]
    assert connection.password == PAYLOAD["rabbitmq"]["default"]["password"]
    app.close()
