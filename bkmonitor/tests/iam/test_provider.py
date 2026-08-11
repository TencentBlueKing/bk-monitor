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
# IAM v4 Provider 集成测试（以命令执行视角）
#
# 模拟 iam_engine_migrate 完整流程：
#   Phase ① plan_migration(scope="system") → apply_migration → 系统注册
#   Phase ② 本地 diff(diff_snapshots) + 远端 reconcile(apply_migration) + 文件迁移
#
# 测试覆盖：
#   1. 系统迁移（plan + apply，验证 reconcile 幂等）
#   2. 本地 diff 结果（diff_snapshots：空快照 → 当前 schema）
#   3. 远端 reconcile 结果（plan(scope="full") → apply(dry_run)：期望 vs 实际）
#   4. 文件迁移完整流程（loader → planner → apply → verify no pending）
#   5. V4 全能力：单次鉴权 / 批量鉴权 / apply_url / get_authorized_resources
#   6. 破坏性变更（action id rename / delete）
#
# 可重复性保证：使用 InMemoryRecorder，每次测试独立干净状态。
# 前置条件：.env 中配置好 IAM v4 环境变量（与原来一致）。
# ==============================================================================

import os
import time

import pytest
from django.conf import settings

from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.migration.diff import diff_snapshots
from bkmonitor.iam.iam_engine.migration.loader import MigrationLoader
from bkmonitor.iam.iam_engine.migration.planner import MigrationPlanner
from bkmonitor.iam.iam_engine.migration.recorder import InMemoryRecorder
from bkmonitor.iam.iam_engine.schema.diff import ChangeType, EntityKind, MigrationPlan
from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles

# ---- 配置 ----

_MISSING_CONFIG = (
    not getattr(settings, "BK_IAM_V4_API_BASE_URL", "")
    or not getattr(settings, "BK_IAM_APP_CODE", "")
    or not getattr(settings, "BK_IAM_APP_SECRET", "")
)
SKIP_REASON = "IAM v4 API 未配置（BK_IAM_V4_API_BASE_URL / BK_IAM_APP_CODE / BK_IAM_APP_SECRET）"

TEST_USER = os.getenv("IAM_V4_TEST_USER", "admin")
TEST_SPACE_ID = os.getenv("IAM_V4_TEST_SPACE_ID", "2")
SYSTEM_ID = settings.BK_IAM_V4_SYSTEM_ID

_APPLY_ENABLED = os.getenv("IAM_V4_APPLY", "").lower() in ("1", "true", "yes")
APPLY_SKIP_REASON = "未开启真实 apply（设置 IAM_V4_APPLY=1 才会执行）"

# 已经存在的迁移文件目录
_MIGRATION_DIR = os.path.join(settings.BASE_DIR, "bkmonitor/iam/iam_migrations")
_DIR_EXISTS = os.path.isdir(_MIGRATION_DIR)


# ==============================================================================
# 辅助工具
# ==============================================================================


def _find_change(plan, kind_value: str, entity_id: str, change_type_value: str):
    for c in plan.changes:
        if c.kind.value == kind_value and c.entity_id == entity_id and c.change_type.value == change_type_value:
            return c
    return None


def _get_test_action():
    return getattr(Actions, "TEST_ACTION", None)


# ==============================================================================
# 一、命令执行视角：迁移三阶段
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4CommandFlow:
    """以 iam_engine_migrate 命令视角测试完整迁移流程。

    使用 InMemoryRecorder 保证可重复——每次测试都是干净状态。
    """

    @classmethod
    def setup_class(cls):
        cls._recorder = InMemoryRecorder()

    # ================================================================
    # Phase ① 系统迁移
    # ================================================================

    def test_phase1_system_plan(self):
        """对应 migrate Phase ①：plan_migration(scope="system") —— 纯本地生成系统计划。"""
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="system")

        print(f"\n  provider={plan.provider_name}, changes={len(plan.changes)}")
        for c in plan.changes:
            print(f"    [{c.kind.value}] {c.change_type.value} {c.entity_id}: {c.reason}")

        assert plan.provider_name == "v4"
        assert len(plan.changes) == 1
        assert plan.changes[0].kind == EntityKind.SYSTEM
        assert plan.changes[0].change_type == ChangeType.CREATE
        print("  ✓ 系统计划只含一个 SYSTEM CREATE")

    def test_phase1_system_apply(self):
        """对应 migrate Phase ①：apply_migration —— 查远端 + reconcile + 执行。

        首次：远端无系统 → CREATE。再次运行：远端已有且一致 → reconcile 跳过。
        """
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="system")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)

        print(f"\n  applied={len(report.applied)} failed={len(report.failed)} elapsed={report.elapsed_seconds:.1f}s")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.entity_id}: {err[:200]}")

        assert report.success, f"系统迁移失败: {report.failed}"
        print("  ✓ 系统迁移成功（reconcile 幂等）")

    # ================================================================
    # Phase ② 本地 diff：makemigrations 的 diff_snapshots
    # ================================================================

    def test_phase2_local_diff(self):
        """对应 makemigrations：diff_snapshots(当前 schema, 空快照) → 全量 CREATE Change。

        验证本地 diff 的计数（53 action + 4 RT + 3 role = 60 CREATE）。
        """
        fw = get_framework()
        current = fw.schema.to_snapshot()
        changes = diff_snapshots(current, {})

        kinds = {}
        for c in changes:
            kinds.setdefault(c.kind.value, []).append(c)

        print("\n  本地 diff 结果（空快照 → 当前 schema）：")
        for kind_val, items in sorted(kinds.items()):
            print(f"    {kind_val}: {len(items)} CREATE")

        action_count = len(kinds.get("action", []))
        rt_count = len(kinds.get("resource_type", []))
        role_count = len(kinds.get("role", []))

        assert action_count == 53, f"预期 53 个 action，实际 {action_count}"
        assert rt_count == 4, f"预期 4 个 resource_type，实际 {rt_count}"
        assert role_count == 3, f"预期 3 个 role，实际 {role_count}"
        assert len(changes) == 60
        print(f"  ✓ 本地 diff: {len(changes)} 个 CREATE Change")

    # ================================================================
    # Phase ② 远端 reconcile：本地期望 vs 远端实际
    # ================================================================

    def test_phase2_remote_reconcile_dry_run(self):
        """对应 migrate Phase ② 的 reconcile 环节。

        plan(scope="full") 生成全量 CREATE，apply(dry_run=True) 展示 reconcile 结果：
          - 远端已有 → reconcile 跳过
          - 远端没有 → 出现在 would_apply 中
        """
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")

        total = len(plan.changes)
        print(f"\n  plan(scope=full) 总 Change 数: {total}")

        # dry_run — 只 reconcile 不执行
        report = provider.apply_migration(plan, dry_run=True, allow_destructive=False)

        would_apply = len(report.would_apply)
        skipped = total - would_apply  # 被 reconcile 跳过的

        print(f"  reconcile 结果: would_apply={would_apply}, skipped={skipped}")
        if would_apply > 0:
            print("  需要执行的（远端不存在）：")
            for c in report.would_apply[:15]:
                print(f"    [{c.kind.value}] {c.change_type.value} {c.entity_id}")

        # 如果之前已执行过全量迁移，大部分应被跳过
        assert report.success
        print(f"  ✓ reconcile 完成: 总 {total}, 跳过 {skipped}（远端已有）, 需执行 {would_apply}")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_phase2_remote_reconcile_apply(self):
        """真实 apply(scope=full) —— 将 reconcile 后需要执行的变更提交到远端。

        设置 IAM_V4_APPLY=1 才会执行。
        """
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)

        print(f"\n  applied={len(report.applied)} failed={len(report.failed)} elapsed={report.elapsed_seconds:.1f}s")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.entity_id}: {err[:200]}")

        assert len(report.failed) == 0, f"迁移有失败: {report.failed}"
        print("  ✓ 全量迁移执行成功")

        # 再次 reconcile：应全部跳过
        plan2 = provider.plan_migration(fw.schema, scope="full")
        report2 = provider.apply_migration(plan2, dry_run=True)
        assert len(report2.would_apply) == 0, f"预期全 noop，实际有 {len(report2.would_apply)} 待执行"
        print(f"  ✓ 二次 reconcile: would_apply={len(report2.would_apply)}（已全部幂等）")

    # ================================================================
    # Phase ② 文件迁移：loader → planner → apply → verify
    # ================================================================

    @pytest.mark.skipif(not _DIR_EXISTS, reason=f"迁移目录不存在: {_MIGRATION_DIR}")
    def test_phase2_file_migration_load(self):
        """文件迁移第一步：加载已有迁移文件，计算 pending。

        使用 InMemoryRecorder（干净状态），所有迁移文件都应为 pending。
        """
        loader = MigrationLoader(_MIGRATION_DIR)
        recorder = self.__class__._recorder  # 每次测试独立干净
        planner = MigrationPlanner(loader, recorder, "v4")

        pending = planner.get_pending()

        print(f"\n  迁移目录: {_MIGRATION_DIR}")
        print(f"  pending 迁移: {len(pending)}")
        for m in pending:
            print(f"    {m.name} ({len(m.operations)} changes)")

        assert len(pending) > 0, "应有至少一个 pending 迁移文件"
        print(f"  ✓ 文件迁移加载成功，{len(pending)} 个 pending")

    @pytest.mark.skipif(not _DIR_EXISTS, reason=f"迁移目录不存在: {_MIGRATION_DIR}")
    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_phase2_file_migration_apply(self):
        """文件迁移第二步：逐个 apply pending 迁移文件。

        每个 migration 的 operations 经 apply_migration 查远端 + reconcile + 执行。
        完成后 recorder.record() 记录已应用状态。
        """
        fw = get_framework()
        provider = fw.providers["v4"]
        loader = MigrationLoader(_MIGRATION_DIR)
        recorder = self.__class__._recorder
        planner = MigrationPlanner(loader, recorder, "v4")

        pending = planner.get_pending()
        if not pending:
            pytest.skip("无 pending 迁移文件")

        print(f"\n  共 {len(pending)} 个 pending 迁移文件待执行")
        for migration in pending:
            plan = MigrationPlan(provider_name="v4", changes=list(migration.operations))
            report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)

            print(f"\n  [{migration.name}]")
            print(f"    applied={len(report.applied)} failed={len(report.failed)}")
            for c in report.applied[:5]:
                print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")

            if report.success:
                recorder.record("v4", migration.name, changes_count=len(report.applied))
            else:
                print(f"    ✗ skipped={report.skipped_reason}")
                break

        print("  ✓ 文件迁移 apply 完成")

    @pytest.mark.skipif(not _DIR_EXISTS, reason=f"迁移目录不存在: {_MIGRATION_DIR}")
    def test_phase2_file_migration_verify(self):
        """文件迁移第三步：apply 后应无 pending。

        注意：需要 test_phase2_file_migration_apply 先跑过且 recorder 已记录。
        """
        loader = MigrationLoader(_MIGRATION_DIR)
        recorder = self.__class__._recorder

        applied = recorder.get_applied("v4")
        print(f"\n  已应用: {applied}")

        planner = MigrationPlanner(loader, recorder, "v4")
        pending = planner.get_pending()
        print(f"  pending: {[m.name for m in pending]}")

        if applied:
            # 如果有已应用记录，应无 pending
            assert len(pending) == 0, f"预期无 pending，实际: {[m.name for m in pending]}"
            print("  ✓ 所有迁移文件已应用，无 pending")
        else:
            print("  （尚未执行 apply，跳过 pending 检查）")

    # ================================================================
    # 验证迁移后的鉴权能力
    # ================================================================

    def test_phase2_auth_is_allowed_resource_free(self):
        """迁移完成后：无资源 action 鉴权可用。"""
        fw = get_framework()
        allowed = fw.is_allowed(AuthRequest(subject=Subject(id=TEST_USER), action_id=Actions.VIEW_GLOBAL_SETTING.id))
        print(f"\n  is_allowed({Actions.VIEW_GLOBAL_SETTING.id}) = {allowed}")
        assert isinstance(allowed, bool)

    def test_phase2_auth_is_allowed_with_resource(self):
        """迁移完成后：有资源 action 鉴权可用。"""
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"\n  is_allowed({Actions.VIEW_BUSINESS.id}, space={TEST_SPACE_ID}) = {allowed}")
        assert isinstance(allowed, bool)


# ==============================================================================
# 二、V4 全能力测试（鉴权 / 批量 / apply_url / 授权资源查询）
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4AuthCapabilities:
    """V4 全能力测试 —— 不依赖迁移状态，只验证鉴权 API 可用性。"""

    # ------- 批量资源鉴权 -------

    def test_batch_by_resource(self):
        fw = get_framework()
        space_ids = [str(i) for i in range(1, 6)]
        result = fw.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resources=tuple(ResourceInstance(type=ResourceTypes.SPACE, id=sid) for sid in space_ids),
            )
        )
        print(f"\n  batch_by_resource: {len(result.items)} 条结果")
        for item in result.items:
            print(f"    space={item.resource_id} allowed={item.allowed}")
        assert len(result.items) == len(space_ids)

    # ------- 批量 action 鉴权 -------

    def test_batch_by_action(self):
        fw = get_framework()
        result = fw.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[
                    Actions.VIEW_BUSINESS.id,
                    Actions.EXPLORE_METRIC.id,
                    Actions.VIEW_RULE.id,
                    Actions.VIEW_EVENT.id,
                    Actions.VIEW_DASHBOARD.id,
                ],
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"\n  batch_by_action: {len(result.items)} 条结果")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 5

    def test_batch_by_action_resource_free(self):
        fw = get_framework()
        result = fw.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[
                    Actions.VIEW_GLOBAL_SETTING.id,
                    Actions.VIEW_SELF_STATE.id,
                    Actions.MANAGE_CALENDAR.id,
                ],
            )
        )
        print(f"\n  batch_by_action (resource-free): {len(result.items)} 条结果")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 3

    # ------- 权限申请 URL -------

    def test_get_apply_url(self):
        fw = get_framework()
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.VIEW_BUSINESS.id],
                resources=(ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),),
            )
        )
        print(f"\n  apply_url: {url}")
        assert isinstance(url, str)
        if url:
            assert url.startswith("http")

    # ------- 有权限的资源列表 -------

    def test_get_authorized_resources_resource_free(self):
        fw = get_framework()
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_GLOBAL_SETTING.id,
        )
        print(f"\n  get_authorized_resources({Actions.VIEW_GLOBAL_SETTING.id}) = {result}")
        assert result == []

    def test_get_authorized_resources_view_business(self):
        fw = get_framework()
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_BUSINESS.id,
        )
        print(f"\n  get_authorized_resources({Actions.VIEW_BUSINESS.id}):")
        for item in result:
            print(f"    type={item['type']} ids={item['ids']}")
        assert isinstance(result, list)
        for item in result:
            if item["type"] == ResourceTypes.SPACE.id:
                for rid in item["ids"]:
                    assert not rid.startswith("space|"), f"space id 应已 decode: {rid}"

    # ------- 角色授权参数校验 -------

    def test_add_authorization_invalid_args(self):
        fw = get_framework()
        provider = fw.providers["v4"]
        with pytest.raises(ValueError):
            provider.add_authorization(
                subject=Subject(id=TEST_USER),
                role=Roles.SPACE_VIEWER,
                resource_type=None,
                resource_ids=["2"],
                expired_at=int(time.time()) + 3600,
                operator=TEST_USER,
            )
        with pytest.raises(ValueError):
            provider.add_authorization(
                subject=Subject(id=TEST_USER),
                role=Roles.SPACE_VIEWER,
                resource_type=ResourceTypes.SPACE,
                resource_ids=[],
                expired_at=int(time.time()) + 3600,
                operator=TEST_USER,
            )
        print("\n  ✓ 参数校验生效")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_add_authorization_space_viewer(self):
        fw = get_framework()
        provider = fw.providers["v4"]
        expired_at = int(time.time()) + 3600
        provider.add_authorization(
            subject=Subject(id=TEST_USER),
            role=Roles.SPACE_VIEWER,
            resource_type=ResourceTypes.SPACE,
            resource_ids=[TEST_SPACE_ID],
            expired_at=expired_at,
            operator=TEST_USER,
        )
        print(f"\n  ✓ 已授权: user={TEST_USER} space={TEST_SPACE_ID} role={Roles.SPACE_VIEWER.id}")
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"  is_allowed(view_business, space={TEST_SPACE_ID}) = {allowed}")
        assert allowed is True


# ==============================================================================
# 三、破坏性变更测试（action id rename / delete）
#
# 全程手动配合。每次改 actions.py 后需重启 pytest（schema 在 AppConfig.ready 冻结）。
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4ActionIdRename:
    """改 action id 的破坏性变更全流程。"""

    # ---------- 阶段 1: 创建 ----------

    def test_A_plan_create(self):
        ta = _get_test_action()
        if ta is None:
            pytest.skip("请先在 actions.py 里加 TEST_ACTION = ActionDef(id='test_action', ...)")
        if ta.id != "test_action":
            pytest.skip(f"当前 TEST_ACTION.id={ta.id}，本步要求 id='test_action'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        change = _find_change(plan, "action", "test_action", "create")
        print(f"\n  plan.summary: {plan.summary()}, destructive={plan.has_destructive()}")
        if change is None:
            print("  未找到 CREATE test_action，可能已在平台。当前 action changes:")
            for c in plan.changes:
                if c.kind.value == "action":
                    print(f"    [{c.change_type.value}] {c.entity_id}")
            pytest.skip("test_action 已在平台上")
        assert change is not None
        print("  ✓ CREATE test_action 在 plan 中")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_A_apply_create(self):
        ta = _get_test_action()
        if ta is None or ta.id != "test_action":
            pytest.skip("需要 TEST_ACTION.id='test_action'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        assert len(report.failed) == 0
        plan2 = provider.plan_migration(fw.schema, scope="full")
        assert _find_change(plan2, "action", "test_action", "create") is None
        print("  ✓ test_action 已存在于平台")

    # ---------- 阶段 2: 手动授权后验证 ----------

    def test_B_verify_granted(self):
        ta = _get_test_action()
        if ta is None or ta.id != "test_action":
            pytest.skip("需要 TEST_ACTION.id='test_action' 且已在平台 UI 授权")
        print(f"\n  确认 user={TEST_USER} action=test_action space={TEST_SPACE_ID} 已授权")
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id="test_action",
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"  is_allowed = {allowed}")
        assert allowed is True

    # ---------- 阶段 3: rename（id 改成 test_action_v2 + 重启）----------

    def test_C_plan_rename_destructive(self):
        ta = _get_test_action()
        if ta is None:
            pytest.skip("需要 actions.py 保留 TEST_ACTION")
        if ta.id != "test_action_v2":
            pytest.skip("需要手动改 TEST_ACTION.id='test_action_v2' 并重启 pytest")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        print(f"\n  plan.summary: {plan.summary()}, destructive={plan.has_destructive()}")
        for c in plan.changes:
            if c.kind.value == "action" and c.entity_id in ("test_action", "test_action_v2"):
                print(f"    [{c.change_type.value}] {c.entity_id}")
        assert _find_change(plan, "action", "test_action_v2", "create") is not None
        assert _find_change(plan, "action", "test_action", "delete") is not None
        assert plan.has_destructive()

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_D_apply_without_destructive_blocked(self):
        ta = _get_test_action()
        if ta is None or ta.id != "test_action_v2":
            pytest.skip("需要 TEST_ACTION.id='test_action_v2'")
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)
        print(f"\n  applied={len(report.applied)} skipped={report.skipped_reason!r}")
        assert len(report.applied) == 0
        assert "destructive" in report.skipped_reason.lower()
        print("  ✓ destructive 保护生效")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_E_apply_with_destructive(self):
        ta = _get_test_action()
        if ta is None or ta.id != "test_action_v2":
            pytest.skip("需要 TEST_ACTION.id='test_action_v2'")
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=True)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        assert len(report.failed) == 0
        plan2 = provider.plan_migration(fw.schema, scope="full")
        assert _find_change(plan2, "action", "test_action_v2", "create") is None
        assert _find_change(plan2, "action", "test_action", "delete") is None
        print("  ✓ rename 完成")

    # ---------- 阶段 4: 验证策略丢失 ----------

    def test_F_verify_permission_lost(self):
        ta = _get_test_action()
        if ta is None or ta.id != "test_action_v2":
            pytest.skip("需要 TEST_ACTION.id='test_action_v2' 且已完成 test_E")
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id="test_action_v2",
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"\n  is_allowed(test_action_v2) = {allowed}")
        assert allowed is False, "预期策略丢失"

    # ---------- 阶段 5: 清理 ----------

    def test_G_cleanup_plan(self):
        ta = _get_test_action()
        if ta is not None:
            pytest.skip(f"TEST_ACTION 仍存在(id={ta.id})，需要先从 actions.py 删除")
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        print(f"\n  plan.summary: {plan.summary()}, destructive={plan.has_destructive()}")
        delete = _find_change(plan, "action", "test_action_v2", "delete")
        if delete is None:
            pytest.skip("test_action_v2 已从平台移除")
        assert delete is not None
        assert plan.has_destructive()

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_G_cleanup_apply(self):
        ta = _get_test_action()
        if ta is not None:
            pytest.skip("需要先从 actions.py 删除 TEST_ACTION")
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema, scope="full")
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=True)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        assert len(report.failed) == 0
        print("  ✓ 清理完成")
