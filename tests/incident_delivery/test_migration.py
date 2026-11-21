import ast
import importlib.util
import uuid

import pytest
from django.db import connections
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.state import ProjectState
from test_delivery import SOURCE


RECEIPT = ("bkmonitor", "0208_incident_delivery_receipt")
MASTER = ("bkmonitor", "0211_merge_20261014_2132")
MERGE = ("bkmonitor", "0212_merge_incident_delivery_receipt")


def load_migration(key):
    spec = importlib.util.spec_from_file_location(key[1], SOURCE / f"bkmonitor/migrations/{key[1]}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Migration(key[1], key[0])


@pytest.fixture
def migration_graph():
    # Read the complete app graph without importing unrelated production services.
    # Cross-app migrations are outside this focused branch-convergence check.
    graph = MigrationGraph()
    dependencies = {}
    for path in (SOURCE / "bkmonitor/migrations").glob("[0-9]*.py"):
        tree = ast.parse(path.read_text())
        migration_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Migration"
        )
        assignment = next(
            node
            for node in migration_class.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "dependencies" for target in node.targets)
        )
        key = ("bkmonitor", path.stem)
        value = assignment.value
        if isinstance(value, ast.Name):
            # 0141 uses a module constant; its role-specific append is cross-app.
            value = next(
                node.value
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == value.id for target in node.targets)
            )
        dependencies[key] = [tuple(dep) for dep in ast.literal_eval(value) if dep[0] == "bkmonitor"]
        graph.add_node(key, None)
    for key, parents in dependencies.items():
        for parent in parents:
            graph.add_dependency(dependencies[key], key, parent)
    graph.validate_consistency()
    graph.ensure_not_cyclic()
    return graph


def test_receipt_and_master_migrations_converge(migration_graph):
    leaves = migration_graph.leaf_nodes("bkmonitor")
    assert len(leaves) == 1, leaves
    plan = migration_graph.forwards_plan(leaves[0])
    assert {RECEIPT, MASTER, MERGE} <= set(plan)
    assert plan.index(MERGE) > max(plan.index(RECEIPT), plan.index(MASTER))


@pytest.mark.parametrize("applied_parent", [MASTER, RECEIPT])
def test_merge_upgrade_plan_from_either_branch(migration_graph, applied_parent):
    applied = set(migration_graph.forwards_plan(applied_parent))
    pending = [key for key in migration_graph.forwards_plan(MERGE) if key not in applied]
    other_parent = RECEIPT if applied_parent == MASTER else MASTER
    assert pending[-1] == MERGE
    assert other_parent in pending
    assert applied_parent not in pending
    assert pending.count(RECEIPT) == (0 if applied_parent == RECEIPT else 1)


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
        migration = load_migration(RECEIPT)
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
        merge = load_migration(MERGE)
        statements = []

        def record_sql(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)

        with target.schema_editor() as editor, target.execute_wrapper(record_sql):
            merged = merge.apply(after.clone(), editor)
            merge.unapply(after, editor)
        assert statements == []
        assert merged.models == after.models
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
