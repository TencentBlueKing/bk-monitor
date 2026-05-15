"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from alarm_backends.service.fta_action.issue_processor import build_issue_default_name, gen_issue_fingerprint
from bkmonitor.utils.common_utils import count_md5


class TestGenIssueFingerprint:
    """gen_issue_fingerprint 函数单测：覆盖空维度退化 / 缺失 / 排序稳定性 / 跨策略区分性。

    入参 data_dimensions 取自 alert.event.extra_info.origin_alarm.data.dimensions
    （adapter 收编前的原始维度集合，命名与 issue_config.aggregate_dimensions 一致）。
    """

    def test_empty_dimensions_returns_strategy_only_fingerprint(self):
        """aggregate_dimensions 为空时退化到 ``count_md5(["strategy:{id}"])``。"""
        fp = gen_issue_fingerprint(123, [], {"any": "dim"})
        assert fp == count_md5(["strategy:123"])
        # data_dimensions 内容不影响（aggregate_dimensions=[] 时不读取）
        assert gen_issue_fingerprint(123, [], {}) == count_md5(["strategy:123"])

    def test_empty_dimensions_strategy_isolation(self):
        """退化路径下不同 strategy_id 仍得到不同指纹（strategy prefix 区分）。"""
        assert gen_issue_fingerprint(123, [], {}) != gen_issue_fingerprint(456, [], {})

    def test_with_dimensions_returns_count_md5_with_kv_prefix(self):
        """非空 aggregate_dimensions 时返回 count_md5([f"strategy:{id}", f"{k}={v}", ...])。"""
        fp = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        assert fp is not None
        # 与 count_md5 公式手算一致：每个元素带 prefix 防错位 / 跨策略碰撞
        assert fp == count_md5(["strategy:123", "bk_host_id=9185731"])

    def test_dim_value_swap_must_not_collide(self):
        """{a:X, b:Y} 与 {a:Y, b:X} 必须算出不同 fingerprint（防键值错位错合并）。

        若 payload 形如 ["123", "X", "Y"]，count_md5 内部 list_sort=True 排序后
        ["X","Y"] 与 ["Y","X"] 相同 → 同一指纹。带 ``f"{k}={v}"`` prefix 后
        ["a=X","b=Y"] 与 ["a=Y","b=X"] 排序后元素不同 → 不同指纹。
        """
        fp1 = gen_issue_fingerprint(123, ["a", "b"], {"a": "X", "b": "Y"})
        fp2 = gen_issue_fingerprint(123, ["a", "b"], {"a": "Y", "b": "X"})
        assert fp1 != fp2

    def test_cross_strategy_dim_value_no_collision(self):
        """strategy_id=123 + a="456" 与 strategy_id=456 + a="123" 必须算出不同 fingerprint。

        若 payload 形如 [str(id), v]，sorted(["123","456"]) == sorted(["456","123"])
        → 同一指纹（跨策略碰撞）。带 ``f"strategy:{id}"`` / ``f"{k}={v}"`` prefix 后
        元素本身有结构区分，不可能字面相等。
        """
        fp1 = gen_issue_fingerprint(123, ["a"], {"a": "456"})
        fp2 = gen_issue_fingerprint(456, ["a"], {"a": "123"})
        assert fp1 != fp2

    def test_missing_dimension_returns_none(self):
        """data_dimensions 缺 aggregate_dimensions 中某个 key → 返回 None。"""
        # 完全缺失
        assert gen_issue_fingerprint(123, ["bk_host_id"], {"other": "value"}) is None
        # 部分缺失
        assert gen_issue_fingerprint(123, ["ip", "service"], {"ip": "<ip>"}) is None

    def test_none_value_returns_none(self):
        """维度值为 None → 返回 None。"""
        assert gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": None}) is None

    def test_empty_string_value_returns_none(self):
        """维度值为空串 → 返回 None。"""
        assert gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": ""}) is None

    def test_dimension_order_stable(self):
        """aggregate_dimensions 配置项顺序变化不应影响指纹（按 key 排序后参与）。"""
        dims = {"ip": "<ip>", "service": "order"}
        fp1 = gen_issue_fingerprint(123, ["ip", "service"], dims)
        fp2 = gen_issue_fingerprint(123, ["service", "ip"], dims)
        assert fp1 == fp2

    def test_different_strategies_produce_different_fingerprints(self):
        """同维度值、不同策略 → 指纹不同（验证 strategy_id 隔离）。"""
        fp1 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        fp2 = gen_issue_fingerprint(456, ["bk_host_id"], {"bk_host_id": "9185731"})
        assert fp1 != fp2

    def test_different_values_produce_different_fingerprints(self):
        """同策略、不同维度值 → 指纹不同（验证按维度切分语义）。"""
        fp1 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        fp2 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "1804751"})
        assert fp1 != fp2

    def test_value_int_or_str_consistent(self):
        """维度值 int 与等价 str 应得到相同指纹（避免类型混淆带来"幽灵"指纹）。"""
        fp_int = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": 9185731})
        fp_str = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        assert fp_int == fp_str

    def test_data_dimensions_extra_keys_ignored(self):
        """data_dimensions 带额外 key（不在 aggregate_dimensions 中）不影响指纹。"""
        fp1 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        fp2 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731", "service": "order", "ip": "<ip>"})
        assert fp1 == fp2

    def test_value_with_leading_trailing_whitespace_normalized(self):
        """值带前后空白时 strip 归一化，与无空白等价。"""
        fp1 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "9185731"})
        fp2 = gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "  9185731  "})
        assert fp1 == fp2

    def test_value_pure_whitespace_returns_none(self):
        """全空白值 strip 后为空，视为缺失，返回 None。"""
        assert gen_issue_fingerprint(123, ["bk_host_id"], {"bk_host_id": "   "}) is None

    def test_dimension_values_snapshot_strict_match_fingerprint(self):
        """dimension_values 快照构造（processor / backfill 同款逻辑）必须与 fingerprint 输入严格归一化对应。

        契约：含空白的 dim 值算同 fingerprint 时，dimension_values 快照也必须是 strip 后形态，
        否则前端 ``dimension_values.bk_host_id="9185731"`` 精确过滤会因快照存为 " 9185731 " 不命中。
        """
        data_dims = {"bk_host_id": "  9185731  ", "service": " order "}
        agg_dims = ["bk_host_id", "service"]

        # processor / backfill 构造 dimension_values 的同款代码
        dimension_values = {key: str(data_dims[key]).strip() for key in sorted(agg_dims)}

        # 同 fingerprint：原始带空白 vs strip 后值再算 fingerprint
        fp_raw = gen_issue_fingerprint(123, agg_dims, data_dims)
        fp_normalized = gen_issue_fingerprint(123, agg_dims, dimension_values)
        assert fp_raw == fp_normalized

        # dimension_values 全部已去前后空白
        assert all(v == v.strip() for v in dimension_values.values())
        assert dimension_values == {"bk_host_id": "9185731", "service": "order"}

    def test_bk_target_dimensions_from_data_dimensions(self):
        """主机型策略：issue_config.aggregate_dimensions=[bk_target_ip, bk_target_cloud_id]，
        data_dimensions（来自 origin_alarm.data.dimensions）含这俩字段，fingerprint 算成功。

        必须从 data_dimensions（adapter 收编前的原始命名）取——不能从 alert.dimensions
        （主机已被收编为 target_type/target + enricher 单独补 ip / bk_cloud_id）取，跨层
        命名不一致 lookup 必失败。
        """
        data_dims = {"bk_target_ip": "<ip-1>", "bk_target_cloud_id": "0", "mount_point": "/"}
        fp = gen_issue_fingerprint(999999, ["bk_target_ip", "bk_target_cloud_id"], data_dims)
        assert fp is not None and len(fp) == 32  # md5 hex

        # 不同 ip → 不同 fingerprint（按主机切分 issue 的预期效果）
        data_dims2 = {**data_dims, "bk_target_ip": "<ip-2>"}
        fp2 = gen_issue_fingerprint(999999, ["bk_target_ip", "bk_target_cloud_id"], data_dims2)
        assert fp != fp2

    def test_pure_dict_lookup_no_event_field_resolution(self):
        """fingerprint 仅按 dict.get(key) 在 data_dimensions 内查找，不做任何字段解析。

        例如 'tags.mount_point' 必须在 data_dimensions 顶层有该 key 才能命中——
        adapter 已把 tags. 前缀剥离写入 origin_alarm.data.dimensions（adapter.py
        line 207-213），所以策略层若配 ``mount_point`` 直接命中。
        """
        # 配置带 tags. 前缀 + data_dimensions 没这个 key → None
        data_dims = {"mount_point": "/data"}
        assert gen_issue_fingerprint(123, ["tags.mount_point"], data_dims) is None

        # 配置纯 key + data_dimensions 含该 key → 命中
        fp = gen_issue_fingerprint(123, ["mount_point"], data_dims)
        assert fp == count_md5(["strategy:123", "mount_point=/data"])


@pytest.mark.parametrize(
    "strategy_id,aggregate_dimensions,data_dims,expected_none",
    [
        (1, [], {}, False),  # 退化路径，永不为 None（count_md5([str(id)])）
        (1, ["a"], {"a": "v"}, False),
        (1, ["a"], {}, True),  # 缺维度
        (1, ["a"], {"a": None}, True),
        (1, ["a"], {"a": ""}, True),
        (1, ["a"], {"a": "   "}, True),  # 全空白
        (1, ["a", "b"], {"a": "v"}, True),  # 部分缺
    ],
)
def test_gen_fingerprint_none_semantics(strategy_id, aggregate_dimensions, data_dims, expected_none):
    """参数化覆盖 None 返回值边界。"""
    result = gen_issue_fingerprint(strategy_id, aggregate_dimensions, data_dims)
    assert (result is None) == expected_none


class TestProcessorOriginDataDimensions:
    """IssueAggregationProcessor._get_origin_data_dimensions 取值路径单测：
    覆盖正常路径 + 各层缺失兜底（第三方告警 / FTA 告警 origin_alarm 缺失场景）。
    """

    def _make_proc_with_event(self, event):
        from unittest.mock import MagicMock

        from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

        proc = IssueAggregationProcessor.__new__(IssueAggregationProcessor)
        proc.alert = MagicMock()
        proc.alert.event = event
        return proc

    def test_full_path_extracts_dimensions(self):
        """正常链路：event.extra_info.origin_alarm.data.dimensions 完整 → 返回 dict。"""
        event = {
            "extra_info": {
                "origin_alarm": {
                    "data": {"dimensions": {"bk_target_ip": "<ip>", "bk_target_cloud_id": "0", "mount_point": "/"}}
                }
            }
        }
        proc = self._make_proc_with_event(event)
        assert proc._get_origin_data_dimensions() == {
            "bk_target_ip": "<ip>",
            "bk_target_cloud_id": "0",
            "mount_point": "/",
        }

    def test_alert_event_none_returns_empty(self):
        """alert.event=None（理论不发生，防御兜底）→ 空 dict。"""
        proc = self._make_proc_with_event(None)
        assert proc._get_origin_data_dimensions() == {}

    def test_extra_info_missing_returns_empty(self):
        """event 缺 extra_info → 空 dict（兜底）。"""
        proc = self._make_proc_with_event({})
        assert proc._get_origin_data_dimensions() == {}

    def test_origin_alarm_missing_returns_empty(self):
        """第三方告警 / FTA 告警可能没有 origin_alarm → 空 dict（兜底）。"""
        proc = self._make_proc_with_event({"extra_info": {}})
        assert proc._get_origin_data_dimensions() == {}

    def test_data_dimensions_missing_returns_empty(self):
        """origin_alarm 存在但缺 data.dimensions → 空 dict（兜底）。"""
        proc = self._make_proc_with_event({"extra_info": {"origin_alarm": {"data": {}}}})
        assert proc._get_origin_data_dimensions() == {}

    def test_inner_doc_to_dict_unwrap(self):
        """alert.event 是 InnerDoc 形态（带 to_dict 方法）→ 递归解包成功。"""
        from unittest.mock import MagicMock

        # 模拟 ES InnerDoc：每层都暴露 to_dict
        inner_data = MagicMock()
        inner_data.to_dict.return_value = {"dimensions": {"bk_host_id": "1804751"}}
        inner_origin = MagicMock()
        inner_origin.to_dict.return_value = {"data": inner_data}
        inner_extra = MagicMock()
        inner_extra.to_dict.return_value = {"origin_alarm": inner_origin}
        inner_event = MagicMock()
        inner_event.to_dict.return_value = {"extra_info": inner_extra}

        proc = self._make_proc_with_event(inner_event)
        assert proc._get_origin_data_dimensions() == {"bk_host_id": "1804751"}


class TestMigrateLegacyActiveIssues:
    """migrate_legacy_active_issues 关键路径 mock 测试，覆盖 review 提到的场景。"""

    def test_no_legacy_returns_zero(self):
        """无 fingerprint=null 活跃 Issue 时 noop 返回 0，不触发 bulk_create。"""
        from unittest.mock import patch

        from bkmonitor.documents.issue import IssueDocument, migrate_legacy_active_issues

        with (
            patch.object(IssueDocument, "rollover"),
            patch("bkmonitor.documents.issue.IssueActivityDocument.rollover"),
            patch.object(IssueDocument, "search") as mock_search,
            patch.object(IssueDocument, "bulk_create") as mock_bulk,
        ):
            scan_iter = iter([])
            mock_search.return_value.filter.return_value.exclude.return_value.params.return_value.scan.return_value = (
                scan_iter
            )
            assert migrate_legacy_active_issues() == 0
            mock_bulk.assert_not_called()

    def test_rollover_failure_raises_migration_error(self):
        """rollover 失败 → raise IssueMigrationError，阻断后续 scan / bulk。"""
        from unittest.mock import patch

        import pytest as _pytest

        from bkmonitor.documents.issue import (
            IssueDocument,
            IssueMigrationError,
            migrate_legacy_active_issues,
        )

        with patch.object(IssueDocument, "rollover", side_effect=RuntimeError("ES down")):
            with _pytest.raises(IssueMigrationError, match="rollover failed"):
                migrate_legacy_active_issues()

    def test_bulk_update_retry_success_then_activity_failure_does_not_raise(self):
        """update retry 成功 + activity 失败 → 整体不 raise（活动写失败仅 warning，不阻塞 migration 主成功）。"""
        from unittest.mock import MagicMock, patch

        from bkmonitor.documents.issue import (
            IssueActivityDocument,
            IssueDocument,
            migrate_legacy_active_issues,
        )

        # 构造一个 legacy hit
        fake_hit = MagicMock()
        fake_hit.meta.id = "legacy_issue_1"
        fake_hit.bk_biz_id = "2"
        fake_hit.status = "pending_review"
        scan_iter = iter([fake_hit])

        with (
            patch.object(IssueDocument, "rollover"),
            patch.object(IssueActivityDocument, "rollover"),
            patch.object(IssueDocument, "search") as mock_search,
            patch.object(IssueDocument, "bulk_create") as mock_iss_bulk,
            patch.object(IssueActivityDocument, "bulk_create") as mock_act_bulk,
        ):
            mock_search.return_value.filter.return_value.exclude.return_value.params.return_value.scan.return_value = (
                scan_iter
            )
            # update_docs 第一次失败、第二次成功；activity 永久失败
            mock_iss_bulk.side_effect = [Exception("bulk attempt 1 failed"), None]
            mock_act_bulk.side_effect = Exception("activity failed")

            # 不应 raise（update 成功后 activity 失败仅 warning）
            result = migrate_legacy_active_issues()
            assert result == 1
            assert mock_iss_bulk.call_count == 2  # update retry 1 次后成功
            assert mock_act_bulk.call_count == 1  # activity 仅尝试 1 次

    def test_bulk_update_both_attempts_fail_raises(self):
        """update_docs 两次都失败 → raise IssueMigrationError。"""
        from unittest.mock import MagicMock, patch

        import pytest as _pytest

        from bkmonitor.documents.issue import (
            IssueActivityDocument,
            IssueDocument,
            IssueMigrationError,
            migrate_legacy_active_issues,
        )

        fake_hit = MagicMock()
        fake_hit.meta.id = "legacy_issue_2"
        fake_hit.bk_biz_id = "2"
        fake_hit.status = "unresolved"
        scan_iter = iter([fake_hit])

        with (
            patch.object(IssueDocument, "rollover"),
            patch.object(IssueActivityDocument, "rollover"),
            patch.object(IssueDocument, "search") as mock_search,
            patch.object(IssueDocument, "bulk_create", side_effect=Exception("bulk down")),
        ):
            mock_search.return_value.filter.return_value.exclude.return_value.params.return_value.scan.return_value = (
                scan_iter
            )
            with _pytest.raises(IssueMigrationError, match="update bulk failed permanently"):
                migrate_legacy_active_issues()

    def test_migrate_does_not_set_sentinel_directly(self):
        """migrate 在 post_migrate 路径下不直接 set 哨兵，避免 web/saas role 缺
        REDIS_*_CONF 触发 alarm_backends.core.storage.redis 模块加载期 AttributeError。
        哨兵由 worker 周期任务 _renew_legacy_migration_done_sentinel_if_needed 异步 set。

        覆盖：noop 路径 + 有 legacy 被 RESOLVE 的成功路径，两条都不应调
        _mark_legacy_migration_done。
        """
        from unittest.mock import MagicMock, patch

        from bkmonitor.documents.issue import (
            IssueActivityDocument,
            IssueDocument,
            migrate_legacy_active_issues,
        )

        # 场景 1：noop 路径（无 legacy）
        with (
            patch.object(IssueDocument, "rollover"),
            patch.object(IssueActivityDocument, "rollover"),
            patch.object(IssueDocument, "search") as mock_search,
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
        ):
            mock_search.return_value.filter.return_value.exclude.return_value.params.return_value.scan.return_value = (
                iter([])
            )
            assert migrate_legacy_active_issues() == 0
            mock_mark.assert_not_called()

        # 场景 2：成功路径（1 条 legacy 被 RESOLVE）
        fake_hit = MagicMock()
        fake_hit.meta.id = "legacy_issue_x"
        fake_hit.bk_biz_id = "2"
        fake_hit.status = "unresolved"

        with (
            patch.object(IssueDocument, "rollover"),
            patch.object(IssueActivityDocument, "rollover"),
            patch.object(IssueDocument, "search") as mock_search,
            patch.object(IssueDocument, "bulk_create"),
            patch.object(IssueActivityDocument, "bulk_create"),
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
        ):
            mock_search.return_value.filter.return_value.exclude.return_value.params.return_value.scan.return_value = (
                iter([fake_hit])
            )
            assert migrate_legacy_active_issues() == 1
            mock_mark.assert_not_called()


class TestLegacyMigrationDoneSentinel:
    """processor _legacy_migration_done 短路检查 → 跳过 legacy fallback ES 查询。"""

    def test_sentinel_present_returns_true(self):
        """哨兵 cache 存在 → True。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

        mock_client = MagicMock()
        mock_client.exists.return_value = 1
        with patch("alarm_backends.service.fta_action.issue_processor.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key:
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            assert IssueAggregationProcessor._legacy_migration_done() is True

    def test_sentinel_absent_returns_false(self):
        """哨兵 cache 不存在 → False（走 fallback）。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

        mock_client = MagicMock()
        mock_client.exists.return_value = 0
        with patch("alarm_backends.service.fta_action.issue_processor.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key:
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            assert IssueAggregationProcessor._legacy_migration_done() is False

    def test_redis_failure_fail_open_to_fallback(self):
        """Redis 异常 → fail-open 返回 False（走 fallback 保证正确性）。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

        mock_client = MagicMock()
        mock_client.exists.side_effect = Exception("redis down")
        with patch("alarm_backends.service.fta_action.issue_processor.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key:
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            assert IssueAggregationProcessor._legacy_migration_done() is False


class TestBackfillPerStrategy:
    """sync_issue_alert_stats 改按策略批处理：同一周期同 strategy 仅扫一次 unlinked alerts。"""

    def test_strategy_processed_only_once_per_cycle(self):
        """同一周期内多个同 strategy Issue 只触发一次批量 backfill 调用。

        测试策略：把 ``_process_single_issue`` 内 backfill 之后的 ES 链路（AlertDocument.search）
        强制抛异常，外层 try/except 吃掉，仅断言 backfill 调用次数与 set 状态——
        避免 mock fluent 链路不全导致 ES connection 泄漏（实测会让 pytest 进程占 13GB+）。
        """
        from unittest.mock import patch

        from bkmonitor.documents.issue import IssueDocument
        from alarm_backends.service.fta_action.tasks.issue_tasks import _process_single_issue

        backfilled: set[str] = set()
        with (
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._backfill_unlinked_alerts_for_strategy"
            ) as mock_backfill,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument") as mock_alert_doc,
        ):
            # 短路：backfill 之后 alert_count 重算第一步 AlertDocument.search 直接抛 → 跳过 ES
            mock_alert_doc.search.side_effect = RuntimeError("short-circuit after backfill assertion")

            issue_a = IssueDocument(id="a", strategy_id="100", fingerprint="fp_a", create_time=1000)
            issue_b = IssueDocument(id="b", strategy_id="100", fingerprint="fp_b", create_time=2000)
            issue_c = IssueDocument(id="c", strategy_id="200", fingerprint="fp_c", create_time=3000)

            for iss in (issue_a, issue_b, issue_c):
                try:
                    _process_single_issue(iss, backfilled)
                except RuntimeError:
                    # 预期：backfill 调用完成后 AlertDocument.search 抛短路异常
                    pass

            # strategy 100 仅触发 1 次（issue_b 进来时已在 set 中跳过），strategy 200 触发 1 次
            calls = [call.args[0] for call in mock_backfill.call_args_list]
            assert calls == ["100", "200"]
            assert backfilled == {"100", "200"}

    def test_legacy_issue_skips_backfill(self):
        """fingerprint=null 的 legacy Issue 直接跳过 backfill 与后续统计（保护 legacy 不被污染）。"""
        from unittest.mock import patch

        from bkmonitor.documents.issue import IssueDocument
        from alarm_backends.service.fta_action.tasks.issue_tasks import _process_single_issue

        backfilled: set[str] = set()
        with patch(
            "alarm_backends.service.fta_action.tasks.issue_tasks._backfill_unlinked_alerts_for_strategy"
        ) as mock_backfill:
            legacy = IssueDocument(id="x", strategy_id="100", create_time=1000)  # fingerprint=None
            _process_single_issue(legacy, backfilled)
            mock_backfill.assert_not_called()
            assert backfilled == set()


class TestRenewLegacyMigrationDoneSentinel:
    """周期任务续命哨兵：避免 30 天 TTL 失效后 processor 退化到 fallback ES 查询。"""

    def test_sentinel_present_skips_renewal(self):
        """哨兵已在 → 跳过续命（不触发 ES probe）。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _renew_legacy_migration_done_sentinel_if_needed,
        )

        mock_client = MagicMock()
        mock_client.exists.return_value = 1
        with (
            patch("alarm_backends.core.cache.key.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key,
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument") as mock_issue_doc,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            _renew_legacy_migration_done_sentinel_if_needed()
            mock_mark.assert_not_called()
            mock_issue_doc.search.assert_not_called()  # 不触发 ES probe

    def test_sentinel_absent_with_zero_legacy_renews(self):
        """哨兵不存在 + ES 探查 legacy=0 → 调 _mark_legacy_migration_done 续命。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _renew_legacy_migration_done_sentinel_if_needed,
        )

        mock_client = MagicMock()
        mock_client.exists.return_value = 0
        # mock ES probe 返回 0
        fake_resp = MagicMock()
        fake_resp.hits.total.value = 0

        with (
            patch("alarm_backends.core.cache.key.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key,
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument") as mock_issue_doc,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            mock_issue_doc.search.return_value.filter.return_value.exclude.return_value.params.return_value.execute.return_value = fake_resp
            _renew_legacy_migration_done_sentinel_if_needed()
            mock_mark.assert_called_once()

    def test_sentinel_absent_with_legacy_remaining_warns_not_renews(self):
        """哨兵不存在 + ES 探查 legacy>0 → 仅 warning 不 set（等下次 deploy migrate）。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _renew_legacy_migration_done_sentinel_if_needed,
        )

        mock_client = MagicMock()
        mock_client.exists.return_value = 0
        fake_resp = MagicMock()
        fake_resp.hits.total.value = 5  # 仍有 legacy

        with (
            patch("alarm_backends.core.cache.key.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key,
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument") as mock_issue_doc,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            mock_issue_doc.search.return_value.filter.return_value.exclude.return_value.params.return_value.execute.return_value = fake_resp
            _renew_legacy_migration_done_sentinel_if_needed()
            mock_mark.assert_not_called()

    def test_redis_exists_failure_skips_silently(self):
        """Redis exists 异常 → 跳过续命（fail-safe，不阻塞周期任务）。"""
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _renew_legacy_migration_done_sentinel_if_needed,
        )

        mock_client = MagicMock()
        mock_client.exists.side_effect = Exception("redis down")

        with (
            patch("alarm_backends.core.cache.key.ISSUE_LEGACY_MIGRATION_DONE_KEY") as mock_key,
            patch("bkmonitor.documents.issue._mark_legacy_migration_done") as mock_mark,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument") as mock_issue_doc,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "test_key"
            # 调用不应抛异常
            _renew_legacy_migration_done_sentinel_if_needed()
            mock_mark.assert_not_called()
            mock_issue_doc.search.assert_not_called()


class TestBackfillMatchPriority:
    """``_backfill_unlinked_alerts_for_strategy`` 匹配优先级 + 时间边界 + scan 范围上限。

    alert_hit.to_dict 形态对齐生产链路：``event.extra_info.origin_alarm.data.dimensions``
    含策略层原始命名（与 issue_config.aggregate_dimensions 同层级）。
    """

    def _make_issue_hit(self, issue_id, fingerprint, agg_dims, create_time):
        """构造模拟 IssueDocument scan hit。"""
        from unittest.mock import MagicMock

        h = MagicMock()
        h.meta.id = issue_id
        h.fingerprint = fingerprint
        h.create_time = create_time
        # aggregate_config 用纯 dict 风格（避免 hasattr to_dict 走 mock 路径）
        h.aggregate_config = {"aggregate_dimensions": agg_dims}
        return h

    def _make_alert_hit(self, alert_id, begin_time, dimensions: dict):
        """构造模拟 AlertDocument scan hit，其 to_dict 含 origin_alarm.data.dimensions。"""
        from unittest.mock import MagicMock

        hit = MagicMock()
        hit.id = alert_id
        hit.begin_time = begin_time
        hit.to_dict.return_value = {
            "event": {
                "extra_info": {"origin_alarm": {"data": {"dimensions": dimensions}}},
            }
        }
        return hit

    def test_specific_dims_priority_over_catch_all(self):
        """配置变更后 catch-all I_old 与具体 I_new 共存：alert 应归具体而非 catch-all。"""
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        # 旧 catch-all I_old (snapshot=[])，新具体 I_new (snapshot=["host"])
        i_old = self._make_issue_hit("I_old", "fp_old_catch_all", [], 1000)
        i_new = self._make_issue_hit("I_new", "fp_new_md5", ["host"], 2000)
        alert_hit = self._make_alert_hit("alert_1", 3000, {"host": "X"})

        # mock live config 为 ["host"]（用户已配新），优先匹配新 group
        live_strategy_cache = {"issue_config": {"aggregate_dimensions": ["host"]}}

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value=live_strategy_cache,
            ),
            patch("alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint") as mock_fp,
        ):
            # IssueDocument.search().filter().filter().params().scan() 返回两个 hits
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i_old, i_new])
            )
            # gen_issue_fingerprint：按 agg_dims 算
            mock_fp.side_effect = lambda sid, ad, dims: ("fp_old_catch_all" if not ad else "fp_new_md5")

            _backfill_unlinked_alerts_for_strategy("100")

            # 验证 alert 被回填到 I_new（具体维度），不是 I_old（catch-all）
            assert mock_bulk.called
            call_args = mock_bulk.call_args
            update_docs = call_args[0][0]
            assert len(update_docs) == 1
            assert update_docs[0].issue_id == "I_new"

    def test_alert_earlier_than_issue_create_time_skipped(self):
        """alert.begin_time < issue.create_time → 跳过回填，保留 first_alert_time 时间线一致性。"""
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        # 单个 Issue create_time=2000
        i = self._make_issue_hit("I_x", "fp_x", ["host"], 2000)
        # alert begin_time=1500 < I.create_time
        alert_hit = self._make_alert_hit("alert_early", 1500, {"host": "X"})

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": ["host"]}},
            ),
            patch(
                "alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint",
                return_value="fp_x",
            ),
        ):
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            # 时间边界跳过 → bulk_create 不被调用
            mock_bulk.assert_not_called()

    def test_dim_replacement_live_config_priority(self):
        """维度替换 ["a"] → ["b"]，alert 同时含 a/b 维度：按 live config 优先归到新 ["b"] Issue。"""
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        i_old = self._make_issue_hit("I_a", "fp_a", ["a"], 1000)
        i_new = self._make_issue_hit("I_b", "fp_b", ["b"], 2000)
        alert_hit = self._make_alert_hit("alert_ab", 3000, {"a": "X", "b": "Y"})

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": ["b"]}},
            ),
            patch("alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint") as mock_fp,
        ):
            # 按 agg_dims 返回不同 fp
            mock_fp.side_effect = lambda sid, ad, dims: "fp_a" if ad == ["a"] else "fp_b"
            # I_old 先 scan（旧 Issue create_time 早）
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i_old, i_new])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            assert mock_bulk.called
            update_docs = mock_bulk.call_args[0][0]
            assert len(update_docs) == 1
            # 应归到 live config 对应的 I_b，而非 dict 顺序在前的 I_a
            assert update_docs[0].issue_id == "I_b"

    def test_early_break_prevents_fallback_to_broader_group(self):
        """alert 早于 live group 对应 Issue → 永久 unlinked，**不**回退到更通用 group 错绑（锁定决策）。

        场景：
          - 旧 catch-all I_old (snapshot=[], create_time=500)
          - 新具体 I_new (snapshot=["host"], create_time=2000)，live config=["host"]
          - alert (host=X, begin_time=1000) — 晚于 I_old 但早于 I_new
        预期：live 优先匹配 I_new → 时间不符 → break，**不回退**到 catch-all I_old；alert 保持 unlinked
        """
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        i_old = self._make_issue_hit("I_old", "fp_old", [], 500)
        i_new = self._make_issue_hit("I_new", "fp_new", ["host"], 2000)
        alert_hit = self._make_alert_hit("alert_mid", 1000, {"host": "X"})  # 早于 I_new (2000) 但晚于 I_old (500)

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": ["host"]}},
            ),
            patch("alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint") as mock_fp,
        ):
            mock_fp.side_effect = lambda sid, ad, dims: "fp_new" if ad == ["host"] else "fp_old"
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i_old, i_new])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            # alert 永久 unlinked：不回退到 catch-all I_old（锁定决策）
            mock_bulk.assert_not_called()

    def test_issue_config_missing_falls_back_to_len_desc(self):
        """策略禁用 Issue 聚合（issue_config 缺失）但仍有历史活跃 Issue：live=None 退化按 len 降序。

        当 issue_config 缺失时不应让 catch-all 永远优先（live_agg_dims_tuple = None 走 fallback）。
        """
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        # 历史 catch-all I_old + 历史具体 I_new；live 策略已无 issue_config
        i_old = self._make_issue_hit("I_old", "fp_old", [], 1000)
        i_new = self._make_issue_hit("I_new", "fp_new", ["host"], 2000)
        alert_hit = self._make_alert_hit("alert_legacy", 3000, {"host": "X"})

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={},  # issue_config 缺失
            ),
            patch("alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint") as mock_fp,
        ):
            mock_fp.side_effect = lambda sid, ad, dims: "fp_new" if ad == ["host"] else "fp_old"
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i_old, i_new])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            assert mock_bulk.called
            update_docs = mock_bulk.call_args[0][0]
            # live=None 退化按 len 降序，具体 I_new (len=1) 优先于 catch-all I_old (len=0)
            assert update_docs[0].issue_id == "I_new"

    def test_alert_missing_origin_alarm_skipped_when_no_catch_all_group(self):
        """无 catch-all group 时，alert 缺 origin_alarm → backfill 跳过该条 alert。

        与 process 主路径"维度凑不齐 → fingerprint=None → 跳过"语义一致，
        backfill 不应错绑到任何 Issue。
        """
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        i = self._make_issue_hit("I_x", "fp_x", ["host"], 1000)
        # alert 完全没有 event.extra_info.origin_alarm 结构（典型第三方告警）
        alert_hit = MagicMock()
        alert_hit.id = "alert_third_party"
        alert_hit.begin_time = 3000
        alert_hit.to_dict.return_value = {"event": {}}

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": ["host"]}},
            ),
        ):
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            mock_bulk.assert_not_called()

    def test_catch_all_group_backfills_alert_without_origin_alarm(self):
        """有 catch-all Issue (snapshot=[]) 时，alert 即使缺 origin_alarm 也应被 backfill 到 catch-all。

        catch-all group 不读 data_dimensions（aggregate_dimensions=[] 时直接 ``count_md5(["strategy:{id}"])``），
        与 process 主路径语义一致：catch-all Issue 必中策略下任何告警，无论维度是否齐全。
        """
        from unittest.mock import MagicMock, patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _backfill_unlinked_alerts_for_strategy,
        )

        # 仅一个 catch-all Issue
        i_catch_all = self._make_issue_hit("I_catch_all", "fp_catch_all", [], 1000)
        # alert 完全没有 origin_alarm 结构
        alert_hit = MagicMock()
        alert_hit.id = "alert_no_dim"
        alert_hit.begin_time = 3000
        alert_hit.to_dict.return_value = {"event": {}}

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([[alert_hit]]),
            ),
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.bulk_create") as mock_bulk,
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": []}},
            ),
            patch("alarm_backends.service.fta_action.issue_processor.gen_issue_fingerprint") as mock_fp,
        ):
            mock_fp.side_effect = lambda sid, ad, dims: "fp_catch_all" if not ad else None
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i_catch_all])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            assert mock_bulk.called, "catch-all Issue 应能 backfill 缺 origin_alarm 的 alert"
            update_docs = mock_bulk.call_args[0][0]
            assert len(update_docs) == 1
            assert update_docs[0].issue_id == "I_catch_all"

    def test_scan_range_capped_to_7_days(self):
        """earliest_create_time 早于 7 天前 → scan 下界缩窄为 now - 7 天，避免范围爆炸。"""
        import time as _time
        from unittest.mock import patch

        from alarm_backends.service.fta_action.tasks.issue_tasks import (
            _BACKFILL_ALERT_SCAN_MAX_LOOKBACK_SEC,
            _backfill_unlinked_alerts_for_strategy,
        )

        old_create_time = int(_time.time()) - 30 * 86400
        i = self._make_issue_hit("I_old", "fp_x", ["host"], old_create_time)

        with (
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.IssueDocument.search") as mock_search,
            patch("alarm_backends.service.fta_action.tasks.issue_tasks.AlertDocument.search") as mock_alert_search,
            patch(
                "alarm_backends.service.fta_action.tasks.issue_tasks._iter_alert_hit_batches",
                return_value=iter([]),
            ),
            patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
                return_value={"issue_config": {"aggregate_dimensions": ["host"]}},
            ),
        ):
            mock_search.return_value.filter.return_value.filter.return_value.params.return_value.scan.return_value = (
                iter([i])
            )

            _backfill_unlinked_alerts_for_strategy("100")

            range_call = mock_alert_search.return_value.filter.return_value.filter.call_args
            range_kwargs = range_call.kwargs
            begin_time_filter = range_kwargs.get("begin_time", {})
            now = int(_time.time())
            expected_lower = now - _BACKFILL_ALERT_SCAN_MAX_LOOKBACK_SEC
            actual_lower = begin_time_filter.get("gte")
            assert abs(actual_lower - expected_lower) < 5, (
                f"expected scan lower bound ≈ now-7d ({expected_lower}), got {actual_lower}; "
                f"earliest_create_time was {old_create_time} (30d ago)"
            )


class TestActiveCountCacheStampedeProtection:
    """``_check_active_issue_count`` 防 cache stampede（性能 review M1）：
    cache miss 时 SET NX EX 短锁让一个 worker 探 ES，其他 worker 跳过本次观测；
    cache 写回 TTL 加 ±20% jitter 打散周期性同步失效。
    """

    def _make_proc(self):
        from unittest.mock import MagicMock

        from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

        proc = IssueAggregationProcessor.__new__(IssueAggregationProcessor)
        proc.strategy_id = 100
        proc.strategy = {"bk_biz_id": 2}
        proc.alert = MagicMock()
        proc.alert.id = "a1"
        return proc

    def test_cache_miss_acquires_probe_lock_then_writes_jittered_ttl(self):
        """cache miss + 抢到 probe_lock → 走 ES count + jittered TTL 写回。"""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.get.return_value = None  # cache miss
        mock_client.set.return_value = True  # probe_lock 抢到 + cache set 都成功

        proc = self._make_proc()

        with (
            patch("alarm_backends.service.fta_action.issue_processor.ISSUE_ACTIVE_COUNT_KEY") as mock_key,
            patch("alarm_backends.service.fta_action.issue_processor.IssueDocument") as mock_doc,
            patch("alarm_backends.service.fta_action.issue_processor.settings") as mock_settings,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "ck"
            mock_key.ttl = 300
            mock_settings.ISSUE_MAX_ACTIVE_PER_STRATEGY = 500
            mock_doc.search.return_value.filter.return_value.filter.return_value.count.return_value = 100

            proc._check_active_issue_count()

            set_calls = mock_client.set.call_args_list
            # 第 1 次 set 是 probe_lock：nx=True, ex=10
            assert set_calls[0].kwargs.get("nx") is True
            assert set_calls[0].kwargs.get("ex") == 10
            # 第 2 次 set 是 cache 写回：jittered TTL ∈ [240, 360]
            cache_ttl = set_calls[1].kwargs.get("ex")
            assert 240 <= cache_ttl <= 360, f"jittered TTL {cache_ttl} 不在 [240, 360]"

    def test_cache_miss_probe_lock_failed_skips_es_count(self):
        """cache miss + probe_lock 抢不到（其他 worker 已抢）→ 跳过 ES count（防穿透核心）。"""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_client.set.return_value = False  # probe_lock 抢不到

        proc = self._make_proc()

        with (
            patch("alarm_backends.service.fta_action.issue_processor.ISSUE_ACTIVE_COUNT_KEY") as mock_key,
            patch("alarm_backends.service.fta_action.issue_processor.IssueDocument") as mock_doc,
            patch("alarm_backends.service.fta_action.issue_processor.settings") as mock_settings,
            patch("alarm_backends.service.fta_action.issue_processor.metrics") as mock_metrics,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "ck"
            mock_key.ttl = 300
            mock_settings.ISSUE_MAX_ACTIVE_PER_STRATEGY = 500

            proc._check_active_issue_count()

            mock_doc.search.assert_not_called()
            mock_metrics.ISSUE_FINGERPRINT_BLOCKED.labels.assert_not_called()

    def test_jittered_ttl_distributes_within_range(self):
        """统计性验证：20 次采样 TTL 都在 [240, 360]，且至少有 2 个不同值（真随机）。"""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_client.set.return_value = True

        proc = self._make_proc()

        with (
            patch("alarm_backends.service.fta_action.issue_processor.ISSUE_ACTIVE_COUNT_KEY") as mock_key,
            patch("alarm_backends.service.fta_action.issue_processor.IssueDocument") as mock_doc,
            patch("alarm_backends.service.fta_action.issue_processor.settings") as mock_settings,
        ):
            mock_key.client = mock_client
            mock_key.get_key.return_value = "ck"
            mock_key.ttl = 300
            mock_settings.ISSUE_MAX_ACTIVE_PER_STRATEGY = 500
            mock_doc.search.return_value.filter.return_value.filter.return_value.count.return_value = 50

            ttl_samples = []
            for _ in range(20):
                mock_client.reset_mock()
                proc._check_active_issue_count()
                ttl_samples.append(mock_client.set.call_args_list[1].kwargs.get("ex"))

            assert all(240 <= t <= 360 for t in ttl_samples), f"out-of-range TTL: {ttl_samples}"
            assert len(set(ttl_samples)) > 1, "TTL not jittered"


class TestBuildIssueDefaultName:
    """build_issue_default_name 默认名称生成器单测：覆盖空维度退化 / 单值 / 多值排序 / 截断 / 回归前缀。"""

    def test_no_dimension_no_suffix(self):
        """dimension_values 为空（aggregate_dimensions=[] 退化路径）→ 仅 strategy_name。"""
        assert build_issue_default_name("CPU 异常", {}, False) == "CPU 异常"

    def test_single_dimension_appends_value(self):
        """单维度值追加为后缀。"""
        assert build_issue_default_name("CPU 异常", {"bk_host_id": "9185731"}, False) == "CPU 异常 - 9185731"

    def test_multiple_dimensions_sorted_by_key(self):
        """多维度按 key 排序后拼接 value，保证同 fingerprint 名称稳定。"""
        # key 排序：app_name → service_name；输入顺序倒置不影响结果
        result = build_issue_default_name("延迟告警", {"service_name": "order", "app_name": "nf"}, False)
        assert result == "延迟告警 - nf | order"

    def test_regression_prefix(self):
        """回归 Issue 加 [回归] 前缀，dim 后缀正常。"""
        assert build_issue_default_name("CPU 异常", {"bk_host_id": "9185731"}, True) == "[回归] CPU 异常 - 9185731"

    def test_regression_no_dimension(self):
        """回归 + 空 dim：仅前缀，无后缀。"""
        assert build_issue_default_name("CPU 异常", {}, True) == "[回归] CPU 异常"

    def test_long_value_truncated(self):
        """单维度值超过 40 字符时截断为 prefix... 避免列表页拉宽。"""
        long_val = "a" * 100
        result = build_issue_default_name("test", {"key": long_val}, False)
        # 后缀应为 37 字符 + "..."（共 40 字符）
        suffix = result.split(" - ", 1)[1]
        assert suffix == "a" * 37 + "..."
        assert len(suffix) == 40

    def test_short_value_not_truncated(self):
        """正常长度值不截断。"""
        result = build_issue_default_name("test", {"key": "a" * 40}, False)
        assert result.endswith("a" * 40)

    def test_int_value_stringified(self):
        """int 维度值自动转 str 拼接。"""
        assert build_issue_default_name("test", {"key": 12345}, False) == "test - 12345"
