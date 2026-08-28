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
# 阶段 2 · 评论 2 —— 迁移期 grant_creator_action 全 Provider 写入
#
# 覆盖：
#   1. 单 Provider（SinglePolicy 等价场景）→ 直通、异常照抛
#   2. 多 Provider 都成功 → 每个 Provider 都被调用一次
#   3. 多 Provider 一侧成功一侧失败 → 不抛错，成功侧照写、失败侧记 log
#   4. 多 Provider 两侧都失败 → 抛出最后一次异常
#   5. 与 CompositionPolicy 子类的解耦：SinglePolicy / AnyOfPolicy / AllOfPolicy
#      / PrimaryPolicy 都必须走"多 Provider 全写"（读鉴权模式不决定写授权目标）
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.provider.composition.all_of import AllOfPolicy
from bkmonitor.iam.iam_engine.provider.composition.any_of import AnyOfPolicy
from bkmonitor.iam.iam_engine.provider.composition.primary import PrimaryPolicy
from bkmonitor.iam.iam_engine.provider.composition.single import SinglePolicy


def _make_provider(name: str, side_effect=None) -> MagicMock:
    """构造一个只关心 grant_creator_action 行为的 mock Provider。"""
    p = MagicMock()
    p.name = name
    if side_effect is not None:
        p.grant_creator_action.side_effect = side_effect
    return p


class TestSingleProviderPassthrough:
    """单 Provider：无论什么策略，都直通到唯一那个 Provider。"""

    def test_single_policy_delegates(self):
        p = _make_provider("v4")
        SinglePolicy([p]).grant_creator_action("space", "2", "alice")
        p.grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")

    def test_single_provider_exception_propagates(self):
        p = _make_provider("v4", side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            SinglePolicy([p]).grant_creator_action("space", "2", "alice")

    def test_any_of_with_single_provider_delegates(self):
        p = _make_provider("v4")
        AnyOfPolicy([p]).grant_creator_action("space", "2", "alice", expired_at=3600, tenant_id="t1")
        p.grant_creator_action.assert_called_once_with("space", "2", "alice", 3600, "t1")


class TestMultiProviderWriteAll:
    """多 Provider：所有策略都必须写入所有 Provider（写授权与读鉴权解耦）。"""

    @pytest.mark.parametrize(
        "policy_cls",
        [AnyOfPolicy, AllOfPolicy, PrimaryPolicy],
        ids=["any_of", "all_of", "primary"],
    )
    def test_all_providers_called_when_all_succeed(self, policy_cls):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        policy = policy_cls([v4, v3])

        policy.grant_creator_action("space", "2", "alice")

        v4.grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")
        v3.grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")

    def test_forwards_expired_at_and_tenant(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        AnyOfPolicy([v4, v3]).grant_creator_action("space", "2", "alice", expired_at=7200, tenant_id="tenant-x")
        v4.grant_creator_action.assert_called_once_with("space", "2", "alice", 7200, "tenant-x")
        v3.grant_creator_action.assert_called_once_with("space", "2", "alice", 7200, "tenant-x")


class TestPartialFailureTolerated:
    """一侧成功一侧失败：不抛错、成功侧写入完成、失败侧记录 log。"""

    def test_v4_ok_v3_fail_does_not_raise(self, caplog):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3", side_effect=RuntimeError("v3 unavailable"))

        with caplog.at_level("WARNING", logger="iam_engine.composition"):
            AnyOfPolicy([v4, v3]).grant_creator_action("space", "2", "alice")

        # 两侧都被调用，V4 成功、V3 抛错
        v4.grant_creator_action.assert_called_once()
        v3.grant_creator_action.assert_called_once()

        # 有 partial success 的 WARNING（含 succeeded/failed 摘要），供人工补偿
        partial_records = [r for r in caplog.records if "partial success" in r.message]
        assert partial_records, "partial success 摘要必须以 WARNING 打出"
        summary = partial_records[0].getMessage()
        assert "v4" in summary
        assert "v3" in summary

    def test_v4_fail_v3_ok_does_not_raise(self):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 unavailable"))
        v3 = _make_provider("v3")

        # 不抛错：v3 那侧成功即视为整体成功
        AnyOfPolicy([v4, v3]).grant_creator_action("space", "2", "alice")

        v4.grant_creator_action.assert_called_once()
        v3.grant_creator_action.assert_called_once()

    def test_partial_failure_across_policies(self):
        """AllOfPolicy / PrimaryPolicy 也必须遵循相同的 partial-tolerant 语义。"""
        for policy_cls in (AllOfPolicy, PrimaryPolicy):
            v4 = _make_provider("v4")
            v3 = _make_provider("v3", side_effect=RuntimeError("v3 boom"))
            # 应当不抛错，与读鉴权 all_of / primary 的严格语义解耦
            policy_cls([v4, v3]).grant_creator_action("space", "2", "alice")
            v4.grant_creator_action.assert_called_once()
            v3.grant_creator_action.assert_called_once()


class TestAllProvidersFail:
    """两侧全失败：上抛最后一次异常，行为对齐"单 Provider 抛错"路径。"""

    def test_all_fail_raises_last_exception(self):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 boom"))
        v3 = _make_provider("v3", side_effect=ValueError("v3 boom"))

        with pytest.raises(ValueError, match="v3 boom"):
            AnyOfPolicy([v4, v3]).grant_creator_action("space", "2", "alice")

        v4.grant_creator_action.assert_called_once()
        v3.grant_creator_action.assert_called_once()

    def test_all_fail_logs_each_error(self, caplog):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 boom"))
        v3 = _make_provider("v3", side_effect=ValueError("v3 boom"))

        with caplog.at_level("ERROR", logger="iam_engine.composition"):
            with pytest.raises(ValueError):
                AnyOfPolicy([v4, v3]).grant_creator_action("space", "2", "alice")

        # 每个 Provider 的失败都应有独立的 exception log
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) == 2
        messages = " ".join(r.getMessage() for r in error_records)
        assert "provider=v4" in messages
        assert "provider=v3" in messages
