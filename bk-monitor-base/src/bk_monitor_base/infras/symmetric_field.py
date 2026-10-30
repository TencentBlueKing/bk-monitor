"""Keep bkcrypto's SymmetricTextField copyable under Django migrations.

This module must stay importable before the Django app registry is ready: it is
called from settings modules and from ``django_setup`` before ``django.setup()``.
"""

import copy


def _copy_symmetric_field(field: object) -> object:
    # Same result as Django Field.__copy__ (subclass identity and shallow
    # state), but allocate the real layout directly: bkcrypto 4.x field bases
    # forbid reassigning Empty.__class__.
    result = object.__new__(type(field))
    result.__dict__ = field.__dict__.copy()
    return result


def ensure_symmetric_field_copy_compatibility() -> None:
    """Repair the SDK field's inherited Django copy method only when it is broken.

    Historical migrations (including blueapps') import the SDK class itself, so
    the repair has to target that class. An SDK-provided copy method is kept.
    """
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
