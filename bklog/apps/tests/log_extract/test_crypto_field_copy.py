"""Regression for the SDK field layout during Django migration table rebuilds."""

import copy

from bkcrypto.contrib.django.fields import SymmetricTextField
from blueapps.utils.crypto import SymmetricTextField as BlueappsSymmetricTextField
from django.test import SimpleTestCase
from django.utils.module_loading import import_string

from apps.utils.crypto import ensure_crypto_field_copy_compatibility


class CryptoFieldCopyTest(SimpleTestCase):
    def test_copy_and_deepcopy_preserve_sdk_and_blueapps_fields(self):
        for field_class in (SymmetricTextField, BlueappsSymmetricTextField):
            for copier in (copy.copy, copy.deepcopy):
                with self.subTest(field=field_class.__module__, copier=copier.__name__):
                    field = field_class(using="archive", prefix="historical:::", null=True, blank=True, default="")
                    field.set_attributes_from_name("credential")
                    duplicate = copier(field)
                    self.assertIs(type(duplicate), field_class)
                    self.assertIsNot(duplicate, field)
                    self.assertIsNot(duplicate.__dict__, field.__dict__)
                    self.assertEqual(duplicate.deconstruct(), field.deconstruct())
                    duplicate.verbose_name = "copy only"
                    self.assertNotEqual(duplicate.verbose_name, field.verbose_name)

    def test_clone_and_deconstruct_retain_import_path(self):
        for field_class in (SymmetricTextField, BlueappsSymmetricTextField):
            with self.subTest(field=field_class.__module__):
                field = field_class(using="archive", prefix="historical:::", null=True, default="")
                clone = field.clone()
                self.assertIs(type(clone), field_class)
                _, path, args, kwargs = field.deconstruct()
                restored = import_string(path)(*args, **kwargs)
                self.assertEqual(restored.deconstruct(), field.deconstruct())
                self.assertEqual(clone.deconstruct(), field.deconstruct())

    def test_compatibility_is_idempotent(self):
        method = SymmetricTextField.__copy__
        ensure_crypto_field_copy_compatibility()
        self.assertIs(SymmetricTextField.__copy__, method)
