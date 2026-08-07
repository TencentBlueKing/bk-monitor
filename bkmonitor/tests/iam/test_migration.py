"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# Schema 快照 + 迁移规划器 + 快照 diff 单元测试
# ==============================================================================

import os
import tempfile

import pytest

from bkmonitor.iam.iam_engine.core.exceptions import MigrationPreCheckFailed
from bkmonitor.iam.iam_engine.migration.diff import diff_snapshots
from bkmonitor.iam.iam_engine.migration.loader import MigrationLoader
from bkmonitor.iam.iam_engine.migration.planner import MigrationPlanner
from bkmonitor.iam.iam_engine.migration.recorder import InMemoryRecorder
from bkmonitor.iam.iam_engine.schema.definitions import (
    ActionDef,
    ResourceTypeDef,
    RoleActionBinding,
    RoleDef,
)
from bkmonitor.iam.iam_engine.schema.diff import ChangeType, EntityKind
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry


# ==============================================================================
# to_snapshot / from_snapshot 双射
# ==============================================================================


class TestSnapshotRoundTrip:
    def _build_registry(self) -> SchemaRegistry:
        r = SchemaRegistry()
        r.register_resource_type(ResourceTypeDef(id="space", name="空间"))
        r.register_resource_type(ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space"))
        r.register_action(ActionDef(id="view_business", name="业务访问", resource_type="space"))
        r.register_action(ActionDef(id="view_global_setting", name="全局配置查看", resource_type=""))
        r.register_role(
            RoleDef(
                id="space_viewer",
                name="业务查看",
                actions=(
                    RoleActionBinding(action_id="view_business", resource_type="space"),
                    RoleActionBinding(action_id="view_global_setting", resource_type=""),
                ),
            )
        )
        r.freeze()
        return r

    def test_to_snapshot_structure(self):
        r = self._build_registry()
        s = r.to_snapshot()
        assert "actions" in s and "resource_types" in s and "roles" in s
        assert s["actions"]["view_business"]["name"] == "业务访问"
        assert s["actions"]["view_business"]["resource_type"] == "space"
        assert s["resource_types"]["apm_application"]["ancestor"] == "space"
        assert len(s["roles"]["space_viewer"]["actions"]) == 2

    def test_from_snapshot_rebuilds(self):
        r = self._build_registry()
        s = r.to_snapshot()
        r2 = SchemaRegistry.from_snapshot(s)
        r2.freeze()
        assert r2.get_action("view_business").name == "业务访问"
        assert r2.get_resource_type("space").name == "空间"
        assert r2.resolve_ancestor_types("apm_application") == ["space"]

    def test_round_trip_empty(self):
        r = SchemaRegistry()
        r.freeze()
        s = r.to_snapshot()
        # 空注册表，所有三类都是空 dict
        assert s["actions"] == {}
        assert s["resource_types"] == {}
        assert s["roles"] == {}
        r2 = SchemaRegistry.from_snapshot(s)
        r2.freeze()
        assert r2.all_actions() == []

    def test_to_snapshot_includes_description_and_extensions(self):
        r = SchemaRegistry()
        r.register_action(
            ActionDef(
                id="view_business",
                name="业务访问",
                resource_type="space",
                description="查看业务权限",
                extensions={"v3": {"action_id": "view_business_v2"}},
            )
        )
        r.register_resource_type(ResourceTypeDef(id="space", name="空间"))
        r.freeze()
        s = r.to_snapshot()
        a = s["actions"]["view_business"]
        assert a["description"] == "查看业务权限"
        assert a["extensions"] == {"v3": {"action_id": "view_business_v2"}}

    def test_from_snapshot_rebuilds_extensions(self):
        r = SchemaRegistry()
        r.register_action(
            ActionDef(
                id="view_business",
                name="业务访问",
                resource_type="space",
                extensions={"v3": {"action_id": "view_business_v2", "version": 1}},
            )
        )
        r.register_resource_type(ResourceTypeDef(id="space", name="空间"))
        r.freeze()
        s = r.to_snapshot()
        r2 = SchemaRegistry.from_snapshot(s)
        r2.freeze()
        a = r2.get_action("view_business")
        assert dict(a.extensions) == {"v3": {"action_id": "view_business_v2", "version": 1}}


# ==============================================================================
# diff_snapshots
# ==============================================================================


class TestDiffSnapshots:
    def _base(self):
        return {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {"view_business": {"name": "业务访问", "resource_type": "space"}},
            "roles": {},
        }

    def test_no_diff(self):
        base = self._base()
        assert diff_snapshots(base, base) == []

    def test_new_action_create(self):
        base = self._base()
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {
                "view_business": {"name": "业务访问", "resource_type": "space"},
                "new_action": {"name": "新操作", "resource_type": "space"},
            },
            "roles": {},
        }
        changes = diff_snapshots(current, base)
        creates = [c for c in changes if c.change_type == ChangeType.CREATE]
        assert len(creates) == 1
        assert creates[0].entity_id == "new_action"

    def test_deleted_action_destructive(self):
        base = self._base()
        current = {"resource_types": {"space": {"name": "空间", "ancestor": ""}}, "actions": {}, "roles": {}}
        changes = diff_snapshots(current, base)
        deletes = [c for c in changes if c.change_type == ChangeType.DELETE]
        assert len(deletes) == 1
        assert deletes[0].entity_id == "view_business"
        assert deletes[0].destructive

    def test_action_name_update(self):
        base = self._base()
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {"view_business": {"name": "业务查看（改名）", "resource_type": "space"}},
            "roles": {},
        }
        changes = diff_snapshots(current, base)
        updates = [c for c in changes if c.change_type == ChangeType.UPDATE]
        assert len(updates) == 1 and updates[0].entity_id == "view_business"

    def test_action_rt_change_delete_create(self):
        base = self._base()
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}, "apm": {"name": "APM", "ancestor": "space"}},
            "actions": {"view_business": {"name": "业务访问", "resource_type": "apm"}},
            "roles": {},
        }
        changes = diff_snapshots(current, base)
        deletes = [c for c in changes if c.change_type == ChangeType.DELETE]
        creates = [c for c in changes if c.change_type == ChangeType.CREATE]
        assert len(deletes) == 1 and deletes[0].entity_id == "view_business"
        assert len(creates) == 1 and creates[0].entity_id == "view_business"

    def test_new_role(self):
        base = self._base()
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {"view_business": {"name": "业务访问", "resource_type": "space"}},
            "roles": {
                "space_viewer": {
                    "name": "业务查看",
                    "actions": [{"action_id": "view_business", "resource_type": "space"}],
                }
            },
        }
        changes = diff_snapshots(current, base)
        role_creates = [c for c in changes if c.change_type == ChangeType.CREATE and c.kind == EntityKind.ROLE]
        assert len(role_creates) == 1 and role_creates[0].entity_id == "space_viewer"

    def test_initial_from_empty(self):
        base = {}
        current = self._base()
        changes = diff_snapshots(current, base)
        kinds = {c.kind for c in changes}
        assert EntityKind.RESOURCE_TYPE in kinds
        assert EntityKind.ACTION in kinds

    def test_new_resource_type(self):
        base = {"resource_types": {}, "actions": {}, "roles": {}}
        current = {"resource_types": {"space": {"name": "空间", "ancestor": ""}}, "actions": {}, "roles": {}}
        changes = diff_snapshots(current, base)
        assert len(changes) == 1
        assert changes[0].kind == EntityKind.RESOURCE_TYPE
        assert changes[0].change_type == ChangeType.CREATE

    def test_action_extensions_changed(self):
        base = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {
                "view_business": {"name": "业务访问", "resource_type": "space", "description": "", "extensions": {}}
            },
            "roles": {},
        }
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {
                "view_business": {
                    "name": "业务访问",
                    "resource_type": "space",
                    "description": "",
                    "extensions": {"v3": {"action_id": "view_business_v2"}},
                }
            },
            "roles": {},
        }
        changes = diff_snapshots(current, base)
        updates = [c for c in changes if c.change_type == ChangeType.UPDATE]
        assert len(updates) == 1
        assert updates[0].entity_id == "view_business"
        assert "extensions" in updates[0].reason.lower() or "changed" in updates[0].reason.lower()

    def test_action_description_changed(self):
        base = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {
                "view_business": {"name": "业务访问", "resource_type": "space", "description": "", "extensions": {}}
            },
            "roles": {},
        }
        current = {
            "resource_types": {"space": {"name": "空间", "ancestor": ""}},
            "actions": {
                "view_business": {
                    "name": "业务访问",
                    "resource_type": "space",
                    "description": "updated desc",
                    "extensions": {},
                }
            },
            "roles": {},
        }
        changes = diff_snapshots(current, base)
        updates = [c for c in changes if c.change_type == ChangeType.UPDATE]
        assert len(updates) == 1
        assert updates[0].entity_id == "view_business"


# ==============================================================================
# MigrationLoader
# ==============================================================================


class TestMigrationLoader:
    def test_load_valid(self):
        with tempfile.TemporaryDirectory() as d:
            code = "dependencies = []\noperations = []\ntarget_snapshot = {'actions': {}, 'resource_types': {}, 'roles': {}}\n"
            with open(os.path.join(d, "0001_initial.py"), "w") as f:
                f.write(code)
            loader = MigrationLoader(d)
            migrations = loader.load_all()
            assert "0001_initial" in migrations
            m = migrations["0001_initial"]
            assert m.dependencies == []
            assert m.target_snapshot == {"actions": {}, "resource_types": {}, "roles": {}}

    def test_load_multiple(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("0001_initial", "0002_add_x"):
                with open(os.path.join(d, f"{name}.py"), "w") as f:
                    f.write("dependencies = []\noperations = []\ntarget_snapshot = {}\n")
            assert len(MigrationLoader(d).load_all()) == 2

    def test_skips_non_matching(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "0001_initial.py"), "w") as f:
                f.write("dependencies = []\noperations = []\ntarget_snapshot = {}\n")
            with open(os.path.join(d, "readme.md"), "w") as f:
                f.write("docs")
            assert len(MigrationLoader(d).load_all()) == 1

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            assert MigrationLoader(d).load_all() == {}

    def test_missing_required_attr(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "0001_initial.py"), "w") as f:
                f.write("dependencies = []\n")
            loader = MigrationLoader(d)
            with pytest.raises(MigrationPreCheckFailed, match="operations"):
                loader.load_all()


# ==============================================================================
# MigrationPlanner
# ==============================================================================


def _make_migration_file(d, number: int, name: str, deps: list[str]):
    deps_str = repr(deps)
    code = f"dependencies = {deps_str}\noperations = []\ntarget_snapshot = {{'actions': {{}}, 'resource_types': {{}}, 'roles': {{}}}}\n"
    fname = f"{number:04d}_{name}.py"
    with open(os.path.join(d, fname), "w") as f:
        f.write(code)


class TestMigrationPlanner:
    def test_linear_chain(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", [])
            _make_migration_file(d, 2, "add_x", ["0001_initial"])
            _make_migration_file(d, 3, "add_y", ["0002_add_x"])
            planner = MigrationPlanner(MigrationLoader(d), InMemoryRecorder(), "v4")
            pending = planner.get_pending()
            assert [m.name for m in pending] == ["0001_initial", "0002_add_x", "0003_add_y"]

    def test_partially_applied(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", [])
            _make_migration_file(d, 2, "add_x", ["0001_initial"])
            recorder = InMemoryRecorder()
            recorder.record("v4", "0001_initial", 3)
            planner = MigrationPlanner(MigrationLoader(d), recorder, "v4")
            pending = planner.get_pending()
            assert len(pending) == 1 and pending[0].name == "0002_add_x"

    def test_all_applied(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", [])
            recorder = InMemoryRecorder()
            recorder.record("v4", "0001_initial", 3)
            planner = MigrationPlanner(MigrationLoader(d), recorder, "v4")
            assert planner.get_pending() == []

    def test_cycle_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "a", ["0002_b"])
            _make_migration_file(d, 2, "b", ["0001_a"])
            planner = MigrationPlanner(MigrationLoader(d), InMemoryRecorder(), "v4")
            with pytest.raises(MigrationPreCheckFailed, match="cycle"):
                planner.get_pending()

    def test_missing_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", ["0000_nonexistent"])
            planner = MigrationPlanner(MigrationLoader(d), InMemoryRecorder(), "v4")
            with pytest.raises(MigrationPreCheckFailed, match="not found"):
                planner.get_pending()

    def test_applied_missing_dep_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", [])
            _make_migration_file(d, 2, "add_x", ["0001_initial"])
            recorder = InMemoryRecorder()
            recorder.record("v4", "0002_add_x", 1)
            planner = MigrationPlanner(MigrationLoader(d), recorder, "v4")
            with pytest.raises(MigrationPreCheckFailed, match="depends on"):
                planner.get_pending()

    def test_providers_independent(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "initial", [])
            recorder = InMemoryRecorder()
            recorder.record("v3", "0001_initial", 3)
            assert len(MigrationPlanner(MigrationLoader(d), recorder, "v4").get_pending()) == 1
            assert MigrationPlanner(MigrationLoader(d), recorder, "v3").get_pending() == []

    def test_diamond_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            _make_migration_file(d, 1, "a", [])
            _make_migration_file(d, 2, "b", ["0001_a"])
            _make_migration_file(d, 3, "c", ["0001_a"])
            _make_migration_file(d, 4, "d", ["0002_b", "0003_c"])
            planner = MigrationPlanner(MigrationLoader(d), InMemoryRecorder(), "v4")
            names = [m.name for m in planner.get_pending()]
            assert names.index("0002_b") > names.index("0001_a")
            assert names.index("0003_c") > names.index("0001_a")
            assert names.index("0004_d") > names.index("0002_b")
            assert names.index("0004_d") > names.index("0003_c")
