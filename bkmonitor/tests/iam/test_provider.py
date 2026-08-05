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
# IAM v4 Provider 全能力集成测试
#
# 执行顺序（从上到下，每步依赖前一步）：
#   1. 连通性检查
#   2. 查看迁移计划（plan，不执行）
#   3. dry-run 确认
#   4. 执行迁移（创建 system + resource_types + actions + roles）
#   5. 验证迁移结果
#   6. 单资源鉴权（resource-free / 有资源）
#   7. 批量资源鉴权
#   8. 批量 action 鉴权
#   9. 权限申请 URL
#
# 前置条件：.env 中配置好以下环境变量
#   BK_IAM_V4_API_BASE_URL = https://xxxxxxx
#   BK_IAM_V4_SYSTEM_ID = bk_monitor_v4
#   BK_IAM_APP_CODE = <your_app_code>
#   BK_IAM_APP_SECRET = <your_app_secret>
#   IAM_V4_TEST_USER = <your_username>  （可选）
#   IAM_V4_TEST_SPACE_ID = <space_id>   （可选）
#
# ==============================================================================

import os

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
from bkmonitor.iam.schema.actions import Actions
from bkmonitor.iam.schema.resource_types import ResourceTypes

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


# ==============================================================================
# 全生命周期测试（按 step1 → stepN 顺序执行）
# ==============================================================================


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4FullLifecycle:
    """IAM v4 Provider 全能力集成测试。"""

    # ================================================================
    # Step 1: 连通性检查
    # ================================================================

    def test_step1_health_check(self):
        """验证 IAM v4 API 连通性。系统未注册时返回 error 也视为连通正常。"""
        fw = get_framework()
        result = fw.providers["v4"].health_check()
        print(f"\n  health_check: status={result['status']} provider={result['provider']}")
        if result["status"] == "ok":
            print(f"  remote_id={result.get('remote_id')}")
        else:
            print(f"  error={result.get('error')}（系统可能尚未注册，正常）")

    # ================================================================
    # Step 2: 查看迁移计划
    # ================================================================

    def test_step2_plan_migration(self):
        """plan_migration — 比对本地 schema 与 IAM 远端，输出变更计划。"""
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        assert plan.provider_name == "v4"
        summary = plan.summary()
        print(
            f"\n  Migration plan: create={summary['create']} update={summary['update']} "
            f"delete={summary['delete']} noop={summary['noop']}"
        )
        print(f"  has_destructive={plan.has_destructive()}")
        if summary["create"] > 0:
            print("\n  待创建的实体（前 15 条）：")
            for c in plan.changes:
                if c.change_type.value == "create":
                    print(f"    + [{c.kind.value}] {c.entity_id}")
                    # noqa — 不然后续步骤无法执行
        if summary["update"] > 0:
            print("\n  待更新的实体（前 10 条）：")
            count = 0
            for c in plan.changes:
                if c.change_type.value == "update" and count < 10:
                    print(f"    ~ [{c.kind.value}] {c.entity_id}: {c.reason}")
                    count += 1

    # ================================================================
    # Step 3: dry-run
    # ================================================================

    def test_step3_apply_migration_dry_run(self):
        """dry_run 模式 — 仅列出将要执行的变更，不实际调用 IAM API。"""
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        report = provider.apply_migration(plan, dry_run=True, allow_destructive=True)
        assert report.provider_name == "v4"
        assert len(report.applied) == 0  # dry_run 不产生实际 applied
        print(f"\n  Would apply: {len(report.would_apply)} changes")
        print(f"  Failed: {len(report.failed)}")
        for c in report.would_apply[:20]:
            print(f"    > [{c.kind.value}] {c.change_type.value} {c.entity_id}")

    # ================================================================
    # Step 4: 执行迁移
    # ================================================================

    def test_step4_apply_migration(self):
        """真实执行迁移 — 在 IAM v4 平台上创建 system / resource_types / actions / roles。"""
        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        summary = plan.summary()
        print(f"\n  Plan: create={summary['create']} update={summary['update']} delete={summary['delete']}")

        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)
        print(f"  Applied: {len(report.applied)}")
        print(f"  Failed: {len(report.failed)}")
        print(f"  Elapsed: {report.elapsed_seconds:.1f}s")

        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.change_type.value} {c.entity_id}: {err[:200]}")

        assert len(report.failed) == 0, f"Migration had {len(report.failed)} failures"

    # ================================================================
    # Step 5: 验证迁移结果
    # ================================================================

    def test_step5_verify_migration(self):
        """迁移完成后：health_check 应为 ok，plan 应为全 noop。"""
        fw = get_framework()

        # 1. health_check 应返回 ok + system_id
        result = fw.providers["v4"].health_check()
        assert result["status"] == "ok"
        assert result["remote_id"] == SYSTEM_ID
        print(f"\n  health_check: ok, remote_id={result['remote_id']}")

        # 2. 再次 plan — 应该全部 noop
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        summary = plan.summary()
        print(
            f"  re-plan: create={summary['create']} update={summary['update']} "
            f"delete={summary['delete']} noop={summary['noop']}"
        )
        assert summary["create"] == 0, f"Still {summary['create']} entities to create"
        assert summary["delete"] == 0

    # ================================================================
    # Step 6: 单资源鉴权
    # ================================================================

    def test_step6_is_allowed_resource_free(self):
        """无资源 action 单次鉴权。"""
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_GLOBAL_SETTING.id,
            )
        )
        print(f"\n  user={TEST_USER} action={Actions.VIEW_GLOBAL_SETTING.id} allowed={allowed}")
        assert isinstance(allowed, bool)

    def test_step6_is_allowed_with_resource(self):
        """有资源 action 单次鉴权。"""
        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"\n  user={TEST_USER} action={Actions.VIEW_BUSINESS.id} space={TEST_SPACE_ID} allowed={allowed}")
        assert isinstance(allowed, bool)

    # ================================================================
    # Step 7: 批量资源鉴权
    # ================================================================

    def test_step7_batch_by_resource(self):
        """同 action，多个 space 批量鉴权。"""
        fw = get_framework()
        space_ids = [str(i) for i in range(1, 6)]
        result = fw.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resources=tuple(ResourceInstance(type=ResourceTypes.SPACE, id=sid) for sid in space_ids),
            )
        )
        print(f"\n  user={TEST_USER} action={Actions.VIEW_BUSINESS.id}")
        for item in result.items:
            print(f"    space={item.resource_id} allowed={item.allowed}")
        assert len(result.items) == len(space_ids)

    # ================================================================
    # Step 8: 批量 action 鉴权
    # ================================================================

    def test_step8_batch_by_action(self):
        """同 space，多个 action 批量鉴权。"""
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
        print(f"\n  user={TEST_USER} space={TEST_SPACE_ID}")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 5

    def test_step8_batch_by_action_resource_free(self):
        """多 resource-free action 批量鉴权（无资源）。"""
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
        print(f"\n  user={TEST_USER} (resource-free)")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 3

    # ================================================================
    # Step 9: 权限申请 URL
    # ================================================================

    def test_step9_get_apply_url(self):
        """生成权限申请 URL。"""
        fw = get_framework()
        print(f"TEST_USER: {TEST_USER}")
        print(f"TEST_SPACE_ID: {TEST_SPACE_ID}")
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.VIEW_BUSINESS.id],
                resources=(ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),),
            )
        )
        print(f"\n  apply_url for {Actions.VIEW_BUSINESS.id} on space={TEST_SPACE_ID}:")
        print(f"  {url}")
        assert isinstance(url, str)
        if url:
            assert url.startswith("http"), f"URL should start with http, got: {url}"

    # ================================================================
    # Step 10: 查询用户对某 action 有权限的资源列表
    # ================================================================

    def test_step10_get_authorized_resources_resource_free_returns_empty(self):
        """resource-free action：provider 前置拦截，直接返回 []（平台不支持该场景，会 400）。"""
        fw = get_framework()
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_GLOBAL_SETTING.id,
        )
        print(f"\n  get_authorized_resources(user={TEST_USER}, action={Actions.VIEW_GLOBAL_SETTING.id})")
        print(f"  result={result}  (resource-free action 应被前置拦截为 [])")
        assert result == []

    def test_step10_get_authorized_resources_view_business(self):
        """有资源 action：查用户对 view_business 有权限的 space 列表。

        期望 space id 已被 codec 解码回业务命名（纯数字或 "*"）。
        """
        fw = get_framework()
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_BUSINESS.id,
        )
        print(f"\n  get_authorized_resources(user={TEST_USER}, action={Actions.VIEW_BUSINESS.id})")
        for item in result:
            print(f"    type={item['type']} ids={item['ids']}")
        assert isinstance(result, list)
        # 校验 codec decode：space 的 id 不应带 "space|" 前缀
        for item in result:
            if item["type"] == ResourceTypes.SPACE.id:
                for rid in item["ids"]:
                    assert not rid.startswith("space|"), f"space id 应已 decode，实际='{rid}'"


# ==============================================================================
# 改 action id 破坏性验证（手动配合）
#
# 运行前置：TestIAMv4FullLifecycle 已跑完，v4 平台已存在完整 schema。
#
# 全流程（每次改 actions.py 后需重启 pytest 进程，schema 在 AppConfig.ready 冻结）：
#
#   阶段 1 —— actions.py 里保持:
#       TEST_ACTION = ActionDef(id="test_action", name="测试动作", resource_type="space")
#   跑:  test_A_plan_create           （只 plan，看到 CREATE test_action）
#        test_A_apply_create          （IAM_V4_APPLY=1 才真跑，把 test_action 迁移到平台）
#
#   阶段 2 —— 你手动去 v4 平台 UI，给 IAM_V4_TEST_USER 授权 test_action + space=TEST_SPACE_ID
#   跑:  test_B_verify_granted        （鉴权应通过，确保基线正确）
#
#   阶段 3 —— 你手动改 actions.py:
#       TEST_ACTION = ActionDef(id="test_action_v2", name="测试动作", resource_type="space")
#   *重启 pytest 进程*
#   跑:  test_C_plan_rename_destructive          （plan 应含 CREATE v2 + DELETE 旧，destructive=True）
#        test_D_apply_without_destructive_blocked（默认 allow_destructive=False → skipped）
#        test_E_apply_with_destructive           （IAM_V4_APPLY=1 才真跑，2 applied）
#
#   阶段 4 —— 验证策略丢失
#   跑:  test_F_verify_permission_lost           （用户对 test_action_v2 应无权限，UI 上 test_action 策略消失）
#
#   阶段 5 —— 清理：手动删除 actions.py 里的 TEST_ACTION 定义，重启 pytest
#   跑:  test_G_cleanup_plan                     （plan 应含 DELETE test_action_v2）
#        test_G_cleanup_apply                    （IAM_V4_APPLY=1 才真跑）
#
# 关键环境变量：
#   IAM_V4_APPLY=1     打开真实 apply 开关（不设置则所有 apply 步骤会被跳过）
# ==============================================================================


# 是否允许对真实 IAM 平台执行 apply
_APPLY_ENABLED = os.getenv("IAM_V4_APPLY", "").lower() in ("1", "true", "yes")
APPLY_SKIP_REASON = "未开启真实 apply（设置 IAM_V4_APPLY=1 才会执行）"


def _get_test_action():
    """动态取 Actions.TEST_ACTION，若未定义则返回 None（测试会 skip）。"""
    return getattr(Actions, "TEST_ACTION", None)


def _find_change(plan, kind_value: str, entity_id: str, change_type_value: str):
    """在 plan.changes 里查找匹配项，未找到返回 None。"""
    for c in plan.changes:
        if c.kind.value == kind_value and c.entity_id == entity_id and c.change_type.value == change_type_value:
            return c
    return None


@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4ActionIdRename:
    """改 action id 的破坏性变更全流程验证。"""

    # ================================================================
    # 阶段 1: 迁移 test_action 到平台
    # ================================================================

    def test_A_plan_create(self):
        """阶段 1: actions.py 已加 TEST_ACTION(id=test_action)，plan 应包含 CREATE。"""
        ta = _get_test_action()
        if ta is None:
            pytest.skip("请先在 actions.py 里加 TEST_ACTION = ActionDef(id='test_action', ...)")
        if ta.id != "test_action":
            pytest.skip(f"当前 TEST_ACTION.id={ta.id}，本步要求 id='test_action'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)

        change = _find_change(plan, "action", "test_action", "create")
        print(f"\n  plan.summary: {plan.summary()}")
        print(f"  destructive: {plan.has_destructive()}")
        if change is None:
            # 也许已经迁移过了；打印现有 changes 便于排查
            print("  未找到 CREATE test_action。当前 changes（action）：")
            for c in plan.changes:
                if c.kind.value == "action":
                    print(f"    [{c.change_type.value}] {c.entity_id}")
            pytest.skip("test_action 已在平台上，跳过（如需重测请到平台 UI 删除）")
        assert change is not None
        print("  ✓ CREATE test_action 待应用")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_A_apply_create(self):
        """阶段 1: 真实 apply，把 test_action 迁移到 v4 平台。"""
        ta = _get_test_action()
        if ta is None or ta.id != "test_action":
            pytest.skip("需要 actions.py 里 TEST_ACTION.id='test_action'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)

        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.change_type.value} {c.entity_id}: {err[:200]}")
        assert len(report.failed) == 0

        # 再次 plan，应该 test_action 不再在 create 列表里
        plan2 = provider.plan_migration(fw.schema)
        assert _find_change(plan2, "action", "test_action", "create") is None
        print("  ✓ test_action 已存在于平台")

    # ================================================================
    # 阶段 2: 你手动授权后，验证基线
    # ================================================================

    def test_B_verify_granted(self):
        """阶段 2 后手动跑: 你已在平台 UI 给 admin 授了 test_action + space=TEST_SPACE_ID。

        手动步骤：
          1. 登陆 v4 权限中心 UI
          2. 进入 bk_monitor_v4 系统
          3. 给用户 `{TEST_USER}` 授权：操作=测试动作(test_action)，资源=space id={TEST_SPACE_ID}
          4. 提交后跑本用例
        """
        ta = _get_test_action()
        if ta is None or ta.id != "test_action":
            pytest.skip("需要 actions.py 里 TEST_ACTION.id='test_action'")

        print("\n  确认手动授权已完成:")
        print(f"    user={TEST_USER}")
        print("    action=test_action")
        print(f"    resource=space:{TEST_SPACE_ID}")

        fw = get_framework()
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id="test_action",
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"  is_allowed(test_action, space={TEST_SPACE_ID}) = {allowed}")
        assert allowed is True, "预期已授权→allowed=True。若为 False，检查平台 UI 授权是否生效、TEST_USER 是否正确。"

    # ================================================================
    # 阶段 3: 你手动把 id 改成 test_action_v2 并重启 pytest 后
    # ================================================================

    def test_C_plan_rename_destructive(self):
        """阶段 3: id 改为 test_action_v2 后重启 pytest，plan 应 CREATE 新 + DELETE 旧。"""
        ta = _get_test_action()
        if ta is None:
            pytest.skip("需要 actions.py 保留 TEST_ACTION")
        if ta.id != "test_action_v2":
            pytest.skip(f"当前 TEST_ACTION.id={ta.id}，本步要求手动改成 'test_action_v2' 并重启 pytest")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        print(f"\n  plan.summary: {plan.summary()}")
        print(f"  destructive: {plan.has_destructive()}")

        # 打印 action 相关 changes
        print("  action 变更:")
        for c in plan.changes:
            if c.kind.value == "action" and c.entity_id in ("test_action", "test_action_v2"):
                print(f"    [{c.change_type.value}] {c.entity_id}")

        create = _find_change(plan, "action", "test_action_v2", "create")
        delete = _find_change(plan, "action", "test_action", "delete")
        assert create is not None, "期望有 CREATE test_action_v2"
        assert delete is not None, "期望有 DELETE test_action（老 id 从远端消失）"
        assert plan.has_destructive() is True, "含 DELETE 时应视为 destructive"

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_D_apply_without_destructive_blocked(self):
        """阶段 3: 默认 allow_destructive=False，含 DELETE 的 plan 会被 skip。"""
        ta = _get_test_action()
        if ta is None or ta.id != "test_action_v2":
            pytest.skip("需要 TEST_ACTION.id='test_action_v2'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=False)
        print(f"\n  applied={len(report.applied)} skipped_reason={report.skipped_reason!r}")
        assert len(report.applied) == 0
        assert report.skipped_reason and "destructive" in report.skipped_reason.lower()
        print("  ✓ destructive 保护生效")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_E_apply_with_destructive(self):
        """阶段 3: 加 allow_destructive=True，真跑 CREATE test_action_v2 + DELETE test_action。"""
        ta = _get_test_action()
        if ta is None or ta.id != "test_action_v2":
            pytest.skip("需要 TEST_ACTION.id='test_action_v2'")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=True)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.change_type.value} {c.entity_id}: {err[:200]}")
        assert len(report.failed) == 0

        # 再次 plan：应无 test_action / test_action_v2 相关 create / delete
        plan2 = provider.plan_migration(fw.schema)
        assert _find_change(plan2, "action", "test_action_v2", "create") is None
        assert _find_change(plan2, "action", "test_action", "delete") is None
        print("  ✓ 平台已完成 rename（本质：删旧建新）")

    # ================================================================
    # 阶段 4: 验证策略确实丢失
    # ================================================================

    def test_F_verify_permission_lost(self):
        """阶段 4: rename 后，之前对 test_action 授的权不应自动继承到 test_action_v2。

        手动步骤：
          1. 到 v4 平台 UI 查看用户 `{TEST_USER}` 的策略
          2. 之前的 test_action 那条策略应已消失（因为对应 action 被删除）
          3. 用户对 test_action_v2 应无权限（需要重新授权）
        """
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
        print(f"\n  is_allowed(test_action_v2, space={TEST_SPACE_ID}) = {allowed}")
        print(f"  →请到平台 UI 确认: {TEST_USER} 的 test_action 策略应已消失")
        assert allowed is False, "预期策略丢失→allowed=False。若为 True，说明平台自动继承了策略（不符合预期）。"

    # ================================================================
    # 阶段 5: 清理
    # ================================================================

    def test_G_cleanup_plan(self):
        """阶段 5: 手动删除 actions.py 的 TEST_ACTION 后重启 pytest，plan 应含 DELETE test_action_v2。"""
        ta = _get_test_action()
        if ta is not None:
            pytest.skip(
                f"检测到 Actions.TEST_ACTION 仍存在(id={ta.id})；清理阶段应先在 actions.py 里删除 TEST_ACTION 定义"
            )

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        print(f"\n  plan.summary: {plan.summary()}")
        print(f"  destructive: {plan.has_destructive()}")

        delete = _find_change(plan, "action", "test_action_v2", "delete")
        if delete is None:
            # 可能已经 apply 过；打印现有 changes
            print("  未找到 DELETE test_action_v2，当前 action changes:")
            for c in plan.changes:
                if c.kind.value == "action":
                    print(f"    [{c.change_type.value}] {c.entity_id}")
            pytest.skip("test_action_v2 已从平台移除，无需再 apply")
        assert delete is not None
        assert plan.has_destructive() is True

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_G_cleanup_apply(self):
        """阶段 5: 真实 apply，删除平台上的 test_action_v2。"""
        ta = _get_test_action()
        if ta is not None:
            pytest.skip("需要先从 actions.py 里删除 TEST_ACTION 定义并重启 pytest")

        fw = get_framework()
        provider = fw.providers["v4"]
        plan = provider.plan_migration(fw.schema)
        report = provider.apply_migration(plan, dry_run=False, allow_destructive=True)
        print(f"\n  applied={len(report.applied)} failed={len(report.failed)}")
        for c in report.applied:
            print(f"    ✓ [{c.kind.value}] {c.change_type.value} {c.entity_id}")
        for c, err in report.failed:
            print(f"    ✗ [{c.kind.value}] {c.change_type.value} {c.entity_id}: {err[:200]}")
        assert len(report.failed) == 0
        print("  ✓ 清理完成")
