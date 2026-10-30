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


def _copy_symmetric_field(field):
    # Match Django Field.__copy__ (including subclass identity and shallow
    # state), but allocate the correct layout directly instead of reassigning
    # Empty.__class__. SDK 4.1.1 adds generic bases that forbid that assignment.
    result = object.__new__(type(field))
    result.__dict__ = field.__dict__.copy()
    return result


def ensure_crypto_field_copy_compatibility():
    """Repair the SDK field's inherited Django copy method when incompatible.

    Blueapps migrations also inherit this SDK class. Patching only a project
    field subclass would leave historical account migrations broken. Keep the
    original class/import path, and leave an SDK-provided copy method alone.
    """
    import copy

    from bkcrypto.contrib.django.fields import SymmetricTextField
    from django.db.models import Field

    if SymmetricTextField.__copy__ is not Field.__copy__:
        return
    try:
        copy.copy(SymmetricTextField())
    except TypeError as error:
        if "__class__ assignment" not in str(error):
            raise
        SymmetricTextField.__copy__ = _copy_symmetric_field
