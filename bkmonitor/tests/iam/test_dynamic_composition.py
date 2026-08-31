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
# 08-28 框架决策 · DynamicCompositionPolicy 单元测试
#
# 覆盖：
#   1. selector 返回已注册 key → 委托到候选池对应 policy
#   2. selector 返回未注册 key → 走 fallback
#   3. selector 抛异常 → 走 fallback
#   4. selector 返回大小写 / 空串 / None → 规范化后走 fallback
#   5. 写授权（grant_creator_action）与展示（get_apply_url）走基类固定语义，
#      与 selector / mode 无关（对所有 provider 扇出 / 走 primary()）
#   6. 构造契约：policies 为空 或 fallback_key 不在 policies 中 → ValueError
#
# 设计原则：框架层测试严格不依赖 Django；构造 mock provider 与 mock
# CompositionPolicy 子策略，验证委托关系。
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy
from bkmonitor.iam.iam_engine.provider.composition.dynamic import DynamicCompositionPolicy


# ------------------------------------------------------------------
# 测试脚手架
# ------------------------------------------------------------------


def _make_provider(name: str) -> MagicMock:
    p = MagicMock()
    p.name = name
    return p


def _make_sub_policy(tag: str) -> MagicMock:
    """构造一个 mock CompositionPolicy 子策略：所有接口返回可追踪的哨兵值。"""
    m = MagicMock(spec=CompositionPolicy)
    m.tag = tag
    # 用 tag 作为返回值哨兵，便于断言哪个子策略被调用
    m.is_allowed.return_value = f"{tag}:is_allowed"
    m.batch_by_resource.return_value = f"{tag}:batch_by_resource"
    m.batch_by_action.return_value = f"{tag}:batch_by_action"
    m.filter_visible_resources.return_value = f"{tag}:filter_visible"
    m.query_policies.return_value = [f"{tag}:policy_expr"]
    m.query_policies_by_actions.return_value = {"a": [f"{tag}:policy_expr"]}
    m.has_any_permission.return_value = True
    return m


@pytest.fixture()
def providers() -> list[MagicMock]:
    return [_make_provider("a"), _make_provider("b")]


@pytest.fixture()
def policies() -> dict[str, MagicMock]:
    return {
        "alpha": _make_sub_policy("alpha"),
        "beta": _make_sub_policy("beta"),
    }


# ------------------------------------------------------------------
# 1. selector 命中 → 委托
# ------------------------------------------------------------------


class TestSelectorDelegation:
    """selector 返回合法 key 时，各读鉴权接口都应精准委托到对应子策略。"""

    def test_is_allowed_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        request = MagicMock()
        assert dyn.is_allowed(request) == "alpha:is_allowed"
        policies["alpha"].is_allowed.assert_called_once_with(request)
        policies["beta"].is_allowed.assert_not_called()

    def test_batch_by_resource_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "beta",
            policies=policies,
            fallback_key="alpha",
        )
        request = MagicMock()
        assert dyn.batch_by_resource(request) == "beta:batch_by_resource"
        policies["beta"].batch_by_resource.assert_called_once_with(request)
        policies["alpha"].batch_by_resource.assert_not_called()

    def test_batch_by_action_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        request = MagicMock()
        assert dyn.batch_by_action(request) == "alpha:batch_by_action"

    def test_filter_visible_resources_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "beta",
            policies=policies,
            fallback_key="alpha",
        )
        subject, action_id, candidates = MagicMock(), "act", tuple()
        assert dyn.filter_visible_resources(subject, action_id, candidates) == "beta:filter_visible"
        policies["beta"].filter_visible_resources.assert_called_once_with(subject, action_id, candidates)

    def test_query_policies_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        subject = MagicMock()
        assert dyn.query_policies(subject, "act") == ["alpha:policy_expr"]

    def test_query_policies_by_actions_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "beta",
            policies=policies,
            fallback_key="alpha",
        )
        subject = MagicMock()
        assert dyn.query_policies_by_actions(subject, ["a"]) == {"a": ["beta:policy_expr"]}

    def test_has_any_permission_delegates(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        assert dyn.has_any_permission(MagicMock(), "act") is True
        policies["alpha"].has_any_permission.assert_called_once()

    def test_selector_result_lowercased(self, providers, policies):
        """selector 返回大写字符串也应能命中（内部规范化 lower()）。"""
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "ALPHA",
            policies=policies,
            fallback_key="beta",
        )
        assert dyn.is_allowed(MagicMock()) == "alpha:is_allowed"


# ------------------------------------------------------------------
# 2. selector 未知 / 异常 / 空值 → fallback
# ------------------------------------------------------------------


class TestFallbackBehavior:
    def test_unknown_key_uses_fallback(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "unknown_mode",
            policies=policies,
            fallback_key="beta",
        )
        assert dyn.is_allowed(MagicMock()) == "beta:is_allowed"
        policies["alpha"].is_allowed.assert_not_called()

    def test_selector_raises_uses_fallback(self, providers, policies):
        def _bad_selector() -> str:
            raise RuntimeError("selector broke")

        dyn = DynamicCompositionPolicy(
            providers,
            selector=_bad_selector,
            policies=policies,
            fallback_key="alpha",
        )
        # 不应把 selector 的异常传出去；应该静默走 fallback
        assert dyn.is_allowed(MagicMock()) == "alpha:is_allowed"

    def test_selector_returns_none_uses_fallback(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: None,
            policies=policies,
            fallback_key="beta",
        )
        assert dyn.is_allowed(MagicMock()) == "beta:is_allowed"

    def test_selector_returns_empty_string_uses_fallback(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "",
            policies=policies,
            fallback_key="alpha",
        )
        assert dyn.is_allowed(MagicMock()) == "alpha:is_allowed"


# ------------------------------------------------------------------
# 3. 写授权 & 展示：与 mode 解耦，走基类固定语义
# ------------------------------------------------------------------


class TestWriteAndDisplayIndependentOfSelector:
    """grant_creator_action / get_apply_url 走基类，不受 selector 影响。

    * grant_creator_action：对 self.providers 全扇出（迁移期双写契约）
    * get_apply_url：走 self.primary()（默认 providers[0]）
    * 这两者的行为不依赖候选池中任何子策略。
    """

    def test_grant_creator_action_uses_base_impl_fanout(self, providers, policies):
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        dyn.grant_creator_action("space", "2", "alice")
        # 所有 provider 都被写入一次（对齐 CompositionPolicy 基类的 fanout 行为）
        providers[0].grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")
        providers[1].grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")
        # 候选子策略的 grant_creator_action 不应被调用（走的是基类而不是委托）
        policies["alpha"].grant_creator_action.assert_not_called()
        policies["beta"].grant_creator_action.assert_not_called()

    def test_get_apply_url_uses_primary(self, providers, policies):
        providers[0].get_apply_url.return_value = "https://a/apply"
        providers[1].get_apply_url.return_value = "https://b/apply"
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "alpha",
            policies=policies,
            fallback_key="beta",
        )
        request = MagicMock()
        # primary() 默认取 providers[0]
        assert dyn.get_apply_url(request) == "https://a/apply"
        providers[0].get_apply_url.assert_called_once_with(request)
        providers[1].get_apply_url.assert_not_called()

    def test_get_apply_data_uses_primary(self, providers, policies):
        providers[0].get_apply_data.return_value = {"from": "a"}
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: "beta",
            policies=policies,
            fallback_key="alpha",
        )
        subject = MagicMock()
        assert dyn.get_apply_data(["act"], [], subject) == {"from": "a"}
        providers[0].get_apply_data.assert_called_once()
        providers[1].get_apply_data.assert_not_called()


# ------------------------------------------------------------------
# 4. 构造契约
# ------------------------------------------------------------------


class TestConstructionContract:
    def test_empty_policies_raises(self, providers):
        with pytest.raises(ValueError, match="at least one candidate policy"):
            DynamicCompositionPolicy(
                providers,
                selector=lambda: "alpha",
                policies={},
                fallback_key="alpha",
            )

    def test_fallback_key_not_in_policies_raises(self, providers, policies):
        with pytest.raises(ValueError, match="fallback_key"):
            DynamicCompositionPolicy(
                providers,
                selector=lambda: "alpha",
                policies=policies,
                fallback_key="not_exist",
            )

    def test_selector_can_be_swapped_via_closure(self, providers, policies):
        """
        selector 是无参 callable：外部只要能在同一 selector 中读到新值，
        DynamicCompositionPolicy 无需重装就能反映"运行时切换"能力。

        本用例模拟"业务侧从共享状态里读 mode"，验证每次调用都会重新问 selector。
        """
        state = {"mode": "alpha"}
        dyn = DynamicCompositionPolicy(
            providers,
            selector=lambda: state["mode"],
            policies=policies,
            fallback_key="beta",
        )

        # 初始命中 alpha
        assert dyn.is_allowed(MagicMock()) == "alpha:is_allowed"
        # 切换外部状态 → 下一次调用直接反映
        state["mode"] = "beta"
        assert dyn.is_allowed(MagicMock()) == "beta:is_allowed"
        # 再切一个未知值 → 走 fallback（beta）
        state["mode"] = "unknown_x"
        assert dyn.is_allowed(MagicMock()) == "beta:is_allowed"


# ------------------------------------------------------------------
# 5. from_options 装配路径
#
# 这一组用例的关注点不是运行期语义（前面 4 组已经充分覆盖），而是"配置期
# 规格 → 运行期对象"的翻译是否正确：
#   * selector 支持 dict 规格（内置 static / django_setting、dotted path）与
#     callable 两种输入形态
#   * policies 支持嵌套的 {"policy": ..., "options": ...} 规格，运行期解析
#     成真正的 CompositionPolicy 实例
#   * 禁止嵌套 dynamic
# ------------------------------------------------------------------


class TestFromOptions:
    """DynamicCompositionPolicy.from_options：装配契约与 conf.py 完全解耦。"""

    def test_from_options_with_static_selector_and_nested_policies(self):
        """
        使用真实的 SinglePolicy 作为子策略，模拟 config/default.py 里
        union 分支的完整装配路径，但完全绕开 django。
        """
        from bkmonitor.iam.iam_engine.provider.composition.dynamic import (
            DynamicCompositionPolicy,
        )
        from bkmonitor.iam.iam_engine.provider.composition.any_of import AnyOfPolicy
        from bkmonitor.iam.iam_engine.provider.composition.primary import PrimaryPolicy

        v4 = _make_provider("v4")
        v3 = _make_provider("v3")

        dyn = DynamicCompositionPolicy.from_options(
            [v4, v3],
            selector={"type": "static", "value": "primary_v4"},
            fallback_key="any_of",
            policies={
                "any_of": {"policy": "any_of"},
                "primary_v4": {
                    "policy": "primary",
                    "options": {"primary_provider": "v4"},
                },
                "primary_v3": {
                    "policy": "primary",
                    "options": {"primary_provider": "v3"},
                },
            },
        )

        # selector=static("primary_v4") → 命中 primary_v4 子策略
        assert isinstance(dyn._policies["primary_v4"], PrimaryPolicy)
        assert isinstance(dyn._policies["any_of"], AnyOfPolicy)
        assert dyn._policies["primary_v4"].primary() is v4
        assert dyn._policies["primary_v3"].primary() is v3
        assert dyn._fallback_key == "any_of"

    def test_from_options_callable_selector_bypasses_spec(self, providers):
        """直接注入 callable：测试 / Python API 场景。"""
        dyn = DynamicCompositionPolicy.from_options(
            providers,
            selector=lambda: "any_of",
            fallback_key="any_of",
            policies={"any_of": {"policy": "any_of"}},
        )
        # 直接构造 provider 结果无所谓，只验证选择器命中
        assert dyn._selector() == "any_of"

    def test_from_options_selector_invalid_type_raises(self, providers):
        with pytest.raises(ValueError, match="selector must be a callable or a spec dict"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector=123,  # type: ignore[arg-type]
                fallback_key="any_of",
                policies={"any_of": {"policy": "any_of"}},
            )

    def test_from_options_empty_policies_raises(self, providers):
        with pytest.raises(ValueError, match="non-empty 'policies'"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector={"type": "static", "value": "any_of"},
                fallback_key="any_of",
                policies={},
            )

    def test_from_options_policy_spec_missing_name_raises(self, providers):
        with pytest.raises(ValueError, match="missing 'policy' name"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector={"type": "static", "value": "any_of"},
                fallback_key="any_of",
                policies={"any_of": {"options": {}}},
            )

    def test_from_options_policy_spec_not_dict_raises(self, providers):
        with pytest.raises(ValueError, match="spec must be a dict"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector={"type": "static", "value": "any_of"},
                fallback_key="any_of",
                policies={"any_of": "not-a-dict"},  # type: ignore[dict-item]
            )

    def test_from_options_nested_dynamic_forbidden(self, providers):
        with pytest.raises(ValueError, match="no nesting"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector={"type": "static", "value": "outer"},
                fallback_key="outer",
                policies={
                    "outer": {
                        "policy": "dynamic",
                        "options": {
                            "selector": {"type": "static", "value": "x"},
                            "fallback_key": "x",
                            "policies": {"x": {"policy": "any_of"}},
                        },
                    }
                },
            )

    def test_from_options_fallback_key_not_in_policies_raises(self, providers):
        with pytest.raises(ValueError, match="fallback_key"):
            DynamicCompositionPolicy.from_options(
                providers,
                selector={"type": "static", "value": "any_of"},
                fallback_key="not_in_pool",
                policies={"any_of": {"policy": "any_of"}},
            )
