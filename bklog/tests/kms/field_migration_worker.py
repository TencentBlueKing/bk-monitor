"""Exercise Django's real SQLite table-rebuild path in an isolated interpreter."""

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
configuration = {
    "SECRET_KEY": "0123456789abcdef" * 2,
    "BLUEAPPS_ENABLE_DB_ENCRYPTION": True,
    "INSTALLED_APPS": [],
    "DATABASES": {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    "BKCRYPTO": {"SYMMETRIC_CIPHERS": {"default": {"common": {"key": "0123456789abcdef"}}}},
}
spec = importlib.util.spec_from_file_location(
    "migration_kms_config", Path(__file__).resolve().parents[2] / "config/kms.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
os.environ["ENABLE_KMS"] = "false"
os.environ["APP_ID"] = "migration-probe"
os.environ["APP_TOKEN"] = "0123456789abcdef" * 2
module.apply_settings(configuration)
from django.conf import settings

settings.configure(**configuration)
import django

django.setup()
import unittest

from apps.tests.log_extract.test_crypto_field_copy import CryptoFieldCopyTest
from bkcrypto.contrib.django.fields import SymmetricTextField
from blueapps.utils.crypto import SymmetricTextField as BlueappsSymmetricTextField
from django.db import connection, migrations, models
from django.db.migrations.state import ProjectState

result = unittest.TextTestRunner(stream=sys.stderr).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(CryptoFieldCopyTest)
)
assert result.wasSuccessful()
for index, field_class in enumerate((SymmetricTextField, BlueappsSymmetricTextField)):
    app_label = f"field_copy_probe_{index}"
    initial = migrations.Migration("0001_initial", app_label)
    initial.operations = [
        migrations.CreateModel(
            name="Credential",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("secret", field_class(null=True, blank=True)),
                ("description", models.TextField(null=True)),
            ],
        )
    ]
    with connection.schema_editor() as editor:
        state = initial.apply(ProjectState(), editor)
    Model = state.apps.get_model(app_label, "Credential")
    Model.objects.create(secret="historical secret 密钥", description="before")
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT secret FROM "{Model._meta.db_table}"')
        ciphertext = cursor.fetchone()[0]
    assert ciphertext.startswith("aes_str:::")
    alter = migrations.Migration("0002_alter_description", app_label)
    alter.operations = [migrations.AlterField("Credential", "description", models.TextField(null=False))]
    previous = state.clone()
    with connection.schema_editor() as editor:
        state = alter.apply(state, editor)
    assert state.apps.get_model(app_label, "Credential").objects.get(pk=1).secret == "historical secret 密钥"
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT secret FROM "{Model._meta.db_table}"')
        assert cursor.fetchone()[0] == ciphertext
    with connection.schema_editor() as editor:
        alter.unapply(previous, editor)
    assert previous.apps.get_model(app_label, "Credential").objects.get(pk=1).secret == "historical secret 密钥"
print("field copy + SQLite migration apply/reverse: OK")
