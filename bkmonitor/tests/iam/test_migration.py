"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# V4Migrator × extensions.only_providers / exclude_providers 过滤集成测试
#
# 全部离线跑：mock V4Client 让 remote 恒为空，
# 验证本地 schema 的可见性过滤对 diff / plan 的影响，
# 无需 IAM v4 API 环境变量。
# ---------------------------------------------------------------------------

from __future__ import annotations

from bkmonitor.iam.iam_engine.schema.definitions import (
    ActionDef,
    ResourceTypeDef,
    RoleActionBinding,
    RoleDef,
)
from bkmonitor.iam.iam_engine.schema.diff import ChangeType, EntityKind
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_v4.config import V4SystemInfo
from bkmonitor.iam.iam_v4.migrator import V4Migrator


class _FakeV4Client:
    """最小 V4Client 桩：远端全空，避免任何网络调用。"""

    def retrieve_system(self) -> dict | None:
        # 返回 None 走 _plan_all_create 分支；本组测试想覆盖 diff 分支的另做
        return None


class _FakeV4ClientWithSystem:
    """远端已注册系统，走 _diff_* 分支。"""

    def __init__(self, system_id: str, system_name: str = "test-system") -> None:
        self._system = {"id": system_id, "name": system_name}

    def retrieve_system(self) -> dict:
        return self._system

    def list_actions(self, page: int = 1, page_size: int = 100) -> dict:
        return {"data": {"results": [], "pagination": {"total_pages": 1}}}

    def list_resource_types(self, page: int = 1, page_size: int = 100) -> dict:
        return {"data": {"results": [], "pagination": {"total_pages": 1}}}

    def list_roles(self, page: int = 1, page_size: int = 100) -> dict:
        return {"data": {"results": [], "pagination": {"total_pages": 1}}}


def _make_system() -> V4SystemInfo:
    return V4SystemInfo(
        id="test_system",
        name="Test System",
        description="",
        callback_url="",
        managers=(),
        clients=(),
    )


def _make_schema(*, rt_ext=None, action_ext=None, role_ext=None) -> SchemaRegistry:
    """构造一个"space + view + admin"三件套，允许分别注入 extensions。"""
    schema = SchemaRegistry()
    schema.register_resource_type(
        ResourceTypeDef(id="space", name="业务", extensions=rt_ext or {}),
    )
    schema.register_action(
        ActionDef(
            id="view_business",
            name="业务查看",
            resource_type="space",
            extensions=action_ext or {},
        ),
    )
    schema.register_role(
        RoleDef(
            id="space_admin",
            name="业务管理员",
            actions=(RoleActionBinding(action_id="view_business", resource_type="space"),),
            extensions=role_ext or {},
        ),
    )
    schema.freeze()
    return schema


class TestV4MigratorProviderVisibility:
    """验证 V4Migrator 遵守 extensions.only_providers / exclude_providers。"""

    # ---------- _plan_all_create 分支（系统未注册） ----------

    def test_plan_all_create_no_filter_all_visible(self):
        """无 extensions → 三个实体都产出 CREATE（+System）。"""
        schema = _make_schema()
        migrator = V4Migrator(_FakeV4Client(), schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        entities = {(c.kind, c.entity_id) for c in plan.changes if c.change_type == ChangeType.CREATE}
        assert (EntityKind.SYSTEM, "test_system") in entities
        assert (EntityKind.RESOURCE_TYPE, "space") in entities
        assert (EntityKind.ACTION, "view_business") in entities
        assert (EntityKind.ROLE, "space_admin") in entities

    def test_plan_all_create_only_v3_action_filtered(self):
        """action 声明 only_providers=('v3',) → V4Migrator 不为它产出 CREATE。"""
        schema = _make_schema(action_ext={"only_providers": ("v3",)})
        migrator = V4Migrator(_FakeV4Client(), schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        action_changes = [c for c in plan.changes if c.kind == EntityKind.ACTION]
        assert action_changes == [], f"expected no action changes, got {action_changes}"
        # 但 resource_type 和 role 仍应存在
        rt_changes = [c for c in plan.changes if c.kind == EntityKind.RESOURCE_TYPE]
        assert any(c.entity_id == "space" for c in rt_changes)

    def test_plan_all_create_exclude_v4_resource_type_filtered(self):
        """resource_type 声明 exclude_providers=('v4',) → V4Migrator 不为它产出 CREATE。"""
        schema = _make_schema(rt_ext={"exclude_providers": ("v4",)})
        migrator = V4Migrator(_FakeV4Client(), schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        rt_changes = [c for c in plan.changes if c.kind == EntityKind.RESOURCE_TYPE]
        assert rt_changes == [], f"expected no resource_type changes, got {rt_changes}"

    def test_plan_all_create_only_v4_role_visible(self):
        """role 声明 only_providers=('v4',) → V4Migrator 正常为它产出 CREATE。"""
        schema = _make_schema(role_ext={"only_providers": ("v4",)})
        migrator = V4Migrator(_FakeV4Client(), schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        role_changes = [c for c in plan.changes if c.kind == EntityKind.ROLE and c.change_type == ChangeType.CREATE]
        assert len(role_changes) == 1
        assert role_changes[0].entity_id == "space_admin"

    # ---------- _diff_* 分支（系统已注册，远端为空） ----------

    def test_diff_only_v3_action_filtered_no_create(self):
        """走 diff 分支时：only_providers=('v3',) 的 action 不会产出 CREATE。"""
        schema = _make_schema(action_ext={"only_providers": ("v3",)})
        client = _FakeV4ClientWithSystem(system_id="test_system", system_name="Test System")
        migrator = V4Migrator(client, schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        action_creates = [c for c in plan.changes if c.kind == EntityKind.ACTION and c.change_type == ChangeType.CREATE]
        assert action_creates == []

    def test_diff_exclude_v4_all_three_filtered(self):
        """三个实体全部 exclude v4 → diff 分支下无任何 CREATE。"""
        schema = _make_schema(
            rt_ext={"exclude_providers": ("v4",)},
            action_ext={"exclude_providers": ("v4",)},
            role_ext={"exclude_providers": ("v4",)},
        )
        client = _FakeV4ClientWithSystem(system_id="test_system", system_name="Test System")
        migrator = V4Migrator(client, schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        non_system_creates = [
            c for c in plan.changes if c.kind != EntityKind.SYSTEM and c.change_type == ChangeType.CREATE
        ]
        assert non_system_creates == []

    def test_diff_regression_backward_compatible(self):
        """回归：没有任何 extensions 的 schema，diff 行为跟以前一致（三个实体都 CREATE）。"""
        schema = _make_schema()
        client = _FakeV4ClientWithSystem(system_id="test_system", system_name="Test System")
        migrator = V4Migrator(client, schema, _make_system())  # type: ignore[arg-type]
        plan = migrator.plan_migration()
        creates_by_kind = {c.kind for c in plan.changes if c.change_type == ChangeType.CREATE}
        assert EntityKind.RESOURCE_TYPE in creates_by_kind
        assert EntityKind.ACTION in creates_by_kind
        assert EntityKind.ROLE in creates_by_kind
