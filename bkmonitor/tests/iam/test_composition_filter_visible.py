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
# 阶段 3 · 评论 3 —— filter_visible_resources 遵循 CompositionPolicy 错误容忍语义
#
# 覆盖：
#   1. SinglePolicy      —— 直通唯一 Provider，异常照抛
#   2. AnyOfPolicy       —— 非 strict：跳过异常侧、合并成功侧；strict：任一异常上抛；
#                           全部失败：抛最后一次异常；一侧 all_granted：整体 all_granted
#   3. AllOfPolicy       —— strict（默认）：任一异常上抛；非 strict：只用成功侧求交集；
#                           所有侧 all_granted 才整体 all_granted；否则取 visible_ids 交集
#   4. PrimaryPolicy     —— 主返回时以主为准（deny 也生效）；主 ProviderUnavailable 时
#                           fallback 到次；全部 ProviderUnavailable 时抛最后一次
#
# 特别验证：与旧实现（基类硬编码遍历）的关键差异——
#   - 旧行为：AnyOfPolicy + V4 抛 ProviderUnavailable + V3 返回可见空间
#     → 直接冒泡异常，上层降级为空，V3 的授权彻底失效
#   - 新行为：非 strict 模式下 AnyOfPolicy 会跳过 V4 异常，返回 V3 的可见空间
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.iam_engine.core.types import ResourceInstance, Subject, VisibleResult
from bkmonitor.iam.iam_engine.provider.composition.all_of import AllOfPolicy
from bkmonitor.iam.iam_engine.provider.composition.any_of import AnyOfPolicy
from bkmonitor.iam.iam_engine.provider.composition.primary import PrimaryPolicy
from bkmonitor.iam.iam_engine.provider.composition.single import SinglePolicy


# ----- fixture helpers -----


def _subject() -> Subject:
    return Subject(id="alice", tenant_id="system")


def _candidates(ids: list[str]) -> tuple[ResourceInstance, ...]:
    return tuple(ResourceInstance(type="space", id=i) for i in ids)


def _provider(name: str, return_value: VisibleResult | None = None, side_effect=None) -> MagicMock:
    p = MagicMock()
    p.name = name
    if side_effect is not None:
        p.filter_visible_resources.side_effect = side_effect
    else:
        p.filter_visible_resources.return_value = return_value
    return p


# ==============================================================================
# SinglePolicy
# ==============================================================================


class TestSinglePolicyFilter:
    def test_delegates_to_single_provider(self):
        v4 = _provider("v4", VisibleResult(all_granted=False, visible_ids=("2", "3")))
        result = SinglePolicy([v4]).filter_visible_resources(_subject(), "view_business", _candidates(["2", "3"]))
        assert result.all_granted is False
        assert set(result.visible_ids) == {"2", "3"}
        v4.filter_visible_resources.assert_called_once()

    def test_provider_exception_propagates(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("boom"))
        with pytest.raises(ProviderUnavailable, match="boom"):
            SinglePolicy([v4]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))


# ==============================================================================
# AnyOfPolicy
# ==============================================================================


class TestAnyOfPolicyFilterNonStrict:
    """非 strict（默认）：跳过异常侧、合并成功侧的 all_granted(OR) 与 ids(并集)。"""

    def test_both_succeed_merges_union(self):
        v4 = _provider("v4", VisibleResult(all_granted=False, visible_ids=("2",)))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3", "5")))
        result = AnyOfPolicy([v4, v3]).filter_visible_resources(
            _subject(), "view_business", _candidates(["2", "3", "5"])
        )
        assert result.all_granted is False
        assert set(result.visible_ids) == {"2", "3", "5"}

    def test_any_all_granted_makes_union_all_granted(self):
        v4 = _provider("v4", VisibleResult(all_granted=True, visible_ids=()))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3",)))
        result = AnyOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["3"]))
        assert result.all_granted is True

    def test_v4_error_v3_ok_returns_v3_visible_ids(self):
        """核心回归：旧实现下 V4 异常直接冒泡、V3 已有授权全丢；新实现跳过 V4 保留 V3。"""
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("2",)))
        result = AnyOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        assert result.all_granted is False
        assert set(result.visible_ids) == {"2"}

    def test_v3_error_v4_ok_returns_v4_visible_ids(self):
        v4 = _provider("v4", VisibleResult(all_granted=False, visible_ids=("7",)))
        v3 = _provider("v3", side_effect=ProviderUnavailable("v3 down"))
        result = AnyOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["7"]))
        assert set(result.visible_ids) == {"7"}

    def test_all_providers_fail_raises_last_error(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", side_effect=RuntimeError("v3 down"))
        with pytest.raises(RuntimeError, match="v3 down"):
            AnyOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))


class TestAnyOfPolicyFilterStrict:
    """strict：任一 Provider 抛异常即上抛，对齐 is_allowed 的严格契约。"""

    def test_strict_v4_error_propagates(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("2",)))
        policy = AnyOfPolicy([v4, v3], strict_errors=True)
        with pytest.raises(ProviderUnavailable, match="v4 down"):
            policy.filter_visible_resources(_subject(), "view_business", _candidates(["2"]))


# ==============================================================================
# AllOfPolicy
# ==============================================================================


class TestAllOfPolicyFilterStrict:
    """strict（默认）：任一异常上抛。"""

    def test_strict_v4_error_propagates(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("2",)))
        with pytest.raises(ProviderUnavailable, match="v4 down"):
            AllOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))


class TestAllOfPolicyFilterMerge:
    """AllOf 语义：所有侧都通过才通过；ids 取交集。"""

    def test_both_succeed_intersection(self):
        v4 = _provider("v4", VisibleResult(all_granted=False, visible_ids=("2", "3")))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3", "5")))
        result = AllOfPolicy([v4, v3]).filter_visible_resources(
            _subject(), "view_business", _candidates(["2", "3", "5"])
        )
        assert result.all_granted is False
        assert set(result.visible_ids) == {"3"}  # 交集

    def test_all_sides_all_granted(self):
        v4 = _provider("v4", VisibleResult(all_granted=True, visible_ids=()))
        v3 = _provider("v3", VisibleResult(all_granted=True, visible_ids=()))
        result = AllOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        assert result.all_granted is True

    def test_mixed_all_granted_side_does_not_constrain_ids(self):
        """一侧 all_granted、另一侧列可见 ids：整体不是 all_granted，ids 取"非 all_granted 侧"。"""
        v4 = _provider("v4", VisibleResult(all_granted=True, visible_ids=()))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("2",)))
        result = AllOfPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        assert result.all_granted is False
        assert set(result.visible_ids) == {"2"}


class TestAllOfPolicyFilterNonStrict:
    def test_non_strict_skips_error_and_uses_survivor(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("2",)))
        policy = AllOfPolicy([v4, v3], strict_errors=False)
        result = policy.filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        assert set(result.visible_ids) == {"2"}

    def test_non_strict_all_fail_returns_empty(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", side_effect=ProviderUnavailable("v3 down"))
        policy = AllOfPolicy([v4, v3], strict_errors=False)
        result = policy.filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        assert result.all_granted is False
        assert result.visible_ids == ()


# ==============================================================================
# PrimaryPolicy
# ==============================================================================


class TestPrimaryPolicyFilter:
    def test_primary_returns_wins(self):
        v4 = _provider("v4", VisibleResult(all_granted=False, visible_ids=("2",)))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3", "5")))
        result = PrimaryPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))
        # 主返回则以主为准（v3 不被调用）
        assert set(result.visible_ids) == {"2"}
        v3.filter_visible_resources.assert_not_called()

    def test_primary_unavailable_falls_back(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3",)))
        result = PrimaryPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["3"]))
        assert set(result.visible_ids) == {"3"}

    def test_all_unavailable_raises_last(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", side_effect=ProviderUnavailable("v3 down"))
        with pytest.raises(ProviderUnavailable, match="v3 down"):
            PrimaryPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["2"]))

    def test_fallback_on_error_disabled_reraises_primary(self):
        v4 = _provider("v4", side_effect=ProviderUnavailable("v4 down"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3",)))
        policy = PrimaryPolicy([v4, v3], fallback_on_error=False)
        with pytest.raises(ProviderUnavailable, match="v4 down"):
            policy.filter_visible_resources(_subject(), "view_business", _candidates(["3"]))
        v3.filter_visible_resources.assert_not_called()

    def test_primary_non_provider_error_not_captured(self):
        """PrimaryPolicy 只捕获 ProviderUnavailable，其他异常直接上抛（对齐 is_allowed 契约）。"""
        v4 = _provider("v4", side_effect=RuntimeError("bad payload"))
        v3 = _provider("v3", VisibleResult(all_granted=False, visible_ids=("3",)))
        with pytest.raises(RuntimeError, match="bad payload"):
            PrimaryPolicy([v4, v3]).filter_visible_resources(_subject(), "view_business", _candidates(["3"]))
        v3.filter_visible_resources.assert_not_called()
