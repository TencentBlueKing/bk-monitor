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
#   BK_IAM_V4_API_BASE_URL = https://bkiam.apigw.o.woa.com/prod
#   BK_IAM_V4_SYSTEM_ID = bk_monitor_v4
#   BK_IAM_APP_CODE = <your_app_code>
#   BK_IAM_APP_SECRET = <your_app_secret>
#   IAM_V4_TEST_USER = <your_username>  （可选，默认 admin）
#   IAM_V4_TEST_SPACE_ID = <space_id>   （可选，默认 1）
#
# 逐步执行：
#   pytest tests/iam/test_provider.py::TestIAMv4FullLifecycle::step1_health_check -xvs
#   pytest tests/iam/test_provider.py::TestIAMv4FullLifecycle::step2_plan_migration -xvs
#   pytest tests/iam/test_provider.py::TestIAMv4FullLifecycle::step3_apply_migration_dry_run -xvs
#   pytest tests/iam/test_provider.py::TestIAMv4FullLifecycle::step4_apply_migration -xvs
#   ... 以此类推
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
TEST_SPACE_ID = os.getenv("IAM_V4_TEST_SPACE_ID", "1")
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
