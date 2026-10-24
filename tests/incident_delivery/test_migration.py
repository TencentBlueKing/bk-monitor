import importlib.util
import uuid

import pytest
from django.db import connections
from django.db.migrations.state import ProjectState
from test_delivery import SOURCE


@pytest.mark.django_db(transaction=True, databases="__all__")
def test_receipt_migration_roundtrip():
    alias = "receipt_migration"
    connection = connections["default"]
    database_name = None
    if connection.vendor == "mysql":
        database_name = "test_receipt_migration_" + uuid.uuid4().hex
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4")
        connections.databases[alias] = {**connections.databases["default"], "NAME": database_name}
    else:
        connections.databases[alias] = {**connections.databases["default"], "NAME": ":memory:"}
    target = connections[alias]
    try:
        spec = importlib.util.spec_from_file_location(
            "receipt_migration", SOURCE / "bkmonitor/migrations/0208_incident_delivery_receipt.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        migration = module.Migration("0208_incident_delivery_receipt", "bkmonitor")
        before = ProjectState()
        with target.schema_editor() as editor:
            after = migration.apply(before.clone(), editor)
        model = after.apps.get_model("bkmonitor", "IncidentDeliveryReceipt")
        model.objects.using(alias).create(
            delivery_key="a" * 64,
            event_id="event-1",
            bk_tenant_id="tenant-a",
            scope_id="bkcc_2",
            payload_digest="b" * 64,
            payload={"event_id": "event-1"},
        )
        assert model.objects.using(alias).get().payload == {"event_id": "event-1"}
        with target.schema_editor() as editor:
            migration.unapply(before, editor)
        assert "incident_delivery_receipt" not in target.introspection.table_names()
    finally:
        target.close()
        del connections[alias]
        del connections.databases[alias]
        if database_name:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database_name}`")
