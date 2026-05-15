"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

from django.core.management.base import BaseCommand

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import IssueDocument
from constants.issue import IssueStatus

logger = logging.getLogger("bkmonitor.commands.backfill_issue_fingerprint")


class Command(BaseCommand):
    """[应急/手动] 存量活跃 Issue 回填 fingerprint / dimension_values。

    ⚠️ **新方案下不再作为主流程使用**——主流程由 fta_web post_migrate hook 自动执行
    `migrate_legacy_active_issues()` 完成切割（直接 RESOLVE 旧 Issue，不回填）。

    本命令仅保留为应急入口，使用场景：
      - 部署期 post_migrate hook 失败且不便重跑 migrate 时
      - 灰度试点期对某个 strategy 单独验证回填行为
      - 历史 RESOLVED 旧 Issue 想要补全 fingerprint 字段（极少需要）

    与 migrate_legacy_active_issues 的语义区别：
      - migrate（主流程）：直接 RESOLVE 旧 Issue，alert 关联保留，旧问题进 RESOLVED 列表
      - backfill（应急）：保留旧 Issue 活跃状态，回填 fingerprint，旧 Issue 自此专属于回填的 fingerprint
      - 两者**不可混用**！主流程跑过后再用 backfill 会破坏一致性

    回填策略：
      - 仅扫描 status in ACTIVE_STATUSES 且 fingerprint 不存在的 Issue
      - 每个 Issue 取最新 1 条关联 alert 的 ``event.extra_info.origin_alarm.data.dimensions``
        （adapter 收编前的原始维度，与 issue_config.aggregate_dimensions 同层级命名）
      - 用 issue.aggregate_config.aggregate_dimensions + 上述 dimensions 算指纹
      - 缺维度 / 第三方告警无 origin_alarm 的告警跳过该 Issue（保留 fingerprint=null）

    可选参数：
      --dry-run            仅打印将回填的 Issue 列表，不写入 ES
      --strategy-id N      仅处理指定策略，便于灰度
      --batch-size N       每批写入条数（默认 100）
    """

    help = "[应急/手动] 存量活跃 Issue 回填 fingerprint。新方案下默认走 post_migrate 自动 RESOLVE，本命令仅作应急用途"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅打印不写入")
        parser.add_argument("--strategy-id", type=int, default=0, help="仅处理指定策略 ID（0 = 全量）")
        parser.add_argument("--batch-size", type=int, default=100, help="每批写入条数")

    def handle(self, *args, **options):
        from alarm_backends.service.fta_action.issue_processor import gen_issue_fingerprint

        dry_run = options["dry_run"]
        strategy_id_filter = options["strategy_id"]
        batch_size = options["batch_size"]

        scanned = 0
        # 区分 dry-run 计划数（planned）与实际写入数（written），避免 dry-run 输出与真跑混淆
        planned = 0
        written = 0
        skipped_missing_dim = 0
        skipped_no_alert = 0
        failed = 0
        pending: list[IssueDocument] = []

        search = (
            IssueDocument.search(all_indices=True)
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .exclude("exists", field="fingerprint")
            .params(size=500)
        )
        if strategy_id_filter:
            search = search.filter("term", strategy_id=str(strategy_id_filter))

        for hit in search.scan():
            scanned += 1
            issue = IssueDocument(**hit.to_dict())

            agg_config = issue.aggregate_config
            if hasattr(agg_config, "to_dict"):
                agg_config = agg_config.to_dict()
            # 与 processor / issue_tasks 一致：None 与 [] 等价处理，避免 for key in None 抛 TypeError
            aggregate_dimensions = (agg_config or {}).get("aggregate_dimensions") or []

            try:
                strategy_id_int = int(issue.strategy_id) if issue.strategy_id else 0
            except (TypeError, ValueError):
                strategy_id_int = 0

            if not strategy_id_int:
                self.stdout.write(self.style.WARNING(f"skip: issue({issue.id}) no strategy_id"))
                failed += 1
                continue

            # 取该 Issue 关联的最新 1 条 alert 提取原始维度（adapter 收编前）
            data_dimensions = self._fetch_alert_origin_data_dimensions(issue.id)
            if data_dimensions is None:
                # 没有任何关联 alert：aggregate_dimensions=[] 时仍可回填（指纹仅含 strategy_id）
                if aggregate_dimensions:
                    skipped_no_alert += 1
                    continue
                data_dimensions = {}

            fingerprint = gen_issue_fingerprint(strategy_id_int, aggregate_dimensions, data_dimensions)
            if fingerprint is None:
                skipped_missing_dim += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"skip: issue({issue.id}) strategy({strategy_id_int}) "
                        f"missing dim, required={aggregate_dimensions} got={list(data_dimensions.keys())}"
                    )
                )
                continue

            # 与 processor 完全一致：按 sorted(aggregate_dimensions) 构建 + str(...).strip() 归一化，
            # 保证回填的 fingerprint 与展示快照字符串严格对应，避免精确过滤/TopN/名称展示分裂
            dimension_values = {key: str(data_dimensions[key]).strip() for key in sorted(aggregate_dimensions)}
            update_doc = IssueDocument(
                id=issue.id,
                fingerprint=fingerprint,
                dimension_values=dimension_values,
                update_time=int(time.time()),
            )

            if dry_run:
                self.stdout.write(
                    f"[dry-run] issue({issue.id}) strategy({strategy_id_int}) → fingerprint={fingerprint}"
                )
                planned += 1
                continue

            pending.append(update_doc)
            planned += 1
            if len(pending) >= batch_size:
                batch_failed = self._flush(pending)
                failed += batch_failed
                written += len(pending) - batch_failed
                pending.clear()

        if pending and not dry_run:
            batch_failed = self._flush(pending)
            failed += batch_failed
            written += len(pending) - batch_failed
            pending.clear()

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[dry-run] done: scanned={scanned} planned={planned} "
                    f"skipped_missing_dim={skipped_missing_dim} skipped_no_alert={skipped_no_alert}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"done: scanned={scanned} written={written} failed={failed} "
                    f"skipped_missing_dim={skipped_missing_dim} skipped_no_alert={skipped_no_alert}"
                )
            )

    @staticmethod
    def _fetch_alert_origin_data_dimensions(issue_id: str) -> dict | None:
        """取该 Issue 关联的最新 1 条 alert 的 ``event.extra_info.origin_alarm.data.dimensions``。

        无关联返回 None，与下游 aggregate_dimensions=[] 退化路径区分；
        有关联但 origin_alarm 结构缺失（第三方告警）返回空 dict，
        让 gen_issue_fingerprint 自然返回 None 进入 skipped_missing_dim 分支。
        """
        from alarm_backends.service.fta_action.tasks.issue_tasks import _extract_origin_data_dimensions

        search = (
            AlertDocument.search(all_indices=True).filter("term", issue_id=issue_id).sort("-begin_time").params(size=1)
        )
        hits = search.execute().hits
        if not hits:
            return None
        return _extract_origin_data_dimensions(hits[0])

    def _flush(self, pending: list[IssueDocument]) -> int:
        """批量 UPSERT；失败计数返回。"""
        try:
            IssueDocument.bulk_create(pending, action=BulkActionType.UPSERT)
            return 0
        except Exception as e:
            logger.exception("[backfill_issue_fingerprint] flush failed: %s", e)
            self.stdout.write(self.style.ERROR(f"flush failed: {e}"))
            return len(pending)
