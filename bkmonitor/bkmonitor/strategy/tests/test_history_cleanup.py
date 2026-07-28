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

import pytest
from django.utils import timezone

from bkmonitor.models import StrategyHistoryModel
from bkmonitor.models import StrategyModel
from bkmonitor.strategy.history import CleanStrategyHistoryParams
from bkmonitor.strategy.history import clean_strategy_history
from bkmonitor.strategy.history import clean_strategy_history_compat

pytestmark = pytest.mark.django_db(databases=("default", "monitor_api"))


def _create_strategy(name: str) -> StrategyModel:
    """创建清理测试使用的最小策略记录。"""
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
    """创建历史并将自动生成的时间调整到指定测试时间。"""
    history = StrategyHistoryModel.objects.create(
        strategy_id=strategy_id,
        create_user="admin",
        operate=operate,
        status=status,
        content=content if content is not None else {"id": strategy_id},
        message=message,
    )
    StrategyHistoryModel.objects.filter(id=history.id).update(create_time=create_time)
    history.create_time = create_time
    return history


def test_compat_cleanup_keeps_legacy_bulk_update_without_displacing_confirmed_snapshot(monkeypatch):
    """兼容快照使用独立保留名额，不能挤掉已确认成功快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("legacy-bulk-status")

    old_confirmed_snapshot = _create_history(strategy.id, now - timedelta(days=45))
    kept_legacy_update = _create_history(
        strategy.id,
        now - timedelta(days=40),
        status=False,
        message="",
    )
    stale_legacy_delete = _create_history(
        strategy.id,
        now - timedelta(days=35),
        operate="delete",
        status=False,
        content={},
        message="",
    )
    confirmed_failure = _create_history(
        strategy.id,
        now - timedelta(days=34),
        status=False,
        message="bulk update failed",
    )

    deleted = clean_strategy_history_compat(CleanStrategyHistoryParams(days=30, batch_size=1))

    assert deleted == 2
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {
        old_confirmed_snapshot.id,
        kept_legacy_update.id,
    }
    assert not StrategyHistoryModel.objects.filter(id=kept_legacy_update.id, status=True).exists()
    assert not StrategyHistoryModel.objects.filter(id=stale_legacy_delete.id).exists()
    assert not StrategyHistoryModel.objects.filter(id=confirmed_failure.id).exists()


def test_compat_cleanup_keeps_latest_delete_for_deleted_strategy(monkeypatch):
    """兼容清理为已删除策略保留最新删除记录，不依赖 status。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    deleted_strategy_id = 900099

    snapshot = _create_history(deleted_strategy_id, now - timedelta(days=45))
    old_delete = _create_history(
        deleted_strategy_id,
        now - timedelta(days=40),
        operate="delete",
        status=False,
        content={},
    )
    kept_delete = _create_history(
        deleted_strategy_id,
        now - timedelta(days=35),
        operate="delete",
        status=False,
        content={},
    )

    deleted = clean_strategy_history_compat(CleanStrategyHistoryParams(days=30, batch_size=1))

    assert deleted == 1
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {snapshot.id, kept_delete.id}
    assert not StrategyHistoryModel.objects.filter(id=old_delete.id).exists()


def test_compat_cleanup_does_not_treat_recent_failed_update_as_legacy(monkeypatch):
    """窗口内普通失败更新不能挤掉窗口外已确认成功的快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("recent-failed-update")

    confirmed_snapshot = _create_history(strategy.id, now - timedelta(days=40))
    recent_failed_update = _create_history(
        strategy.id,
        now - timedelta(days=10),
        status=False,
        message="",
    )

    deleted = clean_strategy_history_compat(CleanStrategyHistoryParams(days=30))

    assert deleted == 0
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {
        confirmed_snapshot.id,
        recent_failed_update.id,
    }


def test_compat_cleanup_keeps_latest_legacy_when_no_confirmed_snapshot(monkeypatch):
    """无确认成功快照时，兼容清理仍应保留最新有内容的旧批量 update。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("legacy-only")

    older_legacy = _create_history(
        strategy.id,
        now - timedelta(days=45),
        status=False,
        message="",
    )
    kept_legacy = _create_history(
        strategy.id,
        now - timedelta(days=35),
        status=False,
        message="",
    )

    deleted = clean_strategy_history_compat(CleanStrategyHistoryParams(days=30, batch_size=1))

    assert deleted == 1
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_legacy.id}
    assert not StrategyHistoryModel.objects.filter(id=older_legacy.id).exists()


def test_compat_cleanup_excludes_empty_content_legacy_from_keep_slots(monkeypatch):
    """空 content 的旧批量 update 不能占用兼容保留名额。

    把空 content 行放在更新时间，若其误占名额会挤掉更早但仍可恢复的 legacy 快照。
    """
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("empty-legacy-content")

    kept_legacy = _create_history(
        strategy.id,
        now - timedelta(days=40),
        status=False,
        message="",
    )
    empty_legacy = _create_history(
        strategy.id,
        now - timedelta(days=35),
        status=False,
        content={},
        message="",
    )

    deleted = clean_strategy_history_compat(CleanStrategyHistoryParams(days=30, batch_size=1))

    assert deleted == 1
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_legacy.id}
    assert not StrategyHistoryModel.objects.filter(id=empty_legacy.id).exists()


def test_existing_strategy_keeps_latest_successful_snapshot(monkeypatch):
    """现存策略应只保留全局最新的成功配置快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("existing-strategy")

    old_create = _create_history(strategy.id, now - timedelta(days=40), operate="create")
    kept_snapshot = _create_history(strategy.id, now - timedelta(days=35), operate="bulk_update")
    failed_update = _create_history(strategy.id, now - timedelta(days=34), status=False)
    stale_delete = _create_history(strategy.id, now - timedelta(days=33), operate="delete")

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30, batch_size=2))

    assert deleted == 3
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_snapshot.id}
    assert not StrategyHistoryModel.objects.filter(id__in=[old_create.id, failed_update.id, stale_delete.id]).exists()


def test_deleted_strategy_keeps_latest_snapshot_and_latest_delete(monkeypatch):
    """已删除策略应保留最新成功快照和最新删除事实。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy_id = 900001

    old_snapshot = _create_history(strategy_id, now - timedelta(days=45), operate="update")
    kept_snapshot = _create_history(strategy_id, now - timedelta(days=40), operate="bulk_update")
    old_delete = _create_history(strategy_id, now - timedelta(days=38), operate="delete")
    # 修复前的删除历史没有回写成功状态，删除事实仍需按时间保留最新一条。
    kept_delete = _create_history(strategy_id, now - timedelta(days=35), operate="delete", status=False)
    failed_update = _create_history(strategy_id, now - timedelta(days=34), status=False)

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30, batch_size=2))

    assert deleted == 3
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {
        kept_snapshot.id,
        kept_delete.id,
    }
    assert not StrategyHistoryModel.objects.filter(id__in=[old_snapshot.id, old_delete.id, failed_update.id]).exists()


def test_recent_snapshot_allows_all_expired_snapshots_to_be_deleted(monkeypatch):
    """窗口内已有更新快照时，不再额外保留过期快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("recent-snapshot")
    expired_snapshot = _create_history(strategy.id, now - timedelta(days=40))
    recent_snapshot = _create_history(strategy.id, now - timedelta(days=10), operate="bulk_update")

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30))

    assert deleted == 1
    assert not StrategyHistoryModel.objects.filter(id=expired_snapshot.id).exists()
    assert StrategyHistoryModel.objects.filter(id=recent_snapshot.id).exists()


def test_failed_and_empty_histories_are_not_recoverable_snapshots(monkeypatch):
    """失败记录和空内容记录不能淘汰更早的有效快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("invalid-snapshots")
    kept_snapshot = _create_history(strategy.id, now - timedelta(days=45))
    empty_snapshot = _create_history(strategy.id, now - timedelta(days=40), content={})
    failed_snapshot = _create_history(strategy.id, now - timedelta(days=35), status=False)

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30))

    assert deleted == 2
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_snapshot.id}
    assert not StrategyHistoryModel.objects.filter(id__in=[empty_snapshot.id, failed_snapshot.id]).exists()


def test_history_at_cutoff_is_not_deleted(monkeypatch):
    """清理范围使用严格小于截止时间，边界记录应保留。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("cutoff-boundary")
    expired = _create_history(strategy.id, now - timedelta(days=30, seconds=1), status=False)
    at_cutoff = _create_history(strategy.id, now - timedelta(days=30), status=False)

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30))

    assert deleted == 1
    assert not StrategyHistoryModel.objects.filter(id=expired.id).exists()
    assert StrategyHistoryModel.objects.filter(id=at_cutoff.id).exists()


def test_cleanup_is_idempotent(monkeypatch):
    """相同保留周期重复执行不应继续删除保留记录。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("idempotent-cleanup")
    _create_history(strategy.id, now - timedelta(days=40))
    kept_snapshot = _create_history(strategy.id, now - timedelta(days=35), operate="bulk_update")

    params = CleanStrategyHistoryParams(days=30, batch_size=1)
    first_deleted = clean_strategy_history(params)
    second_deleted = clean_strategy_history(params)

    assert first_deleted == 1
    assert second_deleted == 0
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_snapshot.id}


def test_dry_run_returns_matched_count_without_deleting_histories(monkeypatch):
    """dry-run 应返回预计删除数量，同时保持数据库内容不变。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("dry-run")
    removable = _create_history(strategy.id, now - timedelta(days=40))
    kept_snapshot = _create_history(strategy.id, now - timedelta(days=35), operate="bulk_update")

    matched = clean_strategy_history(CleanStrategyHistoryParams(days=30, dry_run=True))

    assert matched == 1
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {
        removable.id,
        kept_snapshot.id,
    }


def test_keep_latest_snapshots_retains_multiple_successful_versions(monkeypatch):
    """keep_latest_snapshots>1 时应保留全局最近多条成功快照。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("multi-snapshots")

    oldest = _create_history(strategy.id, now - timedelta(days=50), operate="create")
    kept_older = _create_history(strategy.id, now - timedelta(days=45))
    kept_newer = _create_history(strategy.id, now - timedelta(days=40), operate="bulk_update")
    failed = _create_history(strategy.id, now - timedelta(days=35), status=False)

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30, keep_latest_snapshots=2))

    assert deleted == 2
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {kept_older.id, kept_newer.id}
    assert not StrategyHistoryModel.objects.filter(id__in=[oldest.id, failed.id]).exists()


def test_keep_latest_snapshots_counts_recent_window_versions(monkeypatch):
    """窗口内成功快照会计入 keep_latest_snapshots，从而减少窗外保留条数。"""
    now = timezone.make_aware(datetime(2026, 7, 21, 12, 0, 0))
    monkeypatch.setattr("bkmonitor.strategy.history.timezone.now", lambda: now)
    strategy = _create_strategy("window-counts")

    expired_old = _create_history(strategy.id, now - timedelta(days=50), operate="create")
    expired_kept = _create_history(strategy.id, now - timedelta(days=40))
    recent = _create_history(strategy.id, now - timedelta(days=10), operate="bulk_update")

    deleted = clean_strategy_history(CleanStrategyHistoryParams(days=30, keep_latest_snapshots=2))

    assert deleted == 1
    assert set(StrategyHistoryModel.objects.values_list("id", flat=True)) == {expired_kept.id, recent.id}
    assert not StrategyHistoryModel.objects.filter(id=expired_old.id).exists()


@pytest.mark.parametrize(
    ("days", "batch_size", "keep_latest_snapshots"),
    [
        (0, 1000, 1),
        (-1, 1000, 1),
        (30, 0, 1),
        (30, -1, 1),
        (30, 1000, 0),
        (30, 1000, -1),
    ],
)
def test_cleanup_rejects_non_positive_arguments(days, batch_size, keep_latest_snapshots):
    """保留天数、删除批次和快照保留条数必须为正整数。"""
    with pytest.raises(ValueError):
        CleanStrategyHistoryParams(days=days, batch_size=batch_size, keep_latest_snapshots=keep_latest_snapshots)
