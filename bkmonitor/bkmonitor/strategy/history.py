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

from collections.abc import Iterator
from datetime import datetime
from datetime import timedelta

from django.db.models import OuterRef
from django.db.models import QuerySet
from django.db.models import Subquery
from django.utils import timezone

from bkmonitor.models import StrategyHistoryModel
from bkmonitor.models import StrategyModel

SNAPSHOT_OPERATIONS = ("create", "update", "bulk_update")
DELETE_OPERATIONS = ("delete", "bulk_delete")
LEGACY_BULK_OPERATIONS = ("update", "delete")
STRATEGY_ID_CHUNK_SIZE = 500
# 管理命令允许的最小保留天数；业务层 CleanStrategyHistoryParams 仍只要求正整数，便于单测构造窗口。
MIN_CLEAN_STRATEGY_HISTORY_DAYS = 30


class CleanStrategyHistoryParams:
    """策略历史清理参数。

    校验逻辑集中在此类中：days、batch_size、keep_latest_snapshots 均须为正整数。
    """

    def __init__(
        self,
        days: int,
        batch_size: int = 1000,
        keep_latest_snapshots: int = 1,
        dry_run: bool = False,
    ):
        self.days = self._require_positive_int("days", days)
        self.batch_size = self._require_positive_int("batch_size", batch_size)
        self.keep_latest_snapshots = self._require_positive_int("keep_latest_snapshots", keep_latest_snapshots)
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        self.dry_run = dry_run

    @staticmethod
    def _require_positive_int(name: str, value: object) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value


def _collect_latest_history_ids(queryset: QuerySet, limit: int = 1) -> set[int]:
    """获取查询集中每个策略按时间排序后的最近若干条历史 ID。

    Args:
        queryset: 已包含业务过滤条件的策略历史查询集。
        limit: 每个策略保留的最近记录条数。

    Returns:
        每个策略最近 limit 条历史记录的 ID 集合。
    """
    keep_history_ids: set[int] = set()
    remaining = queryset.order_by()

    for _ in range(limit):
        latest_id = (
            remaining.filter(strategy_id=OuterRef("strategy_id")).order_by("-create_time", "-id").values("id")[:1]
        )
        batch_ids = set(remaining.filter(id=Subquery(latest_id)).values_list("id", flat=True))
        if not batch_ids:
            break
        keep_history_ids.update(batch_ids)
        remaining = remaining.exclude(id__in=batch_ids)

    return keep_history_ids


def _collect_keep_history_ids(strategy_ids: list[int], keep_latest_snapshots: int = 1) -> set[int]:
    """计算一批策略必须保留的历史记录 ID。

    Args:
        strategy_ids: 本批需要处理的策略 ID。
        keep_latest_snapshots: 每个策略保留的最近成功快照条数。

    Returns:
        最近成功快照，以及已删除策略的最新删除记录 ID。
    """
    if not strategy_ids:
        return set()

    existing_strategy_ids = set(StrategyModel.objects.filter(id__in=strategy_ids).values_list("id", flat=True))
    deleted_strategy_ids = set(strategy_ids) - existing_strategy_ids

    recoverable_snapshots = (
        StrategyHistoryModel.objects.filter(
            strategy_id__in=strategy_ids,
            operate__in=SNAPSHOT_OPERATIONS,
            status=True,
        )
        .exclude(content={})
        .exclude(content__isnull=True)
    )
    keep_history_ids = _collect_latest_history_ids(recoverable_snapshots, limit=keep_latest_snapshots)

    if deleted_strategy_ids:
        delete_histories = StrategyHistoryModel.objects.filter(
            strategy_id__in=deleted_strategy_ids,
            operate__in=DELETE_OPERATIONS,
        )
        keep_history_ids.update(_collect_latest_history_ids(delete_histories))

    return keep_history_ids


def _iter_expired_strategy_id_chunks(
    before: datetime,
    chunk_size: int = STRATEGY_ID_CHUNK_SIZE,
) -> Iterator[list[int]]:
    """按 strategy_id 分批产出存在过期历史的策略。

    Args:
        before: 清理截止时间。
        chunk_size: 每批策略数量。

    Yields:
        按 strategy_id 升序排列的策略 ID 列表。
    """
    last_strategy_id = None
    while True:
        queryset = StrategyHistoryModel.objects.filter(create_time__lt=before)
        if last_strategy_id is not None:
            queryset = queryset.filter(strategy_id__gt=last_strategy_id)

        strategy_ids = list(
            queryset.order_by("strategy_id").values_list("strategy_id", flat=True).distinct()[:chunk_size]
        )
        if not strategy_ids:
            return

        yield strategy_ids
        last_strategy_id = strategy_ids[-1]


def _delete_queryset_in_batches(queryset: QuerySet, batch_size: int) -> int:
    """按主键分批删除查询集中的记录。

    Args:
        queryset: 待删除的策略历史查询集。
        batch_size: 单批删除数量。

    Returns:
        实际删除的记录数量。
    """
    model = queryset.model
    last_pk = None
    deleted = 0

    while True:
        batch = queryset.order_by("pk")
        if last_pk is not None:
            batch = batch.filter(pk__gt=last_pk)

        history_ids = list(batch.values_list("pk", flat=True)[:batch_size])
        if not history_ids:
            return deleted

        deleted_count, _ = model._default_manager.filter(pk__in=history_ids).delete()
        deleted += deleted_count
        last_pk = history_ids[-1]


def repair_legacy_bulk_strategy_history_status(batch_size: int = 1000, dry_run: bool = True) -> int:
    """修复存量批量更新和批量删除历史的成功状态。

    旧版批量操作分别使用 ``update`` 和 ``delete`` 类型，且成功后未将
    ``status`` 从默认的 ``False`` 回写为 ``True``。这些记录以空 ``message``
    作为操作成功的判定标准。

    Args:
        batch_size: 单批更新数量。
        dry_run: 为 True 时仅统计匹配记录，不修改数据。

    Returns:
        dry-run 时返回匹配数，实际执行时返回成功更新数。
    """
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean")

    candidates = StrategyHistoryModel.objects.filter(
        operate__in=LEGACY_BULK_OPERATIONS,
        status=False,
        message="",
    )
    if dry_run:
        return candidates.count()

    max_pk = candidates.order_by("-pk").values_list("pk", flat=True).first()
    if max_pk is None:
        return 0

    repaired = 0
    last_pk = None
    while True:
        batch = candidates.filter(pk__lte=max_pk).order_by("pk")
        if last_pk is not None:
            batch = batch.filter(pk__gt=last_pk)

        history_ids = list(batch.values_list("pk", flat=True)[:batch_size])
        if not history_ids:
            return repaired

        repaired += candidates.filter(pk__in=history_ids).update(status=True)
        last_pk = history_ids[-1]


def clean_strategy_history(params: CleanStrategyHistoryParams) -> int:
    """清理指定天数以前的冗余策略历史。

    保留最近 ``params.days`` 天的全部历史；更早的记录中，每个策略额外保留全局最近
    ``params.keep_latest_snapshots`` 条成功快照。已删除策略额外保留全局最新删除记录。

    Args:
        params: 清理参数，校验在 ``CleanStrategyHistoryParams`` 中完成。

    Returns:
        实际删除的历史记录数量。

    Raises:
        ValueError: 由 ``CleanStrategyHistoryParams`` 在构造时抛出。
    """
    before = timezone.now() - timedelta(days=params.days)
    deleted = 0

    for strategy_ids in _iter_expired_strategy_id_chunks(before):
        keep_history_ids = _collect_keep_history_ids(
            strategy_ids,
            keep_latest_snapshots=params.keep_latest_snapshots,
        )
        queryset = StrategyHistoryModel.objects.filter(
            strategy_id__in=strategy_ids,
            create_time__lt=before,
        )
        if keep_history_ids:
            queryset = queryset.exclude(id__in=keep_history_ids)
        if params.dry_run:
            deleted += queryset.count()
        else:
            deleted += _delete_queryset_in_batches(queryset, params.batch_size)

    return deleted
