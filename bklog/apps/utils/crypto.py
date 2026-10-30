"""Preserve bkcrypto 2.x effective keys at the cipher constructor boundary."""

LEGACY_SYMMETRIC_CIPHER_CLASSES = {
    "AES": "apps.utils.aes.LegacyAESSymmetricCipher",
    "SM4": "apps.utils.sm4.LegacySM4SymmetricCipher",
}


class LegacySymmetricKeyMixin:
    def __init__(self, key=None, **options):
        # At this extension point common/algorithm/alias options are already
        # merged by bkcrypto. The key hook alone receives no alias or options.
        if isinstance(key, str):
            key = key.encode(options.get("encoding", "utf-8"))
        if key is not None:
            key = key[: options.get("key_size", 16)]
        super().__init__(key=key, **options)
