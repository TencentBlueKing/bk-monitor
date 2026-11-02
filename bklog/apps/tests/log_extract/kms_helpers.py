"""Synthetic startup credentials and real RSA/AES envelopes for KMS tests."""

import base64
import json
import os

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PAYLOAD = {
    "bkapp_id_secret": {"default": {"app_code": "bk_log_search", "app_secret": "app-secret-" * 4}},
    "mysql": {"default": {"username": "db-user", "password": "db-password"}},
    "rabbitmq": {"default": {"username": "user:/@%", "password": "密钥:/@%?#\\\n"}},
    "redis": {"default": {"password": ""}},
    "bkrepo": {"default": {"username": "repo-user", "password": "repo-password"}},
    "bcs": {"default": {"token": "bcs-token"}},
    "encryption": {"bk_crypto_key": ""},
}


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
