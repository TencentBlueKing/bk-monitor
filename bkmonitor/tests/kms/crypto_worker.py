"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Encrypted-field worker executed in a subprocess, possibly by a bkcrypto 2.x interpreter.

It assembles the real monitor settings (BKCRYPTO, key hook, key sources) from the environment and only swaps
the database for an isolated SQLite file.

    python crypto_worker.py <sqlite-path> write <label>
    python crypto_worker.py <sqlite-path> read <label>
    python crypto_worker.py <sqlite-path> fields
"""

import copy
import importlib.metadata
import json
import os
import sys

TEXT_SAMPLES = ["", "plain", "中文密钥", "quote'\"\\", "line\nbreak", "a" * 15, "b" * 16, "c" * 17, "长" * 300]
JSON_SAMPLES = [{}, {"password": "中文", "nested": {"list": [1, "x"]}}, ["a", 1, None]]


def setup(db_path):
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)
    import settings as monitor_settings

    import django
    from django.conf import settings

    config = {key: getattr(monitor_settings, key) for key in dir(monitor_settings) if key.isupper()}
    config.update(
        INSTALLED_APPS=["django.contrib.contenttypes"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": db_path}},
        DATABASE_ROUTERS=[],
        LOGGING_CONFIG=None,
    )
    settings.configure(**config)
    django.setup()

    from bkcrypto.contrib.django.fields import SymmetricTextField
    from django.db import connection, models

    from bkmonitor.utils.db.fields import SymmetricJsonField

    class Secret(models.Model):
        label = models.CharField(max_length=32)
        index = models.IntegerField()
        text = SymmetricTextField(null=True)
        data = SymmetricJsonField(default=dict)

        class Meta:
            app_label = "kms_crypto_check"
            db_table = "kms_crypto_check_secret"

    if Secret._meta.db_table not in connection.introspection.table_names():
        with connection.schema_editor() as editor:
            editor.create_model(Secret)
    return Secret, connection


def raw_rows(connection, label):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT "index", text, data FROM kms_crypto_check_secret WHERE label = %s ORDER BY "index"', [label]
        )
        return cursor.fetchall()


def write(Secret, label):
    for index, text in enumerate(TEXT_SAMPLES):
        Secret.objects.create(label=label, index=index, text=text, data=JSON_SAMPLES[index % len(JSON_SAMPLES)])
    return {"written": len(TEXT_SAMPLES)}


def read(Secret, connection, label):
    before = raw_rows(connection, label)
    rows = Secret.objects.filter(label=label).order_by("index")
    mismatches = {index for index, text in rows.values_list("index", "text") if text != TEXT_SAMPLES[index]}
    try:
        data = dict(rows.values_list("index", "data"))
    except ValueError:
        # A wrong key leaves the ciphertext in place, which the JSON field cannot parse.
        data = {}
    mismatches |= {
        index for index, *_ in before if data.get(index, object()) != JSON_SAMPLES[index % len(JSON_SAMPLES)]
    }
    return {
        "rows": len(before),
        "mismatches": sorted(mismatches),
        "ciphertext_unchanged": before == raw_rows(connection, label),
    }


def fields(Secret, connection):
    from bkcrypto.contrib.django.fields import SymmetricTextField

    from bkmonitor.utils.db.fields import SymmetricJsonField

    for field in (SymmetricTextField(null=True), SymmetricJsonField(default=dict)):
        for clone in (copy.copy(field), copy.deepcopy(field), field.clone()):
            assert type(clone) is type(field) and clone.deconstruct()[1:] == field.deconstruct()[1:]

    Secret.objects.create(label="migration", index=1, text=TEXT_SAMPLES[2], data=JSON_SAMPLES[1])
    before = raw_rows(connection, "migration")
    old_field = Secret._meta.get_field("text")
    new_field = SymmetricTextField(null=True, blank=True)
    new_field.set_attributes_from_name("text")
    new_field.model = Secret
    # SQLite applies AlterField by rebuilding the table, which deep-copies every field.
    with connection.schema_editor() as editor:
        editor.alter_field(Secret, old_field, new_field)
    row = Secret.objects.get(label="migration")
    return {
        "ciphertext_preserved": raw_rows(connection, "migration") == before,
        "readable": row.text == TEXT_SAMPLES[2] and row.data == JSON_SAMPLES[1],
    }


def main():
    db_path, action = sys.argv[1], sys.argv[2]
    Secret, connection = setup(db_path)
    if action == "write":
        result = write(Secret, sys.argv[3])
    elif action == "read":
        result = read(Secret, connection, sys.argv[3])
    else:
        result = fields(Secret, connection)
    result["bkcrypto"] = importlib.metadata.version("bk-crypto-python-sdk")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
