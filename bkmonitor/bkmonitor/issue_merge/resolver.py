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
from constants.issue import IssueStatus

logger = logging.getLogger("fta_action.issue")


class MergeResolverContext:
    """per-request 显式容器（禁 ThreadLocal）。

    在 Resource.perform_request 入口创建并下传，请求生命周期内缓存合并关系，
    避免 4 个原子操作各自 N+1 查询 SQL。

    关系层加载失败 → degraded=True → Resolver 所有方法 noop（fail-open）。

    Note: assert_not_frozen 不依赖此 context（IssueDocument 状态机方法不持有 context），
    它直接走 SQL 单点查询。
    """

    def __init__(self, bk_biz_id: int | list[int]):
        # 接受单个或多个业务：列表查询可能跨业务，按"页内命中的 distinct bk_biz_id"批量加载。
        # 关系 map 按全局唯一 issue_id 存储，多业务合并到同一 context 无键冲突。
        # 参数名保留 bk_biz_id（单业务调用方 / 测试用关键字传参兼容）。
        self.bk_biz_ids: list[int] = [bk_biz_id] if isinstance(bk_biz_id, int) else list(bk_biz_id)
        self.degraded = False
        # member_id -> main_id（active 关系）
        self._member_to_main: dict[str, str] = {}
        # main_id -> list[member_summary]
        self._main_to_members: dict[str, list[dict]] = {}
        self._loaded = False

    def load(self) -> None:
        """一次 SQL 加载业务集合的全部 active 关系。幂等可重入。"""
        if self._loaded:
            return
        try:
            for r in IssueMergeRelation.objects.filter(
                bk_biz_id__in=self.bk_biz_ids,
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
                "[issue-merge] context load failed, fallback to noop (bk_biz_ids=%s)",
                self.bk_biz_ids,
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
        """主 Issue 行注入 ``merge_status`` 字段 + 聚合数据字段；原地修改 issues。

        Step 1（注入关系摘要）：
        - role='main'：拼装 active_members 摘要列表 + 初始化状态冲突字段（status_conflict / active_member_count）
        - role='member'：拼装 main_issue_id（供前端跳转主 Issue）
        - 普通 Issue：不动

        Step 2（聚合数据字段 + 状态冲突）—— 仅对 role='main' 的 Issue：
        - ``alert_count`` += Σ members.alert_count
        - ``first_alert_time`` = min(self, Σ members.first_alert_time)
        - ``last_alert_time``  = max(self, Σ members.last_alert_time)
        - ``impact_scope`` = self ∪ Σ members.impact_scope（按 dimension 维度 union，instance_list 按 dict 内容去重）
        - ``merge_status.active_member_count`` = Issue 状态仍活跃（pending_review/unresolved）的 member 数；
          注意区别于 ``active_members``（关系层 active 的全部成员列表，与成员 Issue 状态无关）。
        - ``merge_status.status_conflict`` = 主 Issue 处于终态（已解决/已归档）但仍持有活跃 member。
          合并/拆分与状态解耦后，活跃 member 可被并入终态主（不级联其状态），此标记让前端提示
          「该历史 Issue 下仍有关联活跃问题」，避免用户误判异常已结束。

        聚合后的 first/last_alert_time 会被 ``IssueQueryHandler.add_alert_trend`` 用于
        计算告警查询时间窗，保证 member 在主 Issue 自身时间窗外的告警也能进入聚合统计。

        状态冲突字段依赖 Step 2 的 member ES 查询；该查询 fail-open，失败时保留 Step 1 的
        默认值（status_conflict=False / active_member_count=0），即"无法判定则不误报"。
        """
        if context.degraded:
            return

        # Step 1: 注入 merge_status
        main_issue_ids: list[str] = []
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
                    # 状态冲突提示：默认无冲突，Step 2 拿到 member ES 状态后回填真实值（fail-open 时保留默认）
                    "status_conflict": False,
                    "active_member_count": 0,
                }
                main_issue_ids.append(issue_id)
            else:
                main_id = context.main_of(issue_id)
                if main_id:
                    issue["merge_status"] = {
                        "role": "member",
                        "main_issue_id": main_id,
                        "active_members": None,
                    }

        # Step 2: 聚合数据字段（无主 Issue 命中时直接跳过，避免无谓 ES 查询）
        if not main_issue_ids:
            return

        all_member_ids: list[str] = []
        for mid in main_issue_ids:
            for m in context.members_of(mid):
                all_member_ids.append(m["member_issue_id"])
        if not all_member_ids:
            return

        # lazy import 避免循环依赖
        from bkmonitor.documents.issue import IssueDocument

        try:
            hits = (
                IssueDocument.search(all_indices=True)
                .filter("terms", _id=all_member_ids)
                .source(["status", "alert_count", "impact_scope", "first_alert_time", "last_alert_time"])
                .params(size=len(all_member_ids))
                .execute()
                .hits
            )
        except Exception:
            logger.warning(
                "[issue-merge] hydrate aggregate ES fetch failed (fail-open, member_ids=%s)",
                all_member_ids,
                exc_info=True,
            )
            return

        member_doc_map = {hit.meta.id: hit for hit in hits}

        for issue in issues:
            main_id = issue.get("id")
            if not main_id:
                continue
            members = context.members_of(main_id)
            if not members:
                continue
            active_member_count = 0
            for m in members:
                member_doc = member_doc_map.get(m["member_issue_id"])
                if member_doc is None:
                    continue
                # 统计 Issue 状态仍活跃的 member：终态主 Issue 下若存在活跃 member，说明合并/解耦后
                # 该历史 Issue 仍挂着未结束的关联问题（status_conflict）。注意按 member 的 ES 状态判定，
                # 而非关系层——主 resolve 级联同步成 resolved 的 member 不计入。
                if getattr(member_doc, "status", None) in IssueStatus.ACTIVE_STATUSES:
                    active_member_count += 1
                # alert_count 不在此处累加：add_alert_trend 走 AlertDocument 按 display_id 折叠
                # 后会直接覆盖式写回 issue["alert_count"]（resources.py 内 fill_result.alert_count_map），
                # 此处累加属于死代码。仅保留 first/last_alert_time + impact_scope 聚合，
                # 因为这两个字段 add_alert_trend 不再覆盖，由此处提供最终值。
                # first_alert_time min（取最早；caller 用此作为告警查询窗口下界）
                mft = getattr(member_doc, "first_alert_time", None)
                if mft:
                    cur = issue.get("first_alert_time")
                    issue["first_alert_time"] = min(int(cur), int(mft)) if cur else int(mft)
                # last_alert_time max（取最近；caller 用此作为告警查询窗口上界）
                mlt = getattr(member_doc, "last_alert_time", None)
                if mlt:
                    cur = issue.get("last_alert_time")
                    issue["last_alert_time"] = max(int(cur), int(mlt)) if cur else int(mlt)
                # impact_scope union（caller 需在 hydrate 后对主 Issue 再调 enrich_impact_scope
                # 一次，补 member instance 的 alert_query_fields，保持主 / member instance
                # 字段集一致）
                m_scope = getattr(member_doc, "impact_scope", None)
                if hasattr(m_scope, "to_dict"):
                    m_scope = m_scope.to_dict()
                if not isinstance(m_scope, dict):
                    continue
                cls._union_impact_scope(issue, m_scope)

            # 回填状态冲突提示：主 Issue 处于终态（已解决/已归档）但仍持有活跃 member 时置 True。
            # merge_status 必为 Step 1 注入的 main 行（members 非空 → 此处可达），保险起见判空。
            merge_status = issue.get("merge_status")
            if merge_status is not None:
                merge_status["active_member_count"] = active_member_count
                merge_status["status_conflict"] = (
                    issue.get("status") in (IssueStatus.RESOLVED, IssueStatus.ARCHIVED) and active_member_count > 0
                )

    # 计算 instance 去重键时忽略的字段集——这些字段是 enrich 阶段动态注入，主 / member
    # 在 hydrate 调用时 enrich 状态不同（主已 enrich vs member 未 enrich），不能进入去重键
    # 否则同一 instance 会被判为不同导致重复保留。
    _IMPACT_INSTANCE_VOLATILE_FIELDS = frozenset({"alert_query_fields"})

    @classmethod
    def _union_impact_scope(cls, main_issue: dict, member_scope: dict) -> None:
        """把 member 的 impact_scope 并入主 Issue。原地修改 ``main_issue['impact_scope']``。

        union 规则：
        - 维度 key 取并集（跨策略合并时主和 member 可能维度异构，逐维度独立处理）
        - 每个维度的 instance_list 按"核心字段"去重（忽略 enrich 注入的 volatile 字段），
          保证主（已 enrich，含 alert_query_fields）与 member（未 enrich）的同一 instance
          能正确判定相等而合并
        - 维护 ``count = len(instance_list)``，与 instance_list 长度同步

        ⚠ 调用方需在 hydrate_aggregations 完成后对**主 Issue**整体调一次
        ``IssueQueryHandler.enrich_impact_scope``，补 member instance 的 alert_query_fields。
        """
        issue_scope = main_issue.get("impact_scope") or {}
        if hasattr(issue_scope, "to_dict"):
            issue_scope = issue_scope.to_dict()
        if not isinstance(issue_scope, dict):
            issue_scope = {}

        for dim, dim_data in member_scope.items():
            if not isinstance(dim_data, dict):
                continue
            member_inst_list = dim_data.get("instance_list") or []
            if dim not in issue_scope:
                # 主 Issue 没该维度，直接透传 member 维度全部字段（含 link_tpl 等前端跳转模板），
                # 仅覆盖 instance_list 副本与 count 长度，避免后续聚合时主与 member 共享同一引用。
                issue_scope[dim] = {**dim_data, "instance_list": list(member_inst_list), "count": len(member_inst_list)}
                continue
            existing = issue_scope[dim].get("instance_list") or []
            seen = set()
            merged: list = []
            for inst in [*existing, *member_inst_list]:
                if isinstance(inst, dict):
                    key = tuple(
                        sorted((k, str(v)) for k, v in inst.items() if k not in cls._IMPACT_INSTANCE_VOLATILE_FIELDS)
                    )
                else:
                    key = ("__primitive__", str(inst))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(inst)
            issue_scope[dim]["instance_list"] = merged
            issue_scope[dim]["count"] = len(merged)
        main_issue["impact_scope"] = issue_scope

    @classmethod
    def get_active_member_ids(cls, bk_biz_id: int | list[int]) -> list[str]:
        """获取业务（集）的 active member id 列表（SQL-only，单次 ``bk_biz_id__in`` 查询）。

        用于 ES 查询前 ``exclude("terms", _id=...)``，覆盖 SearchIssue / TopN / Export 等
        所有走 IssueQueryHandler.get_search_object 的列表查询路径。接受单个或多个业务——
        ``bk_biz_ids=[-1]``（全授权业务）场景需按展开后的业务集批量排除。

        不走 service Redis：列表查询在 web role 执行，web 无 ``REDIS_*_CONF``——service
        缓存只能 api/worker 读写，web 读必失败、又无 api/worker 调用方写入，缓存恒不命中
        纯属负担。故直接 SQL（命中 ``idx_imr_biz_status_main`` 索引）。

        Fail-open：SQL 失败 → 返回 []（视为无合并，全部展示）。
        """
        biz_ids = [bk_biz_id] if isinstance(bk_biz_id, int) else list(bk_biz_id)
        if not biz_ids:
            return []
        try:
            return list(
                IssueMergeRelation.objects.filter(
                    bk_biz_id__in=biz_ids, status=IssueMergeRelation.STATUS_ACTIVE
                ).values_list("member_issue_id", flat=True)
            )
        except Exception:
            logger.warning(
                "[issue-merge] active_members SQL load failed (fail-open, bk_biz_ids=%s)",
                biz_ids,
                exc_info=True,
            )
            return []

    @classmethod
    def get_split_info_map(cls, member_ids: list[str], bk_biz_ids: list[int] | None = None) -> dict[str, dict]:
        """批量查 status='split' 关系，返回 ``{member_id: split_info}``。

        用途：列表接口给"被拆出的独立 Issue"注入永久拆分溯源（前端据此常驻展示
        「由合并拆分」+「拆分依据」标签；``split_time`` 另供前端做"刚拆出"瞬态高亮）。
        与详情 ``IssueDetailResource._fill_split_info`` 同一套 split_info 键集，差异仅
        ``split_from_main_issue_name`` 留空——列表标签不展示主名，省掉逐主名的 ES 查询。

        多次 split 取最新：``order_by("-update_time", "-id")``；``-id`` 作为 update_time
        相同时的稳定 tiebreaker（AutoField 单调递增）。

        ``bk_biz_ids`` 给定时附加 ``bk_biz_id__in`` 过滤，与详情 ``_fill_split_info`` 口径一致
        （member_issue_id 全局唯一，biz 过滤不影响正确性，仅作 defense-in-depth + 口径统一）；
        不给定则只按 member_issue_id 查（caller 已确保 id 来自鉴权结果）。

        Fail-open：SQL 失败返回 ``{}``（列表无拆分标签，不阻塞主路径）。
        """
        if not member_ids:
            return {}
        filter_kwargs = {
            "member_issue_id__in": member_ids,
            "status": IssueMergeRelation.STATUS_SPLIT,
        }
        if bk_biz_ids:
            filter_kwargs["bk_biz_id__in"] = bk_biz_ids
        try:
            rows = list(
                IssueMergeRelation.objects.filter(
                    **filter_kwargs,
                )
                .order_by("-update_time", "-id")
                .values(
                    "member_issue_id",
                    "main_issue_id",
                    "split_reasons",
                    "split_kind",
                    "update_time",
                    "update_user",
                )
            )
        except Exception:
            logger.warning(
                "[issue-merge] get_split_info_map SQL load failed (fail-open, member_ids=%s)",
                member_ids,
                exc_info=True,
            )
            return {}

        result: dict[str, dict] = {}
        for r in rows:
            member_id = r["member_issue_id"]
            # 已排序，首见即最新；同一 member 多条 split 关系只保留最新一条
            if member_id in result:
                continue
            result[member_id] = {
                "split_from_main_issue_id": r["main_issue_id"],
                "split_from_main_issue_name": None,
                "split_reasons": r["split_reasons"] or [],
                "split_kind": r["split_kind"],
                "split_time": int(r["update_time"].timestamp()) if r["update_time"] else 0,
                "split_operator": r["update_user"],
            }
        return result

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
        from bkmonitor.issue_merge.errors import IssueFrozenError

        raise IssueFrozenError(
            issue_id=issue_id,
            conflicting_main_issue_id=relation["main_issue_id"],
        )
