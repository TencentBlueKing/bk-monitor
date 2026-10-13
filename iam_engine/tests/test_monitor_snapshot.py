from pathlib import Path

from bkmonitor.iam.definitions import Actions, ResourceTypes, Roles
from iam_engine.model.diff import diff_snapshots
from iam_engine.model.loader import MigrationLoader
from iam_engine.schema.loaders import load_from_class
from iam_engine.schema.registry import SchemaRegistry


def test_latest_migration_snapshot_matches_current_definitions():
    registry = SchemaRegistry()
    for container in (ResourceTypes, Actions, Roles):
        load_from_class(registry, container)
    registry.freeze()
    root = Path(__file__).resolve().parents[2]
    migrations = MigrationLoader(str(root / "bkmonitor/bkmonitor/iam/iam_migrations")).load_all()
    latest = migrations["0002_log_mcp_actions"]
    assert latest.dependencies == ["0001_init"]
    assert diff_snapshots(registry.to_snapshot(), latest.target_snapshot) == []
    assert {change.entity_id for change in latest.operations} == {
        "using_log_collection_mcp",
        "using_log_extract_mcp",
        "space_operator",
        "space_admin",
    }
    assert len(latest.target_snapshot["actions"]) == 55
