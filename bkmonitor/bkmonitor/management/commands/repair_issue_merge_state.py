"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Management command：修复 Issue 合并/拆分状态不一致（运维兜底）。

使用场景：
- bkm-cli ``inspect-issue list_conflicts`` 发现状态不一致后，运维 SSH 上服务器执行此命令修复。
- 三种模式：
  * ``resolve_conflicts``：把重复 active 的 member 关系（race window 引起）保留最早一条，其余改 split
  * ``follow_status_resync``：关系 active 但 member ES status ≠ 主当前 status 时调
    ``bulk_follow_status`` 同步（cascade follow 失败兜底）
  * ``reset_pending_split``（**deprecated**）：原 cascade split 失败兜底；主状态变更不再
    触发拆分后该模式仅用于处理历史遗留的 split 关系 ES 未重置情况，保留一个发布周期后移除

示例：
    python manage.py repair_issue_merge_state --bk-biz-id 2 --mode resolve_conflicts --dry-run
    python manage.py repair_issue_merge_state --bk-biz-id 2 --mode follow_status_resync --limit 100
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from bkmonitor.documents.issue import IssueDocument
from bkmonitor.models.issue import IssueMergeRelation
from constants.issue import IssueStatus

MODE_RESOLVE_CONFLICTS = "resolve_conflicts"
MODE_FOLLOW_STATUS_RESYNC = "follow_status_resync"
MODE_RESET_PENDING_SPLIT = "reset_pending_split"  # deprecated，保留兼容旧 SOP 文档
DEFAULT_LIMIT = 500
DEFAULT_SINCE_DAYS = 7

# cascade follow 的 repair 路径专用 kind，写入活动日志 content.kind 供审计区分
REPAIR_FOLLOW_STATUS_KIND = "repair_follow_status_resync"


class Command(BaseCommand):
    help = "修复 Issue 合并/拆分状态不一致（运维兜底；配合 bkm-cli inspect-issue list_conflicts）"

    def add_arguments(self, parser):
        parser.add_argument("--bk-biz-id", type=int, required=True, help="业务 ID")
        parser.add_argument(
            "--mode",
            choices=[MODE_RESOLVE_CONFLICTS, MODE_FOLLOW_STATUS_RESYNC, MODE_RESET_PENDING_SPLIT],
            required=True,
            help=(
                "resolve_conflicts: 解决重复 active 关系；"
                "follow_status_resync: 同步 member ES status 到主当前 status；"
                "reset_pending_split: 补做 ES 重置（deprecated，历史 split 关系遗留兜底）"
            ),
        )
        parser.add_argument("--dry-run", action="store_true", help="仅打印将要执行的操作，不真正修改数据")
        parser.add_argument(
            "--limit", type=int, default=DEFAULT_LIMIT, help=f"单次处理最大条数（默认 {DEFAULT_LIMIT}）"
        )
        parser.add_argument(
            "--since-days",
            type=int,
            default=DEFAULT_SINCE_DAYS,
            help=f"回溯时间窗口（默认 {DEFAULT_SINCE_DAYS} 天）",
        )

    def handle(self, *args, **options):
        bk_biz_id = options["bk_biz_id"]
        mode = options["mode"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        since_days = options["since_days"]
        since_dt = datetime.now() - timedelta(days=since_days)

        self.stdout.write(
            f"[repair-issue-merge] mode={mode} bk_biz_id={bk_biz_id} dry_run={dry_run} "
            f"limit={limit} since_days={since_days}"
        )

        if mode == MODE_RESOLVE_CONFLICTS:
            handled, failed = self._resolve_conflicts(bk_biz_id, since_dt, limit, dry_run)
        elif mode == MODE_FOLLOW_STATUS_RESYNC:
            handled, failed = self._follow_status_resync(bk_biz_id, since_dt, limit, dry_run)
        elif mode == MODE_RESET_PENDING_SPLIT:
            self.stdout.write(
                self.style.WARNING(
                    "[deprecated] reset_pending_split 即将移除（主状态变更已改为 follow 不再拆分）。"
                    "如果你在修复历史 split 关系遗留的 ES 状态不一致仍可使用；"
                    "新场景请改用 follow_status_resync"
                )
            )
            handled, failed = self._reset_pending_split(bk_biz_id, since_dt, limit, dry_run)
        else:
            raise CommandError(f"未支持的 mode: {mode}")

        verb = "WILL handle" if dry_run else "handled"
        self.stdout.write(self.style.SUCCESS(f"[repair-issue-merge] {verb}={handled} failed={failed}"))

    # ---------- modes ----------

    def _resolve_conflicts(self, bk_biz_id: int, since_dt: datetime, limit: int, dry_run: bool) -> tuple[int, int]:
        """解决重复 active 关系：保留每个 member 最早的 active 行，其余改 status='split'。"""
        duplicate_rows = (
            IssueMergeRelation.objects.filter(
                bk_biz_id=bk_biz_id,
                status=IssueMergeRelation.STATUS_ACTIVE,
                create_time__gte=since_dt,
            )
            .values("member_issue_id")
            .annotate(active_count=Count("id"))
            .filter(active_count__gt=1)[:limit]
        )

        handled, failed = 0, 0
        for r in duplicate_rows:
            member_id = r["member_issue_id"]
            rows = list(
                IssueMergeRelation.objects.filter(
                    bk_biz_id=bk_biz_id,
                    member_issue_id=member_id,
                    status=IssueMergeRelation.STATUS_ACTIVE,
                ).order_by("create_time")
            )
            if len(rows) <= 1:
                continue
            keep = rows[0]
            to_split = rows[1:]
            self.stdout.write(
                f"  member={member_id} active_count={len(rows)} keep={keep.pk}(main={keep.main_issue_id}) "
                f"split_ids={[r.pk for r in to_split]}"
            )
            if dry_run:
                handled += len(to_split)
                continue
            try:
                IssueMergeRelation.objects.filter(pk__in=[r.pk for r in to_split]).update(
                    status=IssueMergeRelation.STATUS_SPLIT,
                    split_kind=IssueMergeRelation.SPLIT_KIND_MANUAL,
                    split_reasons=["repair_resolve_conflicts"],
                    update_user="repair_command",
                )
                handled += len(to_split)
            except Exception as e:
                self.stderr.write(f"  resolve_conflicts member={member_id} failed: {e}")
                failed += 1
        return handled, failed

    def _follow_status_resync(self, bk_biz_id: int, since_dt: datetime, limit: int, dry_run: bool) -> tuple[int, int]:
        """同步 member ES status 到主当前 status。

        cascade follow 在 SQL / ES / cache 任一环节 fail-open 后，可能出现关系 active 但
        member ES status 与主当前 status 不一致的情况。本 mode 按主分组扫描，每组调一次
        ``bulk_follow_status``，把不一致 member 拉齐到主当前 status。

        与 ``reset_pending_split`` 的差异：
        - 后者前提是关系已变 split（主 resolve/archive 触发拆分的旧行为遗留）
        - 本 mode 前提是关系**仍 active**——cascade follow 是预期行为，ES 不同步才需修复
        """
        active_rows = list(
            IssueMergeRelation.objects.filter(
                bk_biz_id=bk_biz_id,
                status=IssueMergeRelation.STATUS_ACTIVE,
                update_time__gte=since_dt,
            ).values("main_issue_id", "member_issue_id")[:limit]
        )
        if not active_rows:
            return 0, 0

        # 按主分组（main → [member_ids]）
        main_to_members: dict[str, list[str]] = {}
        for r in active_rows:
            main_to_members.setdefault(r["main_issue_id"], []).append(r["member_issue_id"])

        # 一次 ES 拉所有 main + member 的 status
        all_ids = set(main_to_members.keys())
        for ms in main_to_members.values():
            all_ids.update(ms)
        try:
            hits = (
                IssueDocument.search(all_indices=True)
                .filter("terms", _id=list(all_ids))
                .source(["status"])
                .params(size=len(all_ids))
                .execute()
                .hits
            )
        except Exception as e:
            self.stderr.write(f"ES query failed: {e}")
            return 0, len(active_rows)

        status_map = {hit.meta.id: getattr(hit, "status", None) for hit in hits}

        # 按 (main, target_status) 分组找出需要同步的 member
        groups: dict[tuple[str, str], list[str]] = {}
        for main_id, member_ids in main_to_members.items():
            main_status = status_map.get(main_id)
            if main_status is None:
                # 主已删除或 ES 缺失：跳过；运维另需评估是否清孤儿关系
                continue
            for mid in member_ids:
                m_status = status_map.get(mid)
                if m_status == main_status:
                    continue  # 已一致
                groups.setdefault((main_id, main_status), []).append(mid)

        handled, failed = 0, 0
        for (main_id, target_status), m_ids in groups.items():
            self.stdout.write(f"  resync main={main_id} target={target_status} members={m_ids}")
            if dry_run:
                handled += len(m_ids)
                continue
            try:
                IssueDocument.bulk_follow_status(
                    m_ids,
                    target_status=target_status,
                    operator="repair_command",
                    kind=REPAIR_FOLLOW_STATUS_KIND,
                    main_issue_id=main_id,
                )
                handled += len(m_ids)
            except Exception as e:
                self.stderr.write(f"  bulk_follow_status main={main_id} failed: {e}")
                failed += len(m_ids)
            time.sleep(0.05)  # 避免高 QPS
        return handled, failed

    def _reset_pending_split(self, bk_biz_id: int, since_dt: datetime, limit: int, dry_run: bool) -> tuple[int, int]:
        """补做 ES bulk_reset_for_split：SQL split 但 ES status 未匹配 PENDING_REVIEW 的 member。"""
        split_rows = list(
            IssueMergeRelation.objects.filter(
                bk_biz_id=bk_biz_id,
                status=IssueMergeRelation.STATUS_SPLIT,
                update_time__gte=since_dt,
            ).order_by("-update_time")[:limit]
        )
        if not split_rows:
            return 0, 0

        member_ids = [r.member_issue_id for r in split_rows]
        try:
            hits = (
                IssueDocument.search(all_indices=True)
                .filter("terms", _id=member_ids)
                .source(["status", "assignee"])
                .params(size=len(member_ids))
                .execute()
                .hits
            )
        except Exception as e:
            self.stderr.write(f"ES query failed: {e}")
            return 0, len(split_rows)

        status_map = {
            hit.meta.id: (getattr(hit, "status", None), list(getattr(hit, "assignee", []) or [])) for hit in hits
        }

        # 按 main_issue_id + kind 分组，调 bulk_reset_for_split 批处理
        groups: dict[tuple[str, str], list[str]] = {}
        for r in split_rows:
            es_status, es_assignee = status_map.get(r.member_issue_id, (None, []))
            if es_status is None:
                continue
            if es_status == IssueStatus.PENDING_REVIEW and not es_assignee:
                # 已一致，跳过
                continue
            key = (r.main_issue_id, r.split_kind or IssueMergeRelation.SPLIT_KIND_MANUAL)
            groups.setdefault(key, []).append(r.member_issue_id)

        handled, failed = 0, 0
        for (main_id, kind), m_ids in groups.items():
            self.stdout.write(f"  reset main={main_id} kind={kind} members={m_ids}")
            if dry_run:
                handled += len(m_ids)
                continue
            try:
                IssueDocument.bulk_reset_for_split(m_ids, operator="repair_command", kind=kind, main_issue_id=main_id)
                handled += len(m_ids)
            except Exception as e:
                self.stderr.write(f"  bulk_reset_for_split main={main_id} failed: {e}")
                failed += len(m_ids)
            # 避免高 QPS：每批之间小间隔
            time.sleep(0.05)
        return handled, failed
