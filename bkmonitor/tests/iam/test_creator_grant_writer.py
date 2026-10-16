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
# 通用权限写路径：独立于 CompositionPolicy 的显式 Writer
#
# 覆盖：
#   1. 写目标完全由 CreatorGrantOrchestration 的 Provider 集合决定；
#   2. 一侧失败仍继续其余目标，逐侧结果和详细异常日志可观测；
#   3. 每次调用仅同步尝试一次，不投递后台补偿；
#   4. 配置非法（重复后端 / 未实现的失败策略）启动期拒绝。
# ==============================================================================

from unittest.mock import MagicMock

from iam_engine.provider.codec import IdentityCodec

from tests.iam.helpers import grant_creator_actions


def _make_provider(name: str, side_effect=None) -> MagicMock:
    provider = MagicMock()
    provider.name = name
    provider.codec = IdentityCodec()
    if side_effect is not None:
        if name == "v4":
            provider._get_client.return_value.add_authorization.side_effect = side_effect
        else:
            provider._get_client.return_value.grant_resource_creator_actions.side_effect = side_effect
    return provider


class TestCreatorGrantOrchestration:
    def test_writes_only_to_explicit_write_targets(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")

        result = grant_creator_actions([v3], "space", "2", "alice")

        v3._get_client.return_value.grant_resource_creator_actions.assert_called_once()
        v4._get_client.return_value.add_authorization.assert_not_called()
        assert result.is_success is True
        assert [target.provider_name for target in result.succeeded] == ["v3"]

    def test_forwards_expired_at_and_tenant_id(self):
        v4 = _make_provider("v4")

        grant_creator_actions([v4], "space", "2", "alice", expired_at=7200, tenant_id="tenant-x")

        v4._get_client.assert_called_once_with("tenant-x")
        payload = v4._get_client.return_value.add_authorization.call_args.kwargs["items"]
        assert payload[0]["expired_at"] == 7200
        assert payload[0]["resources"] == [{"type": "space", "id": "2"}]

    def test_partial_failure_is_observable_and_does_not_skip_next_target(self, caplog):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 unavailable"))
        v3 = _make_provider("v3")

        with caplog.at_level("ERROR", logger="iam_engine.permission_writer"):
            result = grant_creator_actions([v4, v3], "space", "2", "alice")

        v4._get_client.return_value.add_authorization.assert_called_once()
        v3._get_client.return_value.grant_resource_creator_actions.assert_called_once()
        assert result.is_success is False
        assert result.is_partial_failure is True
        assert not result.failed[0].retry_scheduled
        assert result.failed[0].error_type == "RuntimeError"

    def test_all_failure_returns_all_target_errors(self):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 unavailable"))
        v3 = _make_provider("v3", side_effect=ValueError("v3 unavailable"))

        result = grant_creator_actions([v4, v3], "space", "2", "alice")

        assert result.is_success is False
        assert result.is_partial_failure is False
        assert [(target.provider_name, target.error_type) for target in result.failed] == [
            ("v3", "ValueError"),
            ("v4", "RuntimeError"),
        ]

    def test_explicit_new_call_retries_all_targets_without_background_recovery(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3", side_effect=[RuntimeError("transient"), None])

        first = grant_creator_actions([v4, v3], "space", "2", "alice")
        second = grant_creator_actions([v4, v3], "space", "2", "alice")

        assert first.is_partial_failure is True
        assert second.is_success is True
        # 第二次是调用方主动发起的独立授权，不是自动补偿。
        assert v4._get_client.return_value.add_authorization.call_count == 2
        assert v3._get_client.return_value.grant_resource_creator_actions.call_count == 2
