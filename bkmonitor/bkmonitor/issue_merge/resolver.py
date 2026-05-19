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
from collections.abc import Iterable

from bkmonitor.models.issue import IssueMergeRelation

logger = logging.getLogger("fta_action.issue")


class MergeResolverContext:
    """per-request 显式容器（禁 ThreadLocal）。

    在 Resource.perform_request 入口创建并下传，请求生命周期内缓存合并关系，
    避免 4 个原子操作各自 N+1 查询 SQL。

    关系层加载失败 → degraded=True → Resolver 所有方法 noop（fail-open）。

    Note: assert_not_frozen 不依赖此 context（IssueDocument 状态机方法不持有 context），
    它直接走 SQL 单点查询。
    """

    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id
        self.degraded = False
        # member_id -> main_id（active 关系）
        self._member_to_main: dict[str, str] = {}
        # main_id -> list[member_summary]
        self._main_to_members: dict[str, list[dict]] = {}
        self._loaded = False

    def load(self) -> None:
        """一次 SQL 加载当前业务的全部 active 关系。幂等可重入。"""
        if self._loaded:
            return
        try:
            for r in IssueMergeRelation.objects.filter(
                bk_biz_id=self.bk_biz_id,
                status=IssueMergeRelation.STATUS_ACTIVE,
            ).values("main_issue_id", "member_issue_id", "merge_reasons", "create_user", "create_time"):
                main_id = r["main_issue_id"]
                member_id = r["member_issue_id"]
                self._member_to_main[member_id] = main_id
                self._main_to_members.setdefault(main_id, []).append(
                    {
                        "member_issue_id": member_id,
                        "merge_time": int(r["create_time"].timestamp()) if r["create_time"] else 0,
                        "merge_reasons": r["merge_reasons"],
                        "merge_operator": r["create_user"],
                    }
                )
        except Exception:
            logger.warning(
                "[issue-merge] context load failed, fallback to noop (bk_biz_id=%s)",
                self.bk_biz_id,
                exc_info=True,
            )
            self.degraded = True
        finally:
            self._loaded = True

    def main_of(self, issue_id: str) -> str | None:
        """member → main；非 member 或 degraded 返回 None。"""
        if self.degraded or not self._loaded:
            return None
        return self._member_to_main.get(issue_id)

    def members_of(self, main_issue_id: str) -> list[dict]:
        """main → active members 摘要列表；非 main 或 degraded 返回 []。"""
        if self.degraded or not self._loaded:
            return []
        return self._main_to_members.get(main_issue_id, [])

    def is_member(self, issue_id: str) -> bool:
        return self.main_of(issue_id) is not None


class IssueMergeResolver:
    """合并视图层：5 个原子操作。关系表为空时全 noop（fast-path）。"""

    @classmethod
    def expand_to_full_ids(cls, ids: Iterable[str], context: MergeResolverContext) -> list[str]:
        """``[A] → [A, m1, m2]``；未合并的 id 透传。

        用途：trend / anomaly_message / "按 Issue 筛选告警" 等"按 issue_id 反查 alert"路径。
        """
        ids = list(ids)
        if context.degraded:
            return ids
        result = list(ids)
        for iid in ids:
            for m in context.members_of(iid):
                result.append(m["member_issue_id"])
        return result

    @classmethod
    def resolve_display_id(cls, physical_id: str, context: MergeResolverContext) -> str:
        """member → main；未合并或 degraded 透传 X → X。

        用途：alert 详情"所属 Issue"跳转 / 通知模板 / 告警搜索结果"Issue"列。
        """
        if context.degraded:
            return physical_id
        return context.main_of(physical_id) or physical_id

    @classmethod
    def filter_out_members(cls, ids: Iterable[str], context: MergeResolverContext) -> list[str]:
        """剔除 active member；未合并或 degraded 时全部透传。

        用途：SearchIssue / TopN / Export 默认不展示被并入 Issue。
        """
        ids = list(ids)
        if context.degraded:
            return ids
        return [iid for iid in ids if not context.is_member(iid)]

    @classmethod
    def hydrate_aggregations(cls, issues: list[dict], context: MergeResolverContext) -> None:
        """主 Issue 行注入 ``merge_status`` 字段；原地修改 issues。

        - role='main'：拼装 active_members 摘要列表
        - role='member'：拼装 main_issue_id（供前端跳转主 Issue）
        - 普通 Issue：不动

        注：alert_count / impact_scope / first/last_alert_time 的实际数值聚合需要 caller
        额外查询 ES 拿 member 文档（bulk 一次），本方法只负责注入关系摘要。
        """
        if context.degraded:
            return
        for issue in issues:
            issue_id = issue.get("id")
            if not issue_id:
                continue
            members = context.members_of(issue_id)
            if members:
                issue["merge_status"] = {
                    "role": "main",
                    "main_issue_id": None,
                    "active_members": members,
                }
            else:
                main_id = context.main_of(issue_id)
                if main_id:
                    issue["merge_status"] = {
                        "role": "member",
                        "main_issue_id": main_id,
                        "active_members": None,
                    }

    @classmethod
    def assert_not_frozen(cls, issue_id: str) -> None:
        """守卫：member 抛 IssueFrozenError；非 member pass。

        不依赖 per-request context（IssueDocument 10 个状态机方法不持有 context）；
        直接走 SQL 单点查询，使用 (member_issue_id, status) 索引 → O(1)。

        Fail-open：DB 异常时不抛，让主路径继续（与 Resolver 整体降级语义一致）。
        """
        try:
            relation = (
                IssueMergeRelation.objects.filter(
                    member_issue_id=issue_id,
                    status=IssueMergeRelation.STATUS_ACTIVE,
                )
                .values("main_issue_id")
                .first()
            )
        except Exception:
            logger.warning(
                "[issue-merge] assert_not_frozen DB query failed, fail-open (issue_id=%s)",
                issue_id,
                exc_info=True,
            )
            return
        if not relation:
            return
        # lazy import 避免循环依赖（IssueFrozenError 在 bkmonitor.documents.issue 定义）
        from bkmonitor.documents.issue import IssueFrozenError

        raise IssueFrozenError(
            issue_id=issue_id,
            conflicting_main_issue_id=relation["main_issue_id"],
        )
