import hashlib

from bkcrypto.symmetric.configs import KeyConfig

from bk_monitor_base.config import get_config


def get_symmetric_cipher_key_config(cipher_type: str) -> KeyConfig:
    config = get_config()
    aes_key = config.encryption.aes_secret_key or config.blueking.app_secret
    config = KeyConfig(key=hashlib.sha256(aes_key.encode("utf-8")).digest())
    return config
