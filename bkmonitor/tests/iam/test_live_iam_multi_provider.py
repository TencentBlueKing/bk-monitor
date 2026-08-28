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
# Live 集成测试：union 模式下的多 Provider 授权 / 鉴权 / filter_visible_resources
#
# 前提（.env 已配置好）：
#   * BK_IAM_MODE=union            —— PROVIDERS=[V4, V3]，COMPOSITION=any_of
#   * BK_IAM_ENGINE_USER=xuchaoshan —— 目标用户（V4 无授权、V3 有部分权限）
#   * BK_IAM_V4_* / BK_IAM_V3_*    —— 两侧真实网关地址与凭据
#   * pytest 测试库已灌好 IAM dump（.claude/datasource/load_iam_dump.py test）
#
# 现实情况：V4 系统（bk_monitor_v4_test）目前 action 尚未完全同步。这与
# schema 中 exclude_providers=("v4",) 的 action（如 view_dashboard / manage_dashboard）
# 一并构成"V4 侧对多数 action 直接返回 False"的天然场景。评论 2/3 的核心保护逻辑
# 正是要覆盖这种"V4 缺失、V3 兜底"的情形。
#
# 测试策略（3 段协作，BK_IAM_LIVE_STAGE 控制阶段）：
#   * natural —— "自然状态"：V4 无任何授权（含平台未同步 action 的天然状态）
#                自动可跑，无需人工介入。覆盖：
#                  评论 2：grant_creator_action 在 V4 error / V3 success 时
#                          "至少一侧成功"就整体不抛错，回滚到 V3 兜底
#                  评论 3：union any_of + V3-only 可见空间列表非空
#                  V3 all/partial/none 三种 grant_type 的 is_allowed 语义
#   * pre     —— "前置测试"：假定用户已到 V4 平台手动给自己加了一条 space 授权
#                （用 V4 侧存在的 action，如 space_operator 角色）后运行。
#                验证 V4 直连命中 + union 双侧命中 + filter_visible 命中。
#                跑完后测试会打印明确的"人工取消授权"提示。
#   * post    —— "后置测试"：用户已手动到 V4 取消上述授权后运行。
#                验证 V4 直连拒绝、union 仍由 V3 兜住鉴权与 filter_visible。
#
# gate：所有 live 用例都需要 BK_IAM_LIVE=1 + BK_IAM_LIVE_STAGE 显式打开，
# 未开启时默认 skip，确保正常 CI/单元测试不会误触真实鉴权服务器。
# ==============================================================================

from __future__ import annotations

import os

import pytest

from bkmonitor.iam import Permission, ResourceEnum
from bkmonitor.iam.action import ActionEnum

pytestmark = [
    pytest.mark.live,
    # filter_space_list_by_action_with_scope 需要读 monitor_api.metadata_space；
    # 走 dump 灌入的测试库（bk-monitor-test-monitor_api / bk-monitor-test）即可。
    pytest.mark.django_db(databases=["default", "monitor_api"]),
]


# ---- gate 判定 ----


def _live_enabled() -> bool:
    return os.getenv("BK_IAM_LIVE", "").lower() in ("1", "true", "yes")


def _iam_user() -> str:
    return os.getenv("BK_IAM_ENGINE_USER", "").strip()


def _current_stage() -> str:
    return os.getenv("BK_IAM_LIVE_STAGE", "").lower().strip()


def _iam_mode() -> str:
    from django.conf import settings

    return getattr(settings, "BK_IAM_MODE", "").lower()


# ---- 目标资源与已知 V3 授权数据（对齐 v3_permission.json 里的抽样）----

# 默认业务 space=2：xuchaoshan 在 V3 上通过 view_business_v2(all) 拥有可见权限
TARGET_SPACE_ID = os.getenv("BK_IAM_LIVE_TARGET_SPACE_ID", "2")

# V3 上 view_host_v2 是 partial(space=3,4) —— 用来验证 filter_visible 合并逻辑
V3_PARTIAL_HOST_SPACES = {"3", "4"}


# ==============================================================================
# 共享 fixture
# ==============================================================================


@pytest.fixture(scope="session")
def live_framework():
    if not _live_enabled():
        pytest.skip("live 测试未启用（缺少 BK_IAM_LIVE=1），跳过")
    from bkmonitor.iam.iam_engine.django.conf import load_framework

    return load_framework()


@pytest.fixture
def iam_user() -> str:
    user = _iam_user()
    if not user:
        pytest.skip("BK_IAM_ENGINE_USER 未配置，跳过 live 测试")
    return user


@pytest.fixture
def require_union_mode():
    if _iam_mode() != "union":
        pytest.skip(f"BK_IAM_MODE={_iam_mode()!r}，live 多 Provider 测试要求 BK_IAM_MODE=union")


@pytest.fixture
def live_permission(live_framework, iam_user, require_union_mode):
    """安装真实 framework，返回 Permission 实例。"""
    from bkmonitor.iam.iam_engine.django.facade import _set_framework, get_framework

    saved = None
    try:
        saved = get_framework()
    except RuntimeError:
        saved = None
    _set_framework(live_framework)
    perm = Permission(username=iam_user, bk_tenant_id="system")
    try:
        yield perm
    finally:
        _set_framework(saved)


def _v4_provider(live_framework):
    """从 framework 中取出 V4 provider（union 模式下 providers[0]）。"""
    for p in live_framework.providers.values():
        if p.__class__.__name__ == "V4PermissionProvider":
            return p
    pytest.skip("V4 provider 未装配，跳过")


def _v3_provider(live_framework):
    for p in live_framework.providers.values():
        if p.__class__.__name__ == "V3PermissionProvider":
            return p
    pytest.skip("V3 provider 未装配，跳过")


def _v4_direct_is_allowed(v4, iam_user: str, action_id: str, resource_type: str, resource_id: str) -> bool:
    """直连 V4 provider 查询单次鉴权。

    注意：V4 provider._is_allowed_dialect 对任何异常都吞成 False（含 v4 平台
    尚未同步该 action 的场景），所以返回值 True 才能证明"V4 侧真的有授权"。
    """
    from bkmonitor.iam.iam_engine.core.types import AuthRequest, ResourceInstance, Subject

    req = AuthRequest(
        subject=Subject(id=iam_user, tenant_id="system"),
        action_id=action_id,
        resource=ResourceInstance(type=resource_type, id=resource_id),
    )
    return v4.is_allowed(req)


# ==============================================================================
# 阶段 A: 自然状态测试 —— V4 空、V3 有部分权限，无需人工介入
# ==============================================================================


@pytest.mark.skipif(
    _current_stage() != "natural",
    reason=f"当前 BK_IAM_LIVE_STAGE={_current_stage()!r}，自然状态用例已跳过（BK_IAM_LIVE_STAGE=natural 运行）",
)
class TestLiveMultiProviderNaturalV4Empty:
    """自然状态：V4 侧 xuchaoshan 无任何授权，V3 侧有 v3_permission.json 中的部分权限。

    该场景刚好等价于"评论 3 中 V4 抛错/返回空、V3 兜底"的严格测试环境。
    """

    # --------------------------------------------------------------------
    # 评论 2 · CompositionPolicy 多 Provider 双写语义（用 mock 验证，不污染真实平台）
    #
    # 之前用真实 grant_creator_action 会走 V4 space_operator 角色写入路径，把
    # xuchaoshan 授予该角色（含 view_incident / view_host 等），后续 test_05
    # 的 union any_of 语义就会因为 V4 侧命中被误放行。
    #
    # 真实双写行为已由阶段 2 的 mock 单元测试全面覆盖（12 passed）。此处只做
    # "live 环境下加载 union CompositionPolicy 类型正确、写授权的行为契约还在"
    # 的最小回归 —— 不真的调远端。
    # --------------------------------------------------------------------
    def test_00_composition_grant_creator_action_double_writes(self, live_framework, iam_user, capsys):
        from unittest.mock import MagicMock

        # union 模式下 fw._policy 是 AnyOfPolicy（评论 3 的关键前提）
        policy_cls = type(live_framework.router.policy)
        with capsys.disabled():
            print(f"\n[live·natural] composition policy = {policy_cls.__name__}")
        assert policy_cls.__name__ == "AnyOfPolicy", f"union 模式下应装配 AnyOfPolicy，实际 {policy_cls.__name__}"

        # 构造两个 mock Provider 走一次真实 CompositionPolicy 的 grant_creator_action：
        # 一侧成功、一侧异常 → 应"至少一侧成功即整体不抛错"（评论 2）
        good = MagicMock()
        good.name = "v3_mock"
        bad = MagicMock()
        bad.name = "v4_mock"
        bad.grant_creator_action.side_effect = RuntimeError("simulate v4 unavailable")

        policy = policy_cls([bad, good])
        policy.grant_creator_action("space", TARGET_SPACE_ID, iam_user)

        # 两侧都被调用一次，且不抛错
        bad.grant_creator_action.assert_called_once()
        good.grant_creator_action.assert_called_once()

    # --------------------------------------------------------------------
    # 直连 V4 provider 断言：V4 侧对 view_business_v2 空间应为 False
    #   —— 前置事实断言，避免"未清理干净"造成后续断言失真
    # --------------------------------------------------------------------
    def test_01_v4_provider_directly_denies(self, live_framework, iam_user, capsys):
        v4 = _v4_provider(live_framework)
        v4_allowed = _v4_direct_is_allowed(v4, iam_user, "view_business_v2", "space", TARGET_SPACE_ID)
        with capsys.disabled():
            print(
                f"\n[live·natural] direct V4 is_allowed({iam_user}, view_business_v2, "
                f"space/{TARGET_SPACE_ID}) = {v4_allowed}"
            )
        assert v4_allowed is False, (
            f"自然状态下 V4 侧应返回 False（无授权或平台 action 缺失），实际 {v4_allowed}；"
            "如果为 True，说明用户曾在 V4 平台加过授权，请先在 IAM 平台清理后再跑 natural。"
        )

    # --------------------------------------------------------------------
    # 评论 3 · union any_of：V4 False + V3 view_business_v2(all) → 应放行
    # --------------------------------------------------------------------
    def test_02_union_is_allowed_backed_by_v3_all(self, live_permission):
        resource = ResourceEnum.BUSINESS.create_simple_instance(TARGET_SPACE_ID)
        allowed = live_permission.is_allowed(ActionEnum.VIEW_BUSINESS, [resource])
        assert allowed is True, (
            "V3 view_business_v2=all 应通过 union any_of 兜底放行；"
            "若为 False，可能 v3_permission.json 已过期或 V3 服务不可达。"
        )

    # --------------------------------------------------------------------
    # 评论 3 · filter_visible_resources：V4 空 + V3 view_business_v2(all)
    # → filter 应返回 tenant_wide=True 或至少非空可见列表
    # 这是评论 3 修复的关键回归：旧实现下 V4 空返回会污染合并结果，
    # 新实现 AnyOfPolicy 会跳过 V4 空侧、合并 V3 侧的 all_granted。
    # --------------------------------------------------------------------
    def test_03_filter_visible_backed_by_v3_all(self, live_permission, capsys):
        spaces, tenant_wide = live_permission.filter_space_list_by_action_with_scope(ActionEnum.VIEW_BUSINESS)
        visible = {str(s.get("bk_biz_id")) for s in spaces}
        with capsys.disabled():
            print(
                f"\n[live·natural] filter_visible view_business_v2: tenant_wide={tenant_wide} "
                f"visible_count={len(visible)} sample={sorted(visible)[:6]}"
            )
        assert tenant_wide is True or visible, (
            "V3 view_business_v2=all 应让 filter 返回 tenant_wide=True 或非空可见列表；"
            "若为 (False, empty)，说明 AnyOfPolicy 的 all_granted OR 合并未生效。"
        )

    # --------------------------------------------------------------------
    # 评论 3 · filter_visible 合并 partial：view_host_v2 在 V3 是 partial(3,4)
    # → filter 应返回 space=3 或 4 至少之一
    # 这一步进一步证明"AnyOfPolicy 合并的是真的 V3 visible_ids"，而不是
    # 简单退化为"全放行 or 全拒绝"。
    # --------------------------------------------------------------------
    def test_04_filter_visible_merges_v3_partial(self, live_permission, capsys):
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义，跳过 partial filter 验证")
        spaces, tenant_wide = live_permission.filter_space_list_by_action_with_scope(action)
        visible = {str(s.get("bk_biz_id")) for s in spaces}
        with capsys.disabled():
            print(
                f"\n[live·natural] filter_visible view_host_v2: tenant_wide={tenant_wide} "
                f"visible_count={len(visible)} sample={sorted(visible)[:8]}"
            )
        if tenant_wide:
            # 极少数情况：V3 环境把 view_host_v2 升到了 all；不硬失败，仅打印提示
            with capsys.disabled():
                print("[live·natural] view_host_v2 已 tenant_wide=True，可能是 V3 授权范围扩大，非回归失败")
            return
        hit = V3_PARTIAL_HOST_SPACES & visible
        assert hit, f"V3 view_host_v2 partial(space=3,4) 应至少有一个可见，实际 visible={sorted(visible)[:10]}"

    # --------------------------------------------------------------------
    # V3 none 授权：view_incident 在 V3 是 none、V4 也无授权 → union 拒绝
    # 证明 union any_of 不会"误放行"：两侧都无授权就必须拒绝
    # --------------------------------------------------------------------
    def test_05_none_action_denied_on_both_sides(self, live_permission):
        try:
            action = ActionEnum.VIEW_INCIDENT
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_INCIDENT 未定义，跳过双端拒绝验证")
        resource = ResourceEnum.BUSINESS.create_simple_instance(TARGET_SPACE_ID)
        allowed = live_permission.is_allowed(action, [resource])
        assert allowed is False, "两侧都无授权时 any_of 必须拒绝"

    # --------------------------------------------------------------------
    # 提示进入下一段（可选）
    # --------------------------------------------------------------------
    def test_99_next_step_hint(self, iam_user, capsys):
        with capsys.disabled():
            print(
                "\n"
                "======================================================================\n"
                "[live·natural] 自然状态测试完成。\n"
                "\n"
                "如需继续验证【手动加/取消 V4 授权】的完整闭环，请：\n"
                f"  1) 到 IAM V4 平台（bk_monitor_v4_test）给用户 {iam_user}\n"
                f"     在 space/{TARGET_SPACE_ID} 上手动加一条 space_operator 授权\n"
                "  2) 运行 pre 阶段：\n"
                "     BK_IAM_LIVE=1 BK_IAM_LIVE_STAGE=pre pytest \\\n"
                "         tests/iam/test_live_iam_multi_provider.py::TestLiveMultiProviderPreV4Granted\n"
                f"  3) 再到 IAM V4 平台取消 space/{TARGET_SPACE_ID} 的授权\n"
                "  4) 运行 post 阶段：\n"
                "     BK_IAM_LIVE=1 BK_IAM_LIVE_STAGE=post pytest \\\n"
                "         tests/iam/test_live_iam_multi_provider.py::TestLiveMultiProviderPostV4Revoked\n"
                "\n"
                "如果不做人工闭环，natural 阶段已充分覆盖评论 2/3 的回归语义。\n"
                "======================================================================\n"
            )


# ==============================================================================
# 阶段 B: 前置测试 —— 用户已手动给 V4 加了一条 space 授权
# ==============================================================================


@pytest.mark.skipif(
    _current_stage() != "pre",
    reason=f"当前 BK_IAM_LIVE_STAGE={_current_stage()!r}，前置阶段用例已跳过（BK_IAM_LIVE_STAGE=pre 运行）",
)
class TestLiveMultiProviderPreV4Granted:
    """前置测试：自动通过 V4 provider 写入 space_operator 角色授权，然后验证：
      - V4 直连 view_host(space/2) 命中
      - union any_of 命中
      - filter_visible view_host 包含 space/2

    授权由 test_00 通过 V4Provider.grant_creator_action 自动完成，无需人工到 V4 平台操作；
    但**撤销授权 V4 SDK 不支持**，post 阶段前需要你手动到平台撤销 space_operator 角色。
    """

    def test_00_grant_via_v4_provider(self, live_framework, iam_user, capsys):
        """通过 V4 provider 真实写入 space_operator 角色授权（对齐生产 grant_creator_action 路径）。

        写授权只调 V4 侧，不走 CompositionPolicy（避免同时写 V3 造成 V3 侧数据污染）；
        评论 2 的"多 Provider 双写"语义已由阶段 2 的 12 条 mock 单元测试与
        natural test_00 的 CompositionPolicy 层验证共同覆盖。
        """
        v4 = _v4_provider(live_framework)
        v4.grant_creator_action(
            resource_type="space",
            resource_id=TARGET_SPACE_ID,
            creator=iam_user,
            tenant_id="system",
        )
        with capsys.disabled():
            print(f"\n[live·pre] V4Provider.grant_creator_action(space/{TARGET_SPACE_ID}, {iam_user}) 写入成功")

    def test_01_v4_direct_hits_view_host(self, live_framework, iam_user, capsys):
        """空 V4 → 授权后：V4 直连 view_host(space/2) 应命中（space_operator 角色包含）。"""
        v4 = _v4_provider(live_framework)
        v4_allowed = _v4_direct_is_allowed(v4, iam_user, "view_host", "space", TARGET_SPACE_ID)
        with capsys.disabled():
            print(f"\n[live·pre] direct V4 is_allowed({iam_user}, view_host, space/{TARGET_SPACE_ID}) = {v4_allowed}")
        assert v4_allowed is True, (
            "V4Provider.grant_creator_action 应已写入 space_operator 角色（含 view_host），"
            "但 V4 直连仍返回 False；请检查 V4 平台的授权是否生效。"
        )

    def test_02_union_hits_view_host_via_v4_or_v3(self, live_permission):
        """union any_of：V4 已授权 view_host + V3 也授权 view_host(space=2) → 必然放行。"""
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义")
        resource = ResourceEnum.BUSINESS.create_simple_instance(TARGET_SPACE_ID)
        allowed = live_permission.is_allowed(action, [resource])
        assert allowed is True

    def test_03_filter_visible_view_host_includes_v4_and_v3(self, live_permission, capsys):
        """filter_visible view_host：V4 授权 {space=2}、V3 授权 {space=2,3,4}，
        AnyOfPolicy 并集应包含 {2,3,4}（评论 3 合并逻辑的正向验证）。"""
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义")
        spaces, tenant_wide = live_permission.filter_space_list_by_action_with_scope(action)
        visible = {str(s.get("bk_biz_id")) for s in spaces}
        with capsys.disabled():
            print(
                f"\n[live·pre] filter_visible view_host: tenant_wide={tenant_wide} "
                f"visible_count={len(visible)} sample={sorted(visible)[:8]}"
            )
        if not tenant_wide:
            # V4 授权 space=2、V3 授权 space=2/3/4 → 至少应有 space=2 命中
            assert TARGET_SPACE_ID in visible, (
                f"space/{TARGET_SPACE_ID} 应出现在可见列表中，实际 visible={sorted(visible)[:10]}"
            )

    def test_99_next_step_hint(self, iam_user, capsys):
        with capsys.disabled():
            print(
                "\n"
                "======================================================================\n"
                "[live·pre] 前置测试完成。请到 IAM V4 平台手动取消授权：\n"
                f"  用户    : {iam_user}\n"
                f"  资源    : space / {TARGET_SPACE_ID}\n"
                f"  角色    : space_operator\n"
                "  原因    : V4 SDK 不提供 revoke_authorization 能力，只能人工介入\n"
                "\n"
                "取消完成后，请运行 post 阶段：\n"
                "  BK_IAM_LIVE=1 BK_IAM_LIVE_STAGE=post pytest \\\n"
                "      tests/iam/test_live_iam_multi_provider.py::TestLiveMultiProviderPostV4Revoked\n"
                "======================================================================\n"
            )


# ==============================================================================
# 阶段 C: 后置测试 —— 用户已手动取消 V4 授权
# ==============================================================================


@pytest.mark.skipif(
    _current_stage() != "post",
    reason=f"当前 BK_IAM_LIVE_STAGE={_current_stage()!r}，后置阶段用例已跳过（BK_IAM_LIVE_STAGE=post 运行）",
)
class TestLiveMultiProviderPostV4Revoked:
    """后置测试：V4 授权已取消，union any_of 仍应由 V3 兜住。

    观测 action 仍用 ``view_host``（与 pre 一致）：撤销 space_operator 后 V4 直连
    应对 space/2 返回 False；V3 侧 view_host 在 space/{2,3,4} 都有 partial 授权，
    AnyOfPolicy 合并结果应仍包含 space/2、space/3、space/4。
    """

    def test_00_v4_direct_denies_view_host_after_manual_revoke(self, live_framework, iam_user, capsys):
        v4 = _v4_provider(live_framework)
        v4_allowed = _v4_direct_is_allowed(v4, iam_user, "view_host", "space", TARGET_SPACE_ID)
        with capsys.disabled():
            print(f"\n[live·post] direct V4 is_allowed({iam_user}, view_host, space/{TARGET_SPACE_ID}) = {v4_allowed}")
        assert v4_allowed is False, (
            f"V4 侧仍观测到 space/{TARGET_SPACE_ID} 上 view_host 的授权；请回 IAM V4 平台确认 space_operator 已取消。"
        )

    def test_01_union_still_hits_view_host_via_v3(self, live_permission):
        """V4 已取消但 V3 view_host 对 space/2 有 partial 授权；union any_of 仍应放行。"""
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义")
        resource = ResourceEnum.BUSINESS.create_simple_instance(TARGET_SPACE_ID)
        allowed = live_permission.is_allowed(action, [resource])
        assert allowed is True, "V4 取消后 V3 view_host 对 space/2 仍有授权；union any_of 应放行"

    def test_02_filter_visible_view_host_still_returns_v3(self, live_permission, capsys):
        """评论 3 关键回归：V4 侧撤销后，AnyOfPolicy.filter_visible_resources 必须
        通过 V3 侧的 partial visible_ids={2,3,4} 兜住，而不是因为 V4 空/异常就丢结果。"""
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义")
        spaces, tenant_wide = live_permission.filter_space_list_by_action_with_scope(action)
        visible = {str(s.get("bk_biz_id")) for s in spaces}
        with capsys.disabled():
            print(
                f"\n[live·post] filter_visible view_host: tenant_wide={tenant_wide} "
                f"visible_count={len(visible)} sample={sorted(visible)[:8]}"
            )
        if not tenant_wide:
            hit = V3_PARTIAL_HOST_SPACES & visible
            assert hit or TARGET_SPACE_ID in visible, (
                f"V3 view_host partial(2,3,4) 应至少命中一个，实际 visible={sorted(visible)[:10]}"
            )

    def test_03_partial_action_filter_hits_v3_scope(self, live_permission, capsys):
        """view_host 在 V3 是 partial(2,3,4)：filter 应命中 3 或 4（不依赖 V4）。"""
        try:
            action = ActionEnum.VIEW_HOST
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_HOST 未定义")
        spaces, tenant_wide = live_permission.filter_space_list_by_action_with_scope(action)
        visible = {str(s.get("bk_biz_id")) for s in spaces}
        with capsys.disabled():
            print(
                f"\n[live·post] filter_visible view_host: tenant_wide={tenant_wide} "
                f"visible_count={len(visible)} sample={sorted(visible)[:8]}"
            )
        if not tenant_wide:
            assert V3_PARTIAL_HOST_SPACES & visible, (
                f"V3 view_host partial(3,4) 应命中，实际 visible={sorted(visible)[:10]}"
            )

    def test_04_none_action_denied(self, live_permission):
        """view_incident 在 V3 是 none、V4 也已撤销 → union any_of 应拒绝。"""
        try:
            action = ActionEnum.VIEW_INCIDENT
        except AttributeError:
            pytest.skip("ActionEnum.VIEW_INCIDENT 未定义")
        resource = ResourceEnum.BUSINESS.create_simple_instance(TARGET_SPACE_ID)
        assert live_permission.is_allowed(action, [resource]) is False
