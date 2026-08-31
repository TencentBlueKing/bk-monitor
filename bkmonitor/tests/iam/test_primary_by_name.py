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
# 08-28 框架决策 · PrimaryPolicy 按 name 指定 primary_provider 的能力测试
#
# 覆盖：
#   1. 显式 primary_provider=<name> 命中 → self._primary 为该 provider
#   2. 未指定 primary_provider → 兼容旧语义（providers[0] 为主）
#   3. 显式 name 不存在于 providers → ValueError（fail fast）
#   4. 显式 name 命中后，fallback 顺序为"其它 providers 按声明顺序"
#   5. primary() 用于 get_apply_url / get_apply_data 时也返回显式指定的 primary
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.iam_engine.provider.composition.primary import PrimaryPolicy


def _make_provider(name: str) -> MagicMock:
    p = MagicMock()
    p.name = name
    return p


class TestPrimaryProviderByName:
    def test_explicit_primary_name_hits(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        policy = PrimaryPolicy([v4, v3], primary_provider="v3")

        assert policy.primary() is v3
        # is_allowed 直接走 primary（v3），无异常时不 fallback 到 v4
        v3.is_allowed.return_value = True
        request = MagicMock()
        assert policy.is_allowed(request) is True
        v3.is_allowed.assert_called_once_with(request)
        v4.is_allowed.assert_not_called()

    def test_no_primary_name_defaults_to_first_provider(self):
        """未指定 primary_provider → 兼容旧行为，取 providers[0] 为主。"""
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        policy = PrimaryPolicy([v4, v3])

        assert policy.primary() is v4

    def test_unknown_primary_name_raises(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        with pytest.raises(ValueError, match="primary_provider="):
            PrimaryPolicy([v4, v3], primary_provider="v99")

    def test_fallback_order_excludes_primary(self):
        """显式指定 primary_provider=v3 后：v3 挂了应 fallback 到 v4，
        v4 挂了应上抛异常。"""
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        # 主抛不可用 → 走备
        v3.is_allowed.side_effect = ProviderUnavailable("v3 down")
        v4.is_allowed.return_value = True

        policy = PrimaryPolicy([v4, v3], primary_provider="v3")
        assert policy.is_allowed(MagicMock()) is True
        v3.is_allowed.assert_called_once()
        v4.is_allowed.assert_called_once()

    def test_all_unavailable_raises_last(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        v3.is_allowed.side_effect = ProviderUnavailable("v3 down")
        v4.is_allowed.side_effect = ProviderUnavailable("v4 down")

        policy = PrimaryPolicy([v4, v3], primary_provider="v3")
        with pytest.raises(ProviderUnavailable, match="v4 down"):
            policy.is_allowed(MagicMock())

    def test_primary_used_for_apply_url(self):
        """primary() 也决定 get_apply_url / get_apply_data 的落点。"""
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        v3.get_apply_url.return_value = "https://v3/apply"

        policy = PrimaryPolicy([v4, v3], primary_provider="v3")
        assert policy.get_apply_url(MagicMock()) == "https://v3/apply"
        v3.get_apply_url.assert_called_once()
        v4.get_apply_url.assert_not_called()

    def test_fallback_on_error_false_bubbles_primary_error(self):
        """fallback_on_error=False 时主故障不 fallback，即使 name 显式指定 primary。"""
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")
        v3.is_allowed.side_effect = ProviderUnavailable("v3 down")

        policy = PrimaryPolicy([v4, v3], primary_provider="v3", fallback_on_error=False)
        with pytest.raises(ProviderUnavailable, match="v3 down"):
            policy.is_allowed(MagicMock())
        v4.is_allowed.assert_not_called()
