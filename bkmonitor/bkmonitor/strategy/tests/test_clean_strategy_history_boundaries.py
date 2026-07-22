# -*- coding: utf-8 -*-  # noqa: UP009
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import router
from django.utils import timezone

from bkmonitor.models import StrategyHistoryModel
from bkmonitor.models import StrategyModel
from bkmonitor.strategy.history import CleanStrategyHistoryParams
from bkmonitor.strategy.history import _collect_keep_history_ids
from bkmonitor.strategy.history import _delete_queryset_in_batches
from bkmonitor.strategy.history import clean_strategy_history

FIXED_NOW = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
DAYS = 30
BEFORE = FIXED_NOW - timedelta(days=DAYS)
OLD = BEFORE - timedelta(hours=1)
OLDER = BEFORE - timedelta(hours=2)
OLDEST = BEFORE - timedelta(hours=3)
RECENT = FIXED_NOW - timedelta(hours=1)
CMD = "clean_strategy_history"

pytestmark = pytest.mark.django_db(databases=("default", "monitor_api"))


def _freeze_now(monkeypatch, now: datetime = FIXED_NOW) -> datetime:
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    return now


def _create_strategy(name: str) -> StrategyModel:
    return StrategyModel.objects.create(
        bk_biz_id=2,
        name=name,
        scenario="os",
        type=StrategyModel.StrategyType.Monitor,
    )


def _create_history(
    strategy_id: int,
    create_time: datetime,
    *,
    operate: str = "update",
    status: bool = True,
    content: dict | None = None,
    message: str = "",
) -> StrategyHistoryModel:
    history = StrategyHistoryModel.objects.create(
        strategy_id=strategy_id,
        create_user="admin",
        operate=operate,
        status=status,
        content=content if content is not None else {"id": strategy_id},
        message=message,
    )
    StrategyHistoryModel.objects.filter(id=history.id).update(create_time=create_time)
    history.refresh_from_db()
    return history


def _remaining_ids() -> set[int]:
    return set(StrategyHistoryModel.objects.values_list("id", flat=True))


def _params(**kwargs) -> CleanStrategyHistoryParams:
    defaults = {"days": DAYS, "batch_size": 2, "keep_latest_snapshots": 1}
    defaults.update(kwargs)
    return CleanStrategyHistoryParams(**defaults)


class TestCleanStrategyHistoryBoundaryMatrix:
    """策略历史删除大边界套件：截止窗口、保留规则、分片删除与命令端到端。"""

    def test_cutoff_boundary_equal_before_is_not_deleted(self, monkeypatch):
        """create_time == before 不进入清理窗口（严格 <）。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("cutoff-eq")
        at_boundary = _create_history(strategy.id, BEFORE, status=False)
        older = _create_history(strategy.id, OLD, status=False)

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {at_boundary.id}
        assert not StrategyHistoryModel.objects.filter(id=older.id).exists()

    def test_recent_records_outside_window_never_deleted(self, monkeypatch):
        """窗口内历史全部保留，清理应返回 0。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("recent-keep-all")
        recent_a = _create_history(strategy.id, RECENT - timedelta(minutes=1))
        recent_b = _create_history(strategy.id, RECENT)

        deleted = clean_strategy_history(_params())

        assert deleted == 0
        assert _remaining_ids() == {recent_a.id, recent_b.id}

    def test_empty_content_is_not_recoverable_snapshot(self, monkeypatch):
        """空 content 不能作为可恢复快照淘汰更早成功记录。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("empty-content")
        kept = _create_history(strategy.id, OLDEST)
        empty = _create_history(strategy.id, OLD, content={})

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept.id}
        assert not StrategyHistoryModel.objects.filter(id=empty.id).exists()

    def test_failed_update_with_traceback_is_never_kept_as_snapshot(self, monkeypatch):
        """失败更新即使时间更新也不能成为保留快照。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("failed-trace")
        kept = _create_history(strategy.id, OLDEST)
        failed = _create_history(
            strategy.id,
            OLD,
            status=False,
            message="Traceback (most recent call last):\nValueError",
        )

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept.id}
        assert not StrategyHistoryModel.objects.filter(id=failed.id).exists()

    def test_legacy_empty_message_with_failed_status_is_not_recoverable(self, monkeypatch):
        """存量失败记录即使 message 为空，也不能按成功快照保留。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("legacy-empty")
        kept = _create_history(strategy.id, OLDEST)
        legacy_failed = _create_history(strategy.id, OLD, status=False, message="")

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept.id}
        assert not StrategyHistoryModel.objects.filter(id=legacy_failed.id).exists()

    def test_recent_failed_record_does_not_steal_keep_slot(self, monkeypatch):
        """窗口内的失败记录不占用 keep_latest_snapshots 名额。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("failed-recent")
        older = _create_history(strategy.id, OLDEST)
        kept = _create_history(strategy.id, OLD)
        recent_failed = _create_history(strategy.id, RECENT, status=False, message="")

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept.id, recent_failed.id}
        assert not StrategyHistoryModel.objects.filter(id=older.id).exists()

    def test_bulk_update_status_true_is_preferred_over_older_update(self, monkeypatch):
        """同策略多条成功快照时，保留全局最新一条。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("bulk-prefer")
        old_update = _create_history(strategy.id, OLDEST, operate="update")
        kept_bulk = _create_history(strategy.id, OLD, operate="bulk_update")

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept_bulk.id}
        assert not StrategyHistoryModel.objects.filter(id=old_update.id).exists()

    def test_create_snapshot_can_be_the_only_kept_record(self, monkeypatch):
        """现存策略只保留成功快照，不保留过期 delete。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("create-only")
        create_snap = _create_history(strategy.id, OLD, operate="create")
        delete_row = _create_history(strategy.id, OLD + timedelta(minutes=1), operate="delete", status=False)

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {create_snap.id}
        assert not StrategyHistoryModel.objects.filter(id=delete_row.id).exists()

    def test_deleted_strategy_keeps_latest_snapshot_and_latest_delete(self, monkeypatch):
        """已删除策略保留最新成功快照和最新删除事实。"""
        _freeze_now(monkeypatch)
        deleted_id = 910001
        old_snap = _create_history(deleted_id, OLDEST, operate="update")
        kept_snap = _create_history(deleted_id, OLDER, operate="bulk_update")
        old_delete = _create_history(deleted_id, OLD - timedelta(minutes=2), operate="delete", status=False)
        kept_delete = _create_history(deleted_id, OLD, operate="bulk_delete", status=False)

        deleted = clean_strategy_history(_params())

        assert deleted == 2
        assert _remaining_ids() == {kept_snap.id, kept_delete.id}
        assert not StrategyHistoryModel.objects.filter(id__in=[old_snap.id, old_delete.id]).exists()

    def test_deleted_strategy_with_only_delete_rows_keeps_latest_delete(self, monkeypatch):
        """仅有删除记录时，仍保留最新一条删除事实。"""
        _freeze_now(monkeypatch)
        deleted_id = 910002
        old_delete = _create_history(deleted_id, OLDEST, operate="delete", status=False)
        kept_delete = _create_history(deleted_id, OLD, operate="delete", status=False)

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {kept_delete.id}
        assert not StrategyHistoryModel.objects.filter(id=old_delete.id).exists()

    def test_same_create_time_prefers_greater_id(self, monkeypatch):
        """相同 create_time 时按更大 id 作为更新记录保留。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("tie-break")
        first = _create_history(strategy.id, OLD, content={"v": 1})
        second = _create_history(strategy.id, OLD, content={"v": 2})
        assert second.id > first.id

        deleted = clean_strategy_history(_params())

        assert deleted == 1
        assert _remaining_ids() == {second.id}

    def test_strategy_id_zero_full_cleanup_keeps_latest_recoverable(self, monkeypatch):
        """strategy_id=0 也要走完整清理路径，并保留最新成功快照。"""
        _freeze_now(monkeypatch)
        older = _create_history(0, OLDEST, operate="create")
        kept = _create_history(0, OLD, operate="create")
        failed = _create_history(
            0,
            OLD + timedelta(minutes=1),
            operate="create",
            status=False,
            message="create failed",
        )

        deleted = clean_strategy_history(_params(batch_size=1))

        assert deleted == 2
        assert _remaining_ids() == {kept.id}
        assert not StrategyHistoryModel.objects.filter(id__in=[older.id, failed.id]).exists()

    def test_multi_chunk_cleanup_does_not_skip_strategy_groups(self, monkeypatch):
        """跨多个 strategy_id chunk 时，每组都应保留最新成功快照。"""
        _freeze_now(monkeypatch)
        strategies = [_create_strategy(f"chunk-{i}") for i in range(5)]
        kept = []
        removable = []
        for strategy in strategies:
            removable.append(_create_history(strategy.id, OLDEST).id)
            kept.append(_create_history(strategy.id, OLD).id)

        monkeypatch.setattr("bkmonitor.strategy.history.STRATEGY_ID_CHUNK_SIZE", 2)
        deleted = clean_strategy_history(_params(batch_size=1))

        assert deleted == 5
        assert _remaining_ids() == set(kept)
        assert not StrategyHistoryModel.objects.filter(id__in=removable).exists()

    def test_keyset_delete_handles_non_contiguous_pks(self, monkeypatch):
        """按主键 keyset 分页删除时，pk 空洞不应导致漏删。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("pk-gaps")
        row_ids = []
        for minute in (5, 4, 3, 2, 1):
            row_ids.append(_create_history(strategy.id, OLD - timedelta(minutes=minute)).id)

        filler = _create_history(strategy.id + 100000, OLD)
        StrategyHistoryModel.objects.filter(id=filler.id).delete()

        queryset = StrategyHistoryModel.objects.filter(id__in=row_ids[:-1])
        deleted = _delete_queryset_in_batches(queryset, batch_size=2)

        assert deleted == 4
        assert list(StrategyHistoryModel.objects.filter(id__in=row_ids).values_list("id", flat=True)) == [row_ids[-1]]

    def test_keyset_delete_preserves_explicit_database_alias(self, monkeypatch):
        """删除必须沿用传入 queryset 的数据库，不能重新经过写路由。"""
        strategy = _create_strategy("explicit-database-alias")
        history = _create_history(strategy.id, OLD)
        queryset = StrategyHistoryModel.objects.using("monitor_api").filter(id=history.id)
        monkeypatch.setattr(router, "db_for_write", lambda *_args, **_kwargs: "default")

        deleted = _delete_queryset_in_batches(queryset, batch_size=1)

        assert deleted == 1
        assert not StrategyHistoryModel.objects.using("monitor_api").filter(id=history.id).exists()

    def test_window_outside_latest_recoverable_allows_deleting_all_old_snapshots(self, monkeypatch):
        """窗口外已有更新成功快照时，过期旧快照可全部删除。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("outside-latest")
        old_a = _create_history(strategy.id, OLDEST)
        old_b = _create_history(strategy.id, OLD)
        recent = _create_history(strategy.id, RECENT, operate="bulk_update")

        deleted = clean_strategy_history(_params())

        assert deleted == 2
        assert _remaining_ids() == {recent.id}
        assert not StrategyHistoryModel.objects.filter(id__in=[old_a.id, old_b.id]).exists()

    def test_keep_latest_snapshots_counts_recent_and_expired_together(self, monkeypatch):
        """keep_latest_snapshots 统计全局成功快照，窗口内快照会挤占窗外保留名额。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("keep-n-window")
        expired_old = _create_history(strategy.id, OLDEST, operate="create")
        expired_kept = _create_history(strategy.id, OLD)
        recent = _create_history(strategy.id, RECENT, operate="bulk_update")

        deleted = clean_strategy_history(_params(keep_latest_snapshots=2))

        assert deleted == 1
        assert _remaining_ids() == {expired_kept.id, recent.id}
        assert not StrategyHistoryModel.objects.filter(id=expired_old.id).exists()

    def test_mixed_operate_types_only_recoverable_ops_compete(self, monkeypatch):
        """只有 create/update/bulk_update 成功记录参与快照竞选。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("mixed-ops")
        create_row = _create_history(strategy.id, OLDEST, operate="create")
        update_row = _create_history(strategy.id, OLDER, operate="update")
        bulk_row = _create_history(strategy.id, OLD, operate="bulk_update")
        delete_row = _create_history(strategy.id, OLD + timedelta(minutes=1), operate="delete", status=False)

        deleted = clean_strategy_history(_params())

        assert deleted == 3
        assert _remaining_ids() == {bulk_row.id}
        assert not StrategyHistoryModel.objects.filter(id__in=[create_row.id, update_row.id, delete_row.id]).exists()

    def test_collect_keep_history_ids_for_existing_strategy_excludes_delete(self, monkeypatch):
        """现存策略的 keep 集合不应包含 delete 记录。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("keep-ids-existing")
        snap = _create_history(strategy.id, OLD)
        delete_row = _create_history(strategy.id, OLD + timedelta(minutes=1), operate="delete", status=False)

        keep_ids = _collect_keep_history_ids([strategy.id], keep_latest_snapshots=1)

        assert keep_ids == {snap.id}
        assert delete_row.id not in keep_ids

    def test_cleanup_is_idempotent_on_mixed_dataset(self, monkeypatch):
        """混合数据集重复清理时，第二次应删除 0 条。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("idempotent-matrix")
        _create_history(strategy.id, OLDEST)
        kept = _create_history(strategy.id, OLD, operate="bulk_update")
        deleted_id = 910010
        _create_history(deleted_id, OLDEST, operate="update")
        kept_snap = _create_history(deleted_id, OLDER, operate="update")
        kept_delete = _create_history(deleted_id, OLD, operate="delete", status=False)

        params = _params(batch_size=1)
        first = clean_strategy_history(params)
        second = clean_strategy_history(params)

        assert first == 2
        assert second == 0
        assert _remaining_ids() == {kept.id, kept_snap.id, kept_delete.id}

    def test_command_real_delete_end_to_end(self, monkeypatch):
        """管理命令应真正删除过期冗余历史并输出删除数量。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("cmd-real")
        old = _create_history(strategy.id, OLDEST)
        kept = _create_history(strategy.id, OLD)
        stdout = StringIO()

        call_command(CMD, days=DAYS, batch_size=1, keep_latest_snapshots=1, execute=True, stdout=stdout)

        assert "deleted 1 records" in stdout.getvalue()
        assert not StrategyHistoryModel.objects.filter(id=old.id).exists()
        assert StrategyHistoryModel.objects.filter(id=kept.id).exists()

    def test_command_rejects_non_positive_keep_latest_snapshots(self):
        """命令层应将非法 keep_latest_snapshots 转为 CommandError。"""
        with pytest.raises(CommandError, match="must be a positive integer"):
            call_command(CMD, days=DAYS, keep_latest_snapshots=0, stdout=StringIO())

    def test_params_reject_bool_and_non_int_values(self):
        """bool / 浮点 / 字符串都不能冒充正整数参数。"""
        for kwargs in (
            {"days": True, "batch_size": 1000, "keep_latest_snapshots": 1},
            {"days": 30, "batch_size": 1.5, "keep_latest_snapshots": 1},
            {"days": 30, "batch_size": 1000, "keep_latest_snapshots": "1"},
        ):
            with pytest.raises(ValueError, match="must be a positive integer"):
                CleanStrategyHistoryParams(**kwargs)

    def test_params_reject_non_boolean_dry_run(self):
        """dry_run 只接受布尔值，避免字符串参数误触真实删除。"""
        with pytest.raises(ValueError, match="dry_run must be a boolean"):
            CleanStrategyHistoryParams(days=30, dry_run="true")

    def test_no_old_histories_returns_zero(self, monkeypatch):
        """没有过期历史时返回 0。"""
        _freeze_now(monkeypatch)
        strategy = _create_strategy("no-old")
        recent = _create_history(strategy.id, RECENT)

        assert clean_strategy_history(_params()) == 0
        assert _remaining_ids() == {recent.id}

    def test_full_matrix_across_existing_deleted_zero_and_chunks(self, monkeypatch):
        """综合矩阵：现存策略 / 已删策略 / strategy_id=0 / 多 chunk / 窗口内噪声。"""
        _freeze_now(monkeypatch)
        monkeypatch.setattr("bkmonitor.strategy.history.STRATEGY_ID_CHUNK_SIZE", 2)

        existing = _create_strategy("matrix-existing")
        existing_old = _create_history(existing.id, OLDEST, operate="update")
        existing_kept = _create_history(existing.id, OLD, operate="bulk_update")

        failed_noise_strategy = _create_strategy("matrix-failed")
        failed_old = _create_history(
            failed_noise_strategy.id,
            OLDEST,
            operate="update",
            status=False,
            message="update failed",
        )
        failed_kept = _create_history(failed_noise_strategy.id, OLD, operate="update")

        deleted_id = 910003
        deleted_old_snap = _create_history(deleted_id, OLDEST, operate="update")
        deleted_kept_snap = _create_history(deleted_id, OLDER, operate="update")
        deleted_old_del = _create_history(deleted_id, OLD - timedelta(minutes=1), operate="delete", status=False)
        deleted_kept_del = _create_history(deleted_id, OLD, operate="bulk_delete", status=False)

        zero_old = _create_history(0, OLDEST, operate="create")
        zero_kept = _create_history(0, OLD, operate="create")

        recent_noise = _create_history(existing.id, RECENT, status=False, message="")

        deleted = clean_strategy_history(_params(batch_size=1))

        assert deleted == 5
        assert _remaining_ids() == {
            existing_kept.id,
            failed_kept.id,
            deleted_kept_snap.id,
            deleted_kept_del.id,
            zero_kept.id,
            recent_noise.id,
        }
        assert not StrategyHistoryModel.objects.filter(
            id__in=[
                existing_old.id,
                failed_old.id,
                deleted_old_snap.id,
                deleted_old_del.id,
                zero_old.id,
            ]
        ).exists()
