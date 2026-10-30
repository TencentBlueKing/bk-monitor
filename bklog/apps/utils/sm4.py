"""Legacy business-key compatibility; imported only when SM4 is selected."""

from bkcrypto.symmetric.ciphers.sm4 import SM4SymmetricCipher

from apps.utils.crypto import LegacySymmetricKeyMixin


class LegacySM4SymmetricCipher(LegacySymmetricKeyMixin, SM4SymmetricCipher):
    pass
