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
#   1. 写目标完全由 PermissionWriter 的 Provider 集合决定；
#   2. 一侧失败仍继续其余目标，逐侧结果和详细异常日志可观测；
#   3. 重试会重放完整 desired state，恢复的后端会被再次写入；
#   4. 配置非法（重复后端 / 未实现的失败策略）启动期拒绝。
# ==============================================================================

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy
from bkmonitor.iam.iam_engine.provider.permission_writer import PermissionWriter
from bkmonitor.iam.iam_engine.provider.router import ProviderRouter


def _make_provider(name: str, side_effect=None) -> MagicMock:
    provider = MagicMock()
    provider.name = name
    if side_effect is not None:
        provider.grant_creator_action.side_effect = side_effect
    return provider


class TestPermissionWriter:
    def test_writes_only_to_explicit_write_targets(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3")

        result = PermissionWriter([v3]).grant_creator_action("space", "2", "alice")

        v3.grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")
        v4.grant_creator_action.assert_not_called()
        assert result.is_success is True
        assert [target.provider_name for target in result.succeeded] == ["v3"]

    def test_forwards_expired_at_and_tenant_id(self):
        v4 = _make_provider("v4")

        PermissionWriter([v4]).grant_creator_action("space", "2", "alice", expired_at=7200, tenant_id="tenant-x")

        v4.grant_creator_action.assert_called_once_with("space", "2", "alice", 7200, "tenant-x")

    def test_partial_failure_is_observable_and_does_not_skip_next_target(self, caplog):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 unavailable"))
        v3 = _make_provider("v3")

        with caplog.at_level("ERROR", logger="iam_engine.permission_writer"):
            result = PermissionWriter([v4, v3]).grant_creator_action("space", "2", "alice")

        v4.grant_creator_action.assert_called_once()
        v3.grant_creator_action.assert_called_once()
        assert result.is_success is False
        assert result.is_partial_failure is True
        assert result.failed[0].as_log_dict() == {
            "provider": "v4",
            "succeeded": False,
            "error_type": "RuntimeError",
            "error_message": "v4 unavailable",
        }
        assert [target.provider_name for target in result.succeeded] == ["v3"]
        records = [record for record in caplog.records if "permission write failed" in record.getMessage()]
        assert len(records) == 1
        assert records[0].exc_info is not None
        assert "provider=v4" in records[0].getMessage()
        assert "resource=space/2" in records[0].getMessage()

    def test_all_failure_returns_all_target_errors(self):
        v4 = _make_provider("v4", side_effect=RuntimeError("v4 unavailable"))
        v3 = _make_provider("v3", side_effect=ValueError("v3 unavailable"))

        result = PermissionWriter([v4, v3]).grant_creator_action("space", "2", "alice")

        assert result.is_success is False
        assert result.is_partial_failure is False
        assert [(target.provider_name, target.error_type) for target in result.failed] == [
            ("v4", "RuntimeError"),
            ("v3", "ValueError"),
        ]

    def test_retry_replays_all_targets_and_can_fill_previously_failed_target(self):
        v4 = _make_provider("v4")
        v3 = _make_provider("v3", side_effect=[RuntimeError("transient"), None])
        writer = PermissionWriter([v4, v3])

        first = writer.grant_creator_action("space", "2", "alice")
        second = writer.grant_creator_action("space", "2", "alice")

        assert first.is_partial_failure is True
        assert second.is_success is True
        # 重试不是只补失败侧：它重放同一个幂等的 desired state 到所有写目标。
        assert v4.grant_creator_action.call_count == 2
        assert v3.grant_creator_action.call_count == 2


class TestProviderRouterWriteRouting:
    def test_creator_grant_uses_writer_not_read_policy(self):
        write_target = _make_provider("writer-target")
        read_policy = MagicMock(spec=CompositionPolicy)
        router = ProviderRouter(
            read_policy=read_policy,
            permission_writer=PermissionWriter([write_target]),
        )

        result = router.grant_creator_action("space", "2", "alice")

        write_target.grant_creator_action.assert_called_once_with("space", "2", "alice", None, "")
        assert result.is_success is True
        # CompositionPolicy 已没有创建者授权接口；这里证明 Router 的写路由只依赖 Writer。
        assert not hasattr(read_policy, "grant_creator_action")


class TestPermissionWriterConstruction:
    def test_requires_at_least_one_target(self):
        with pytest.raises(ValueError, match="at least one provider"):
            PermissionWriter([])

    def test_rejects_duplicate_targets(self):
        v4 = _make_provider("v4")
        another_v4 = _make_provider("v4")
        with pytest.raises(ValueError, match="must be unique"):
            PermissionWriter([v4, another_v4])

    def test_rejects_unimplemented_failure_policy(self):
        with pytest.raises(ValueError, match="only on_failure='log'"):
            PermissionWriter([_make_provider("v4")], on_failure="outbox")
